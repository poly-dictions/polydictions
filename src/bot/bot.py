"""Main bot class with setup and lifecycle management."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands

from src.bot.handlers import (
    alerts_router,
    common_router,
    deal_router,
    filters_router,
    watchlist_router,
)
from src.bot.middlewares import DatabaseMiddleware, ErrorsMiddleware, RateLimitMiddleware
from src.config import get_settings
from src.database import DatabaseManager
from src.services import (
    AlertMonitorService,
    EventMonitorService,
    NewsMonitorService,
    PolymarketService,
)

logger = logging.getLogger(__name__)


class PolydictionsBot:
    """Main bot class managing all components."""

    def __init__(self, db: DatabaseManager) -> None:
        settings = get_settings()

        self.bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self.db = db
        self.polymarket = PolymarketService()

        # Monitor services
        self.event_monitor: Optional[EventMonitorService] = None
        self.alert_monitor: Optional[AlertMonitorService] = None
        self.news_monitor: Optional[NewsMonitorService] = None

        self._setup_middlewares()
        self._setup_routers()

    def _setup_middlewares(self) -> None:
        """Set up bot middlewares."""
        # Outer middlewares (run first, catch all errors)
        self.dp.update.outer_middleware(ErrorsMiddleware())
        self.dp.update.outer_middleware(RateLimitMiddleware())

        # Inner middlewares (provide data to handlers)
        self.dp.update.middleware(DatabaseMiddleware(self.db))

    def _setup_routers(self) -> None:
        """Set up message routers."""
        self.dp.include_router(common_router)
        self.dp.include_router(deal_router)
        self.dp.include_router(watchlist_router)
        self.dp.include_router(alerts_router)
        self.dp.include_router(filters_router)

    async def setup_commands(self) -> None:
        """Set up bot menu commands."""
        commands = [
            BotCommand(command="start", description="Subscribe to notifications"),
            BotCommand(command="deal", description="Analyze event with AI"),
            BotCommand(command="watchlist", description="Show your watchlist"),
            BotCommand(command="watch", description="Add event to watchlist"),
            BotCommand(command="interval", description="Set update interval"),
            BotCommand(command="alerts", description="Show price alerts"),
            BotCommand(command="alert", description="Set price alert"),
            BotCommand(command="keywords", description="Set keyword filters"),
            BotCommand(command="categories", description="Show categories"),
            BotCommand(command="pause", description="Pause notifications"),
            BotCommand(command="resume", description="Resume notifications"),
            BotCommand(command="help", description="Show help"),
        ]

        await self.bot.set_my_commands(commands)
        await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Bot menu commands configured")

    async def send_notification(self, user_id: int, text: str) -> bool:
        """Send notification to user."""
        try:
            await self.bot.send_message(user_id, text)
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            return False

    async def send_to_channel(self, text: str) -> bool:
        """Send message to configured channel."""
        settings = get_settings()
        if not settings.channel_id:
            return False

        try:
            await self.bot.send_message(settings.channel_id, text)
            return True
        except Exception as e:
            logger.error(f"Failed to send to channel: {e}")
            return False

    async def _start_monitors(self) -> None:
        """Start background monitoring services."""
        # Event monitor
        self.event_monitor = EventMonitorService(
            db=self.db,
            polymarket=self.polymarket,
            send_notification=self.send_notification,
            send_to_channel=self.send_to_channel,
        )
        await self.event_monitor.start()

        # Alert monitor
        self.alert_monitor = AlertMonitorService(
            db=self.db,
            polymarket=self.polymarket,
            send_notification=self.send_notification,
        )
        await self.alert_monitor.start()

        # News monitor
        self.news_monitor = NewsMonitorService(
            db=self.db,
            polymarket=self.polymarket,
            send_notification=self.send_notification,
        )
        await self.news_monitor.start()

        logger.info("All monitoring services started")

    async def _stop_monitors(self) -> None:
        """Stop background monitoring services."""
        if self.event_monitor:
            await self.event_monitor.stop()
        if self.alert_monitor:
            await self.alert_monitor.stop()
        if self.news_monitor:
            await self.news_monitor.stop()

        logger.info("All monitoring services stopped")

    async def start(self) -> None:
        """Start the bot."""
        # Register startup/shutdown handlers
        self.dp.startup.register(self._on_startup)
        self.dp.shutdown.register(self._on_shutdown)

        # Inject polymarket service into dispatcher
        self.dp["polymarket"] = self.polymarket

        logger.info("Starting bot...")
        await self.dp.start_polling(self.bot, allowed_updates=["message", "callback_query"])

    async def _on_startup(self) -> None:
        """Called when bot starts."""
        await self.setup_commands()
        await self._start_monitors()
        logger.info("Bot started successfully")

    async def _on_shutdown(self) -> None:
        """Called when bot stops."""
        logger.info("Shutting down...")
        await self._stop_monitors()
        await self.polymarket.close()
        await self.bot.session.close()
        logger.info("Bot shutdown complete")
