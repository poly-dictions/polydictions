"""News/context monitoring service for watchlist events."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from src.config import get_settings
from src.database import DatabaseManager, Repository
from src.services.polymarket import PolymarketService
from src.utils.helpers import hash_context

logger = logging.getLogger(__name__)


class NewsMonitorService:
    """Service for monitoring news/context updates on watchlist events."""

    def __init__(
        self,
        db: DatabaseManager,
        polymarket: PolymarketService,
        send_notification: Callable[[int, str], Coroutine[Any, Any, bool]],
    ) -> None:
        self.db = db
        self.polymarket = polymarket
        self.send_notification = send_notification
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_check: dict[int, float] = {}  # user_id -> timestamp

        settings = get_settings()
        self.default_interval = settings.news_check_interval

    async def start(self) -> None:
        """Start the news monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("News monitor started")

    async def stop(self) -> None:
        """Stop the news monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("News monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        # Initial delay
        await asyncio.sleep(60)

        while self._running:
            try:
                await self._check_all_watchlists()
                await asyncio.sleep(30)  # Check every 30 seconds for users who need updates
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in news monitoring: {e}")

    async def _check_all_watchlists(self) -> None:
        """Check watchlists for all users based on their intervals."""
        current_time = datetime.now().timestamp()

        async with self.db.session() as session:
            repo = Repository(session)
            watchlists = await repo.get_all_watched_slugs()

            for telegram_id, slugs in watchlists.items():
                if not slugs:
                    continue

                # Get user's interval
                user = await repo.get_user(telegram_id)
                if not user:
                    continue

                user_interval = user.news_interval or self.default_interval

                # Check if it's time for this user
                last_check = self._last_check.get(telegram_id, 0)
                if current_time - last_check < user_interval:
                    continue

                self._last_check[telegram_id] = current_time

                logger.debug(f"Checking watchlist for user {telegram_id}: {len(slugs)} events")
                await self._check_user_watchlist(repo, telegram_id, slugs, user_interval)

    async def _check_user_watchlist(
        self,
        repo: Repository,
        telegram_id: int,
        slugs: list[str],
        user_interval: int,
    ) -> None:
        """Check watchlist for a specific user and send status."""
        updates: list[tuple[str, str]] = []  # (slug, context)
        no_updates: list[str] = []

        for slug in slugs:
            try:
                new_context = await self.polymarket.fetch_market_context(slug)

                if not new_context:
                    no_updates.append(slug)
                    continue

                # Check if context changed
                new_hash = hash_context(new_context)
                changed = await repo.update_news_cache(slug, new_hash, new_context)

                if changed:
                    updates.append((slug, new_context))
                    logger.info(f"News update detected for {slug}")
                else:
                    no_updates.append(slug)

                await asyncio.sleep(2)  # Rate limit

            except Exception as e:
                logger.error(f"Error checking news for {slug}: {e}")
                no_updates.append(slug)

        # Build and send status message
        await self._send_status_message(telegram_id, updates, no_updates, user_interval)

    async def _send_status_message(
        self,
        telegram_id: int,
        updates: list[tuple[str, str]],
        no_updates: list[str],
        user_interval: int,
    ) -> None:
        """Send watchlist status message to user."""
        if not updates and not no_updates:
            return

        interval_min = user_interval // 60
        msg_parts = []

        # Add updates
        for slug, context in updates:
            truncated = context[:800] + ("..." if len(context) > 800 else "")
            msg_parts.append(
                f"<b>{slug}</b>\n"
                f"https://polymarket.com/event/{slug}\n"
                f"<b>New Update:</b>\n{truncated}"
            )

        # Add no-update items
        if no_updates:
            if len(no_updates) == 1:
                msg_parts.append(f"<b>{no_updates[0]}</b> - No new updates")
            else:
                no_update_text = "\n".join([f"• {slug}" for slug in no_updates])
                msg_parts.append(f"<b>No new updates:</b>\n{no_update_text}")

        header = (
            f"<b>Watchlist Status</b> ({datetime.now().strftime('%H:%M')})\n"
            f"Next update in {interval_min} min\n\n"
        )
        full_msg = header + "\n\n".join(msg_parts)

        # Truncate if too long
        if len(full_msg) > 4000:
            full_msg = full_msg[:3950] + "\n\n<i>...truncated</i>"

        try:
            await self.send_notification(telegram_id, full_msg)
            logger.debug(f"Sent watchlist status to user {telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send status to {telegram_id}: {e}")
