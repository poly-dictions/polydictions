import os
import json
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Set
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Import new features
from features import Watchlist, Categories, Alerts

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

POLYMARKET_API = "https://gamma-api.polymarket.com"
USERS_FILE = "users.json"
SEEN_EVENTS_FILE = "seen_events.json"
KEYWORDS_FILE = "keywords.json"
PAUSED_USERS_FILE = "paused_users.json"
CHECK_INTERVAL = 60  # Check every 60 seconds (1 minute)

subscribed_users: Set[int] = set()
seen_events: Set[str] = set()
user_keywords: Dict[int, List[str]] = {}
paused_users: Set[int] = set()


class Storage:

    @staticmethod
    def load_users() -> Set[int]:
        if Path(USERS_FILE).exists():
            try:
                with open(USERS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('users', []))
            except Exception as e:
                logger.error(f"Error loading users: {e}")
        return set()
    
    @staticmethod
    def save_users(users: Set[int]):
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump({'users': list(users)}, f, indent=2)
            logger.info(f"Saved {len(users)} users")
        except Exception as e:
            logger.error(f"Error saving users: {e}")

    @staticmethod
    def load_seen_events() -> Set[str]:
        if Path(SEEN_EVENTS_FILE).exists():
            try:
                with open(SEEN_EVENTS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('events', []))
            except Exception as e:
                logger.error(f"Error loading events: {e}")
        return set()

    @staticmethod
    def save_seen_events(events: Set[str]):
        try:
            with open(SEEN_EVENTS_FILE, 'w') as f:
                json.dump({'events': list(events)}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving events: {e}")

    @staticmethod
    def load_keywords() -> Dict[int, List[str]]:
        if Path(KEYWORDS_FILE).exists():
            try:
                with open(KEYWORDS_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    return {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading keywords: {e}")
        return {}

    @staticmethod
    def save_keywords(keywords: Dict[int, List[str]]):
        try:
            with open(KEYWORDS_FILE, 'w') as f:
                json.dump(keywords, f, indent=2)
            logger.info(f"Saved keywords for {len(keywords)} users")
        except Exception as e:
            logger.error(f"Error saving keywords: {e}")

    @staticmethod
    def load_paused_users() -> Set[int]:
        if Path(PAUSED_USERS_FILE).exists():
            try:
                with open(PAUSED_USERS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('users', []))
            except Exception as e:
                logger.error(f"Error loading paused users: {e}")
        return set()

    @staticmethod
    def save_paused_users(users: Set[int]):
        try:
            with open(PAUSED_USERS_FILE, 'w') as f:
                json.dump({'users': list(users)}, f, indent=2)
            logger.info(f"Saved {len(users)} paused users")
        except Exception as e:
            logger.error(f"Error saving paused users: {e}")


class PolymarketAPI:

    @staticmethod
    def matches_keywords(event_data: Dict, keywords: List[str]) -> bool:
        """
        Check if event matches any of the user's keywords.
        Supports:
        - Simple word matching (case-insensitive)
        - Phrase matching with quotes
        - OR logic (comma-separated keywords)

        Examples:
        - btc, eth -> matches events with 'btc' OR 'eth'
        - "united states", election -> matches events with phrase "united states" OR word "election"
        """
        if not keywords:
            return True  # No filters = show all events

        title = event_data.get('title', '').lower()

        # Also check market questions
        markets = event_data.get('markets', [])
        market_text = ' '.join([m.get('question', '').lower() for m in markets])

        # Combined searchable text
        searchable = f"{title} {market_text}"

        # Check each keyword (OR logic)
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue

            # Check if it's a phrase (has quotes)
            if (keyword.startswith('"') and keyword.endswith('"')) or \
               (keyword.startswith("'") and keyword.endswith("'")):
                # Phrase matching - remove quotes
                phrase = keyword[1:-1].lower()
                if phrase in searchable:
                    return True
            else:
                # Simple word matching
                if keyword.lower() in searchable:
                    return True

        return False

    @staticmethod
    async def fetch_market_context(event_slug: str, market_question: str = None, retry: int = 0) -> Optional[str]:
        """
        Fetch Market Context from Polymarket API.
        This provides AI-generated context about the market/event.
        IMPORTANT: Must use event_slug in the prompt parameter, not market_question.
        """
        if not event_slug:
            logger.error("Cannot fetch Market Context: event_slug is empty")
            return None

        # The API only accepts event slugs, not market questions
        url = f"https://polymarket.com/api/grok/event-summary?prompt={event_slug}"

        # Create a timeout object with 120 seconds total timeout
        timeout = aiohttp.ClientTimeout(total=120)

        # Create SSL context that doesn't verify certificates (fixes Windows SSL issues)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                logger.info(f"Fetching Market Context for: {event_slug} (attempt {retry + 1}/2)")
                async with session.post(
                    url,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': '*/*',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                ) as response:
                    logger.info(f"Market Context API status: {response.status}")
                    if response.status == 200:
                        text = await response.text()
                        logger.info(f"Received response of length: {len(text)} chars")
                        if text and len(text) > 50:
                            # Remove sources block if present
                            if '__SOURCES__' in text:
                                text = text.split('__SOURCES__')[0].strip()
                            logger.info(f"✓ Got Market Context (length: {len(text)} chars)")
                            return text
                        else:
                            logger.warning(f"Market Context response too short: {len(text)} chars")
                            logger.warning(f"Response: {text}")
                            # Retry if response is too short and we haven't retried yet
                            if retry < 1 and len(text) < 50:
                                logger.info("Retrying due to short response...")
                                await asyncio.sleep(2)
                                return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
                    elif response.status == 400:
                        logger.error(f"Bad Request (400) - Invalid event slug: {event_slug}")
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                    else:
                        logger.warning(f"Market Context API returned status: {response.status}")
                        error_text = await response.text()
                        logger.warning(f"Error response: {error_text}")
                        # Retry on 5xx errors
                        if retry < 1 and response.status >= 500:
                            logger.info("Retrying due to server error...")
                            await asyncio.sleep(3)
                            return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
        except asyncio.TimeoutError:
            logger.error(f"Market Context request timed out after 120 seconds (attempt {retry + 1}/2)")
            # Retry once on timeout
            if retry < 1:
                logger.info("Retrying after timeout...")
                await asyncio.sleep(2)
                return await PolymarketAPI.fetch_market_context(event_slug, market_question, retry + 1)
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Market Context: {e}")
        except Exception as e:
            logger.error(f"Error fetching Market Context: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return None

    @staticmethod
    async def fetch_ai_analysis(event_slug: str, event_id: str = None) -> Optional[str]:
        """Fetch AI analysis from Polymarket Grok API (legacy method, now uses fetch_market_context)"""
        return await PolymarketAPI.fetch_market_context(event_slug)

    @staticmethod
    async def fetch_event_by_slug(slug: str) -> Optional[Dict]:
        url = f"{POLYMARKET_API}/events"
        params = {"slug": slug}

        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        events = await response.json()
                        if isinstance(events, list) and len(events) > 0:
                            return events[0]
                    else:
                        logger.error(f"Failed to fetch event: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching event '{slug}': {e}")

        return None

    @staticmethod
    async def fetch_recent_events(limit: int = 20) -> List[Dict]:
        url = f"{POLYMARKET_API}/events"
        params = {
            "limit": limit,
            "offsetgit init": 0,
            "closed": "false",
            "order": "new"
        }

        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        events = await response.json()
                        return events if isinstance(events, list) else []
                    else:
                        logger.error(f"Failed to fetch events: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching events: {e}")

        return []
    
    @staticmethod
    def parse_polymarket_url(url: str) -> Optional[str]:
        pattern = r'polymarket\.com/event/([a-zA-Z0-9\-]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def format_money(value) -> str:
        try:
            num = float(value) if value else 0
            return f"${num:,.0f}"
        except:
            return "$0"
    
    @staticmethod
    def format_date(date_str: str) -> str:
        if not date_str:
            return "N/A"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %H:%M UTC')
        except:
            return date_str
    
    @staticmethod
    def calculate_totals(markets: List[Dict]) -> tuple:
        total_liquidity = 0.0
        total_volume = 0.0
        for market in markets:
            try:
                liquidity = float(market.get('liquidityNum', market.get('liquidity', 0)) or 0)
                total_liquidity += liquidity
            except:
                pass

            try:
                volume = float(market.get('volumeNum', market.get('volume', 0)) or 0)
                total_volume += volume
            except:
                pass
        
        return total_liquidity, total_volume

    @staticmethod
    def format_event(event_data: Dict) -> str:
        try:
            title = event_data.get('title', 'Unknown Event')
            slug = event_data.get('slug', '')
            markets = event_data.get('markets', [])
            
            if not markets:
                return "No market data available"
            
            event_liquidity = event_data.get('liquidity')
            event_volume = event_data.get('volume')
            
            if event_liquidity is not None and event_volume is not None:
                total_liquidity = float(event_liquidity)
                total_volume = float(event_volume)
            else:
                total_liquidity, total_volume = PolymarketAPI.calculate_totals(markets)
            
            end_date = event_data.get('endDate')
            if not end_date and markets:
                end_date = markets[0].get('endDate') or markets[0].get('end_date_iso')
            
            formatted_date = PolymarketAPI.format_date(end_date)
            
            msg = []
            msg.append(f"🟠 <b>{title}</b>\n")
            msg.append(f"🔗 <b>Link:</b> https://polymarket.com/event/{slug}\n")
            msg.append(f"🟠 <b>Market stats:</b>")
            msg.append(f"<b>Closes:</b> {formatted_date}")
            msg.append(f"<b>Total Liquidity:</b> {PolymarketAPI.format_money(total_liquidity)}")
            msg.append(f"<b>Total Volume:</b> {PolymarketAPI.format_money(total_volume)}\n")
            
            if len(markets) == 1:
                market = markets[0]
                outcomes = market.get('outcomes', [])
                
                if outcomes and isinstance(outcomes, str):
                    try:
                        outcomes = json.loads(outcomes)
                    except:
                        outcomes = []
                
                outcome_prices = market.get('outcomePrices')
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except:
                        outcome_prices = []
                
                if len(outcomes) == 2:
                    msg.append("🟠 <b>Current Odds:</b>")
                    for idx, outcome in enumerate(outcomes):
                        name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                        if outcome_prices and idx < len(outcome_prices):
                            price = float(outcome_prices[idx])
                            percentage = price * 100 if price <= 1 else price
                            msg.append(f"  • {name}: {percentage:.1f}%")
                else:
                    msg.append("🟠 <b>Options:</b>")
                    for idx, outcome in enumerate(outcomes):
                        name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                        if outcome_prices and idx < len(outcome_prices):
                            price = float(outcome_prices[idx])
                            percentage = price * 100 if price <= 1 else price
                            msg.append(f"  {idx + 1}. {name}: {percentage:.1f}%")
            else:
                # Filter markets with valid data
                valid_markets = []
                for market in markets:
                    market_outcomes = market.get('outcomes', [])
                    if isinstance(market_outcomes, str):
                        try:
                            market_outcomes = json.loads(market_outcomes)
                        except:
                            market_outcomes = []
                    
                    market_prices = market.get('outcomePrices')
                    if isinstance(market_prices, str):
                        try:
                            market_prices = json.loads(market_prices)
                        except:
                            market_prices = []
                    
                    # Only include markets with valid outcomes and prices
                    if market_outcomes and market_prices:
                        valid_markets.append(market)
                
                msg.append(f"🟠 <b>Markets ({len(valid_markets)}):</b>")
                for idx, market in enumerate(valid_markets, 1):
                    question = market.get('question', f'Market {idx}')
                    msg.append(f"  {idx}. {question}")
                    
                    market_outcomes = market.get('outcomes', [])
                    if isinstance(market_outcomes, str):
                        try:
                            market_outcomes = json.loads(market_outcomes)
                        except:
                            market_outcomes = []
                    
                    market_prices = market.get('outcomePrices')
                    if isinstance(market_prices, str):
                        try:
                            market_prices = json.loads(market_prices)
                        except:
                            market_prices = []
                    
                    if market_outcomes and market_prices:
                        for o_idx, outcome in enumerate(market_outcomes[:5]):
                            o_name = outcome.get('name', outcome) if isinstance(outcome, dict) else outcome
                            if o_idx < len(market_prices):
                                o_price = float(market_prices[o_idx])
                                o_percentage = o_price * 100 if o_price <= 1 else o_price
                                msg.append(f"     • {o_name}: {o_percentage:.1f}%")
            
            return "\n".join(msg)

        except Exception as e:
            logger.error(f"Error formatting event: {e}")
            return "Error formatting event data"

    @staticmethod
    async def format_event_with_ai(event_data: Dict) -> str:
        """Format event with Market Context from Polymarket"""
        # Get basic format
        basic_msg = PolymarketAPI.format_event(event_data)

        # Get the market question for more specific context
        slug = event_data.get('slug', '')
        markets = event_data.get('markets', [])
        market_question = None

        # Use the first market's question if available
        if markets and len(markets) > 0:
            market_question = markets[0].get('question')

        # Fetch Market Context from Polymarket
        market_context = await PolymarketAPI.fetch_market_context(slug, market_question)

        if market_context:
            context_msg = f"\n\n🧠 <b>Market Context:</b>\n{market_context}"
            # Don't truncate - show full context
            return basic_msg + context_msg

        return basic_msg


class PolydictionsBot:
    
    def __init__(self, token: str):
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        # Initialize new features
        self.watchlist = Watchlist()
        self.categories = Categories()
        self.alerts = Alerts()

        self.setup_handlers()

        global subscribed_users, seen_events, user_keywords, paused_users
        subscribed_users = Storage.load_users()
        seen_events = Storage.load_seen_events()
        user_keywords = Storage.load_keywords()
        paused_users = Storage.load_paused_users()

        logger.info(f"Loaded {len(subscribed_users)} users, {len(seen_events)} events, "
                   f"{len(user_keywords)} keyword filters, {len(paused_users)} paused users")
    
    def setup_handlers(self):
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_deal, Command("deal"))
        self.dp.message.register(self.cmd_help, Command("help"))
        self.dp.message.register(self.cmd_keywords, Command("keywords"))
        self.dp.message.register(self.cmd_pause, Command("pause"))
        self.dp.message.register(self.cmd_resume, Command("resume"))

        # New feature handlers
        self.dp.message.register(self.cmd_watch, Command("watch"))
        self.dp.message.register(self.cmd_unwatch, Command("unwatch"))
        self.dp.message.register(self.cmd_watchlist, Command("watchlist"))
        self.dp.message.register(self.cmd_category, Command("category"))
        self.dp.message.register(self.cmd_categories, Command("categories"))
        self.dp.message.register(self.cmd_alert, Command("alert"))
        self.dp.message.register(self.cmd_alerts, Command("alerts"))
        self.dp.message.register(self.cmd_rmalert, Command("rmalert"))
    
    async def cmd_start(self, message: Message):
        user_id = message.from_user.id
        subscribed_users.add(user_id)
        Storage.save_users(subscribed_users)

        text = (
            "🎯 <b>Welcome to Polydictions Bot</b>\n\n"
            "Track and analyze Polymarket events.\n\n"
            "<b>📊 Main Commands:</b>\n"
            "/deal &lt;link&gt; - Analyze event with AI Context\n"
            "/start - Subscribe to notifications\n"
            "/pause - Pause notifications\n"
            "/resume - Resume notifications\n\n"
            "<b>🔍 Filters:</b>\n"
            "/keywords - Filter by keywords\n"
            "/category - Filter by category (crypto, politics, sports)\n"
            "/categories - Show all categories\n\n"
            "<b>📋 Watchlist:</b>\n"
            "/watch &lt;slug&gt; - Add to watchlist\n"
            "/watchlist - Show watchlist\n"
            "/unwatch &lt;slug&gt; - Remove from watchlist\n\n"
            "<b>🔔 Price Alerts:</b>\n"
            "/alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
            "/alerts - Show alerts\n"
            "/rmalert &lt;#&gt; - Remove alert\n\n"
            "You're now subscribed to new events! 🔔\n\n"
            "💡 <b>Pro tip:</b> Use /category or /keywords to filter events!"
        )

        await message.answer(text)
        logger.info(f"User {user_id} subscribed")
    
    async def cmd_deal(self, message: Message):
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer(
                "❌ Please provide a Polymarket link.\n\n"
                "Example:\n/deal https://polymarket.com/event/your-event-slug"
            )
            return

        url = parts[1].strip()
        slug = PolymarketAPI.parse_polymarket_url(url)

        if not slug:
            await message.answer("❌ Invalid Polymarket URL")
            return

        processing = await message.answer("⏳ Fetching event data...")

        try:
            event_data = await PolymarketAPI.fetch_event_by_slug(slug)

            if not event_data:
                await processing.edit_text("❌ Event not found")
                return

            # Format basic event info
            basic_msg = PolymarketAPI.format_event(event_data)

            # Send basic info first
            await processing.edit_text(basic_msg)

            # Now fetch Market Context (this takes time)
            context_msg = await message.answer("🧠 Generating Market Context... (this may take 10-30 seconds)")

            # Get the market question for more specific context
            markets = event_data.get('markets', [])
            market_question = None
            if markets and len(markets) > 0:
                market_question = markets[0].get('question')

            # Fetch Market Context
            event_slug = event_data.get('slug', '')
            logger.info(f"Attempting to fetch Market Context for slug: {event_slug}")

            market_context = await PolymarketAPI.fetch_market_context(
                event_slug,
                market_question
            )

            if market_context:
                logger.info(f"Successfully fetched Market Context: {len(market_context)} chars")
                context_text = f"🧠 <b>Market Context:</b>\n\n{market_context}"

                # Check if context is too long
                if len(context_text) > 4000:
                    # Split into chunks
                    await context_msg.edit_text("🧠 <b>Market Context:</b>\n\n(Message too long, sending in parts...)")
                    chunks = [market_context[i:i+3900] for i in range(0, len(market_context), 3900)]
                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await context_msg.edit_text(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                        else:
                            await message.answer(f"🧠 <b>Market Context (Part {idx+1}):</b>\n\n{chunk}")
                else:
                    await context_msg.edit_text(context_text)
            else:
                logger.error(f"Market Context returned None for slug: {event_slug}")
                await context_msg.edit_text(
                    "⚠️ Market Context generation failed.\n\n"
                    "This can happen if:\n"
                    "• The event is too new\n"
                    "• The API is temporarily unavailable\n"
                    "• The event doesn't have enough data\n\n"
                    "Check bot logs for details."
                )

            logger.info(f"User {message.from_user.id} checked event: {slug}")

        except Exception as e:
            logger.error(f"Error in /deal: {e}")
            await processing.edit_text(f"❌ Error: {str(e)}")
    
    async def cmd_help(self, message: Message):
        text = (
            "<b>Polydictions Bot</b>\n\n"
            "<b>📊 Main Commands:</b>\n"
            "/deal &lt;link&gt; - Analyze event with Market Context\n"
            "/start - Subscribe to notifications\n"
            "/pause - Pause notifications\n"
            "/resume - Resume notifications\n\n"
            "<b>🔍 Filters:</b>\n"
            "/keywords - Filter by keywords\n"
            "/category - Filter by category (crypto, politics, sports)\n"
            "/categories - Show all categories\n\n"
            "<b>📋 Watchlist:</b>\n"
            "/watch &lt;slug&gt; - Add to watchlist\n"
            "/watchlist - Show watchlist\n"
            "/unwatch &lt;slug&gt; - Remove from watchlist\n\n"
            "<b>🔔 Price Alerts:</b>\n"
            "/alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
            "/alerts - Show alerts\n"
            "/rmalert &lt;#&gt; - Remove alert\n\n"
            "<b>Features:</b>\n"
            "• 🧠 AI-powered Market Context\n"
            "• 📈 Event statistics & odds\n"
            "• 🔔 Price alerts\n"
            "• 📋 Watchlist tracking\n"
            "• 🔍 Smart filtering"
        )

        await message.answer(text)

    async def cmd_keywords(self, message: Message):
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        # Show current keywords and help
        if len(parts) < 2:
            current = user_keywords.get(user_id, [])
            if current:
                keywords_text = ", ".join(current)
                help_text = (
                    f"<b>Your current keywords:</b>\n{keywords_text}\n\n"
                    "<b>How to use:</b>\n"
                    "/keywords btc, eth, election - Set keywords\n"
                    "/keywords clear - Remove all filters\n\n"
                    "<b>Filter options:</b>\n"
                    "• Simple words: btc, eth, sports\n"
                    "• Phrases: \"united states\", \"world cup\"\n"
                    "• OR logic: keywords separated by commas\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>btc, eth</code> → any event with btc OR eth\n"
                    "• <code>\"united states\", election</code> → phrase + word\n"
                    "• <code>sports, football, basketball</code> → any sports event\n\n"
                    "Only events matching your keywords will be sent!"
                )
            else:
                help_text = (
                    "<b>Keyword Filters</b>\n\n"
                    "Filter events by keywords to see only what matters!\n\n"
                    "<b>How to use:</b>\n"
                    "/keywords btc, eth, election - Set keywords\n"
                    "/keywords clear - Remove all filters\n\n"
                    "<b>Filter options:</b>\n"
                    "• Simple words: btc, eth, sports\n"
                    "• Phrases: \"united states\", \"world cup\"\n"
                    "• OR logic: keywords separated by commas\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>btc, eth</code> → any event with btc OR eth\n"
                    "• <code>\"united states\", election</code> → phrase + word\n"
                    "• <code>sports, football, basketball</code> → any sports event\n\n"
                    "Currently no filters set - you'll receive all events."
                )

            await message.answer(help_text)
            return

        # Parse keywords
        keyword_input = parts[1].strip()

        # Clear keywords
        if keyword_input.lower() == "clear":
            if user_id in user_keywords:
                del user_keywords[user_id]
                Storage.save_keywords(user_keywords)
                await message.answer("✅ All keyword filters removed. You'll receive all events.")
            else:
                await message.answer("You don't have any keyword filters set.")
            return

        # Parse comma-separated keywords
        keywords = [k.strip() for k in keyword_input.split(',')]
        keywords = [k for k in keywords if k]  # Remove empty strings

        if not keywords:
            await message.answer("❌ Please provide at least one keyword.")
            return

        # Save keywords
        user_keywords[user_id] = keywords
        Storage.save_keywords(user_keywords)

        keywords_display = "\n".join([f"  • {k}" for k in keywords])
        await message.answer(
            f"✅ <b>Keywords saved!</b>\n\n"
            f"You will only receive events matching:\n{keywords_display}\n\n"
            f"Use /keywords clear to remove filters."
        )
        logger.info(f"User {user_id} set keywords: {keywords}")

    async def cmd_pause(self, message: Message):
        user_id = message.from_user.id

        if user_id in paused_users:
            await message.answer("You're already paused. Use /resume to resume notifications.")
            return

        paused_users.add(user_id)
        Storage.save_paused_users(paused_users)

        await message.answer(
            "⏸️ <b>Notifications paused</b>\n\n"
            "You won't receive any new event notifications.\n\n"
            "Use /resume when you want to resume notifications."
        )
        logger.info(f"User {user_id} paused notifications")

    async def cmd_resume(self, message: Message):
        user_id = message.from_user.id

        if user_id not in paused_users:
            await message.answer("You're not paused. Notifications are already active!")
            return

        paused_users.remove(user_id)
        Storage.save_paused_users(paused_users)

        keywords_info = ""
        if user_id in user_keywords:
            keywords_info = f"\n\n🔍 Active filters: {', '.join(user_keywords[user_id])}"

        await message.answer(
            f"▶️ <b>Notifications resumed</b>\n\n"
            f"You'll receive new event notifications again!{keywords_info}"
        )
        logger.info(f"User {user_id} resumed notifications")

    # Watchlist commands
    async def cmd_watch(self, message: Message):
        """Add event to watchlist"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer(
                "❌ Please provide a Polymarket link or event slug.\n\n"
                "Example:\n/watch https://polymarket.com/event/btc-price-2025\n"
                "or\n/watch btc-price-2025"
            )
            return

        url_or_slug = parts[1].strip()
        slug = PolymarketAPI.parse_polymarket_url(url_or_slug)
        if not slug:
            slug = url_or_slug

        if self.watchlist.add(user_id, slug):
            await message.answer(f"✅ Added <b>{slug}</b> to your watchlist!")
            logger.info(f"User {user_id} added {slug} to watchlist")
        else:
            await message.answer("⚠️ This event is already in your watchlist.")

    async def cmd_unwatch(self, message: Message):
        """Remove event from watchlist"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("❌ Please provide an event slug.\n\nExample:\n/unwatch btc-price-2025")
            return

        slug = parts[1].strip()

        if self.watchlist.remove(user_id, slug):
            await message.answer(f"✅ Removed <b>{slug}</b> from your watchlist.")
            logger.info(f"User {user_id} removed {slug} from watchlist")
        else:
            await message.answer("⚠️ Event not found in your watchlist.")

    async def cmd_watchlist(self, message: Message):
        """Show user's watchlist"""
        user_id = message.from_user.id
        watchlist = self.watchlist.get(user_id)

        if not watchlist:
            await message.answer(
                "📋 <b>Your Watchlist is empty</b>\n\n"
                "Add events with:\n/watch &lt;event-slug&gt;"
            )
            return

        msg = ["📋 <b>Your Watchlist:</b>\n"]
        for idx, slug in enumerate(watchlist, 1):
            msg.append(f"{idx}. {slug}")
            msg.append(f"   https://polymarket.com/event/{slug}\n")

        msg.append(f"\n<b>Total:</b> {len(watchlist)} events")
        msg.append("\nUse /unwatch &lt;slug&gt; to remove")

        await message.answer("\n".join(msg))

    # Category filter commands
    async def cmd_category(self, message: Message):
        """Set category filters"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            current_cats = self.categories.get_categories(user_id)
            all_cats = self.categories.get_all_categories()

            if current_cats:
                msg = f"<b>Your categories:</b> {', '.join(current_cats)}\n\n"
            else:
                msg = "<b>No category filters set</b>\n\n"

            msg += "<b>Available categories:</b>\n"
            msg += ", ".join(all_cats)
            msg += "\n\n<b>Usage:</b>\n"
            msg += "/category crypto politics\n"
            msg += "/category clear - Remove filters"

            await message.answer(msg)
            return

        categories_input = parts[1].strip()

        if categories_input.lower() == "clear":
            self.categories.clear_categories(user_id)
            await message.answer("✅ Category filters cleared. You'll receive all events.")
            logger.info(f"User {user_id} cleared category filters")
            return

        categories = [c.strip() for c in categories_input.split()]

        if self.categories.set_categories(user_id, categories):
            await message.answer(
                f"✅ <b>Category filters set!</b>\n\n"
                f"You'll only receive events in:\n{', '.join(self.categories.get_categories(user_id))}"
            )
            logger.info(f"User {user_id} set categories: {categories}")
        else:
            await message.answer(
                f"❌ Invalid categories.\n\n"
                f"Available: {', '.join(self.categories.get_all_categories())}"
            )

    async def cmd_categories(self, message: Message):
        """Show all available categories"""
        all_cats = self.categories.get_all_categories()
        msg = "<b>📂 Available Categories:</b>\n\n"
        msg += "\n".join([f"• {cat}" for cat in all_cats])
        msg += "\n\n<b>Usage:</b>\n/category crypto politics"

        await message.answer(msg)

    # Price alert commands
    async def cmd_alert(self, message: Message):
        """Set price alert"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()

        if len(parts) < 4:
            await message.answer(
                "❌ Invalid format.\n\n"
                "<b>Usage:</b>\n"
                "/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;\n"
                "/alert &lt;event-slug&gt; &lt; &lt;threshold&gt;\n\n"
                "<b>Examples:</b>\n"
                "/alert btc-price-2025 &gt; 70\n"
                "/alert election-winner &lt; 30"
            )
            return

        slug = parts[1]
        condition = parts[2]
        try:
            threshold = float(parts[3])
        except ValueError:
            await message.answer("❌ Threshold must be a number (0-100)")
            return

        if condition not in [">", "<"]:
            await message.answer("❌ Condition must be '>' or '<'")
            return

        if threshold < 0 or threshold > 100:
            await message.answer("❌ Threshold must be between 0 and 100")
            return

        if self.alerts.add_alert(user_id, slug, condition, threshold):
            await message.answer(
                f"✅ <b>Alert set!</b>\n\n"
                f"Event: {slug}\n"
                f"Condition: {condition} {threshold}%\n\n"
                f"You'll be notified when the price crosses this threshold."
            )
            logger.info(f"User {user_id} set alert: {slug} {condition} {threshold}%")
        else:
            await message.answer("⚠️ This alert already exists.")

    async def cmd_alerts(self, message: Message):
        """Show user's alerts"""
        user_id = message.from_user.id
        alerts = self.alerts.get_alerts(user_id)

        if not alerts:
            await message.answer(
                "🔔 <b>No alerts set</b>\n\n"
                "Set alerts with:\n/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;"
            )
            return

        msg = ["🔔 <b>Your Price Alerts:</b>\n"]
        for idx, alert in enumerate(alerts):
            status = "✅ Triggered" if alert.triggered else "⏳ Active"
            msg.append(f"{idx + 1}. {alert.event_slug}")
            msg.append(f"   {alert.condition} {alert.threshold}% - {status}\n")

        msg.append(f"\n<b>Total:</b> {len(alerts)} alerts")
        msg.append("\nUse /rmalert &lt;number&gt; to remove")

        await message.answer("\n".join(msg))

    async def cmd_rmalert(self, message: Message):
        """Remove price alert"""
        user_id = message.from_user.id
        text = message.text or ""
        parts = text.split()

        if len(parts) < 2:
            await message.answer("❌ Please provide alert number.\n\nExample:\n/rmalert 1")
            return

        try:
            index = int(parts[1]) - 1
        except ValueError:
            await message.answer("❌ Invalid number")
            return

        if self.alerts.remove_alert(user_id, index):
            await message.answer("✅ Alert removed!")
            logger.info(f"User {user_id} removed alert {index}")
        else:
            await message.answer("❌ Alert not found.")

    async def check_new_events(self):
        global seen_events
        logger.info(f"Starting event monitoring with {len(seen_events)} seen events already loaded")

        if not seen_events:
            logger.info("Seen events is empty, initializing with recent 100 events...")
            initial = await PolymarketAPI.fetch_recent_events(limit=100)
            for event in initial:
                event_id = event.get('id')
                if event_id:
                    seen_events.add(str(event_id))
            Storage.save_seen_events(seen_events)
            logger.info(f"Initialized with {len(seen_events)} events")
        else:
            logger.info(f"Using existing {len(seen_events)} seen events from storage")
            # Also fetch recent events and add any we might have missed
            logger.info("Refreshing with recent events to catch any gaps...")
            initial = await PolymarketAPI.fetch_recent_events(limit=50)
            added_count = 0
            for event in initial:
                event_id = str(event.get('id', ''))
                if event_id and event_id not in seen_events:
                    volume = float(event.get('volume', 0) or 0)
                    # Only add if volume > $10k (likely old event we missed)
                    if volume > 10000:
                        seen_events.add(event_id)
                        added_count += 1
                        logger.info(f"Added missed event to seen list: ID={event_id}, Volume=${volume:,.0f}")
            if added_count > 0:
                Storage.save_seen_events(seen_events)
                logger.info(f"Added {added_count} previously missed events to seen list")
        
        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL)
                
                recent = await PolymarketAPI.fetch_recent_events(limit=20)
                new_events = []
                filtered_count = 0
                filtered_high_volume = 0

                for event in recent:
                    event_id = str(event.get('id', ''))
                    if event_id:
                        if event_id not in seen_events:
                            # Additional check: filter out events with high volume (likely old events)
                            # If volume > $50k, it's probably been around for a while
                            volume = float(event.get('volume', 0) or 0)

                            if volume > 50000:
                                # This is likely an old event with high volume, mark as seen but don't notify
                                seen_events.add(event_id)
                                filtered_high_volume += 1
                                logger.info(f"Filtered high-volume event: ID={event_id}, Volume=${volume:,.0f}, Title={event.get('title', 'N/A')[:50]}")
                            else:
                                # This is a genuinely new event
                                seen_events.add(event_id)
                                new_events.append(event)
                                logger.info(f"New event found: ID={event_id}, Volume=${volume:,.0f}, Title={event.get('title', 'N/A')[:50]}")
                        else:
                            filtered_count += 1

                logger.info(f"Checked {len(recent)} events: {len(new_events)} new, {filtered_count} already seen, {filtered_high_volume} filtered (high volume)")

                if new_events:
                    Storage.save_seen_events(seen_events)
                    logger.info(f"Found {len(new_events)} new events")

                    if subscribed_users:
                        for event in new_events:
                            formatted = PolymarketAPI.format_event(event)
                            notification = f"<b>New Polymarket Event</b>\n\n{formatted}"

                            for user_id in list(subscribed_users):
                                try:
                                    # Skip if user is paused
                                    if user_id in paused_users:
                                        continue

                                    # Check keyword filters
                                    user_filter = user_keywords.get(user_id, [])
                                    if user_filter and not PolymarketAPI.matches_keywords(event, user_filter):
                                        # Event doesn't match user's keywords, skip
                                        continue

                                    # Send notification
                                    await self.bot.send_message(user_id, notification)
                                    await asyncio.sleep(0.5)
                                except Exception as e:
                                    logger.error(f"Failed to notify {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Error in monitoring: {e}")
    
    async def start(self):
        asyncio.create_task(self.check_new_events())
        
        logger.info("Bot started")
        await self.dp.start_polling(self.bot, allowed_updates=["message"])


async def main():
    token = None
    
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from config import BOT_TOKEN
        token = BOT_TOKEN
        logger.info("Loaded token from config.py")
    except ImportError as e:
        logger.error(f"Failed to import config.py: {e}")
        token = os.getenv('BOT_TOKEN')
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("BOT_TOKEN not found!")
        logger.error(f".env path: {Path(__file__).parent / '.env'}")
        logger.error(f".env exists: {(Path(__file__).parent / '.env').exists()}")
        logger.error("Create .env with: BOT_TOKEN=your_token")
        logger.error("Or config.py with: BOT_TOKEN = 'your_token'")
        return

    token = token.strip()
    
    bot = PolydictionsBot(token)
    await bot.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
