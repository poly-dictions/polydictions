"""Watchlist command handlers."""

import logging

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from pydantic import ValidationError

from src.config.constants import MIN_NEWS_INTERVAL
from src.database import Repository
from src.services.polymarket import PolymarketService
from src.utils.helpers import hash_context
from src.utils.validators import IntervalInput, WatchInput, validate_polymarket_url

logger = logging.getLogger(__name__)
router = Router(name="watchlist")


class WatchlistStates(StatesGroup):
    """States for watchlist command flow."""

    waiting_for_link = State()


@router.message(Command("watch"))
async def cmd_watch(
    message: Message,
    state: FSMContext,
    repo: Repository,
    polymarket: PolymarketService,
) -> None:
    """Handle /watch command - add event to watchlist."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "<b>Send me a Polymarket link to watch</b>\n\n"
            "Example:\nhttps://polymarket.com/event/btc-price-2025"
        )
        await state.set_state(WatchlistStates.waiting_for_link)
        return

    url_or_slug = parts[1].strip()
    await _add_to_watchlist(message, user_id, url_or_slug, repo, polymarket)


@router.message(StateFilter(WatchlistStates.waiting_for_link))
async def handle_watch_link(
    message: Message,
    state: FSMContext,
    repo: Repository,
    polymarket: PolymarketService,
) -> None:
    """Handle link sent after /watch command."""
    await state.clear()

    if not message.from_user or not message.text:
        return

    await _add_to_watchlist(
        message, message.from_user.id, message.text.strip(), repo, polymarket
    )


async def _add_to_watchlist(
    message: Message,
    user_id: int,
    url_or_slug: str,
    repo: Repository,
    polymarket: PolymarketService,
) -> None:
    """Add event to user's watchlist."""
    slug = validate_polymarket_url(url_or_slug)

    if not slug:
        await message.answer(
            "Invalid link. Please send a valid Polymarket URL.\n\n"
            "Example: https://polymarket.com/event/your-event-slug"
        )
        return

    try:
        WatchInput(event_slug=slug)
    except ValidationError as e:
        await message.answer(f"Invalid input: {e.errors()[0]['msg']}")
        return

    # Ensure user exists
    await repo.get_or_create_user(user_id)

    if await repo.add_to_watchlist(user_id, slug):
        await message.answer(f"Added <b>{slug}</b> to your watchlist!\n\nFetching Market Context...")

        # Fetch and cache initial context
        try:
            context = await polymarket.fetch_market_context(slug)
            if context:
                context_hash = hash_context(context)
                await repo.update_news_cache(slug, context_hash, context)

                truncated = context[:2000] + ("..." if len(context) > 2000 else "")
                await message.answer(f"<b>Market Context for {slug}:</b>\n\n{truncated}")
            else:
                await message.answer("Could not fetch Market Context for this event.")
        except Exception as e:
            logger.error(f"Error fetching context for {slug}: {e}")
            await message.answer("Error fetching Market Context.")
    else:
        await message.answer(f"<b>{slug}</b> is already in your watchlist.")


@router.message(Command("unwatch"))
async def cmd_unwatch(message: Message, repo: Repository) -> None:
    """Handle /unwatch command - remove from watchlist."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Please provide an event slug.\n\nExample:\n/unwatch btc-price-2025"
        )
        return

    slug = parts[1].strip().lower()

    if await repo.remove_from_watchlist(user_id, slug):
        await message.answer(f"Removed <b>{slug}</b> from your watchlist.")
        logger.info(f"User {user_id} removed {slug} from watchlist")
    else:
        await message.answer("Event not found in your watchlist.")


@router.message(Command("watchlist"))
async def cmd_watchlist(message: Message, repo: Repository) -> None:
    """Handle /watchlist command - show user's watchlist."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    watchlist = await repo.get_user_watchlist(user_id)

    if not watchlist:
        await message.answer(
            "<b>Your Watchlist is empty</b>\n\n"
            "Add events with:\n/watch &lt;event-slug&gt;"
        )
        return

    lines = ["<b>Your Watchlist:</b>\n"]
    for idx, slug in enumerate(watchlist, 1):
        lines.append(f"{idx}. {slug}")
        lines.append(f"   https://polymarket.com/event/{slug}\n")

    lines.append(f"\n<b>Total:</b> {len(watchlist)} events")
    lines.append("\nUse /unwatch &lt;slug&gt; to remove")

    await message.answer("\n".join(lines))


@router.message(Command("interval"))
async def cmd_interval(message: Message, repo: Repository) -> None:
    """Handle /interval command - set watchlist update interval."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user = await repo.get_user(user_id)
    current_interval = (user.news_interval // 60) if user else 5

    text = message.text or ""
    parts = text.split()

    if len(parts) < 2:
        await message.answer(
            f"<b>Update Interval</b>\n\n"
            f"Current: <b>{current_interval} minutes</b>\n\n"
            f"<b>Usage:</b>\n"
            f"/interval &lt;minutes&gt;\n\n"
            f"<b>Examples:</b>\n"
            f"/interval 3 - every 3 minutes\n"
            f"/interval 10 - every 10 minutes\n"
            f"/interval 30 - every 30 minutes\n\n"
            f"<i>Minimum: {MIN_NEWS_INTERVAL // 60} minutes</i>"
        )
        return

    try:
        validated = IntervalInput(minutes=int(parts[1]))
        seconds = validated.minutes * 60

        await repo.get_or_create_user(user_id)
        await repo.set_user_interval(user_id, seconds)

        await message.answer(
            f"<b>Interval set to {validated.minutes} minutes!</b>\n\n"
            f"You'll receive watchlist updates every {validated.minutes} minutes."
        )
    except ValueError:
        await message.answer("Please provide a valid number of minutes.")
    except ValidationError:
        await message.answer(
            f"Minimum interval is {MIN_NEWS_INTERVAL // 60} minutes.\n\n"
            f"Example: /interval 3"
        )
