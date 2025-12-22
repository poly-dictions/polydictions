"""Event monitoring service for new market detection."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from src.config import get_settings
from src.database import DatabaseManager, Repository
from src.services.polymarket import PolymarketService
from src.utils.formatters import format_event
from src.utils.helpers import matches_keywords, matches_category

logger = logging.getLogger(__name__)


class EventMonitorService:
    """Service for monitoring new Polymarket events."""

    def __init__(
        self,
        db: DatabaseManager,
        polymarket: PolymarketService,
        send_notification: Callable[[int, str], Coroutine[Any, Any, bool]],
        send_to_channel: Callable[[str], Coroutine[Any, Any, bool]] | None = None,
    ) -> None:
        self.db = db
        self.polymarket = polymarket
        self.send_notification = send_notification
        self.send_to_channel = send_to_channel
        self._running = False
        self._task: asyncio.Task[None] | None = None

        settings = get_settings()
        self.check_interval = settings.event_check_interval
        self.high_volume_threshold = settings.high_volume_threshold
        self.new_event_age_hours = settings.new_event_age_hours
        self.max_seen_events = settings.max_seen_events
        self.channel_id = settings.channel_id

    async def start(self) -> None:
        """Start the event monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Event monitor started")

    async def stop(self) -> None:
        """Stop the event monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Event monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        # Initialize seen events on first run
        await self._initialize_seen_events()

        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_new_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event monitoring: {e}")

    async def _initialize_seen_events(self) -> None:
        """Initialize seen events if empty."""
        async with self.db.session() as session:
            repo = Repository(session)
            count = await repo.get_seen_events_count()

            if count == 0:
                logger.info("Initializing seen events with recent 100 events...")
                events = await self.polymarket.fetch_recent_events(limit=100)
                for event in events:
                    event_id = event.get("id")
                    if event_id:
                        await repo.mark_event_seen(str(event_id))
                logger.info(f"Initialized with {len(events)} events")

    async def _check_new_events(self) -> None:
        """Check for new events and notify users."""
        recent = await self.polymarket.fetch_recent_events(limit=20)
        new_events: list[dict[str, Any]] = []

        async with self.db.session() as session:
            repo = Repository(session)

            for event in recent:
                event_id = str(event.get("id", ""))
                if not event_id:
                    continue

                if await repo.is_event_seen(event_id):
                    continue

                # Check if event is actually new
                if not self._is_actually_new_event(event):
                    await repo.mark_event_seen(event_id)
                    continue

                await repo.mark_event_seen(event_id)
                new_events.append(event)
                logger.info(f"New event found: {event.get('title', 'N/A')[:50]}")

            # Cleanup old seen events
            await repo.cleanup_old_seen_events(self.max_seen_events)

        if not new_events:
            return

        logger.info(f"Found {len(new_events)} new events")

        # Post to channel if configured
        if self.send_to_channel and self.channel_id:
            for event in new_events:
                await self._post_to_channel(event)

        # Notify users
        await self._notify_users(new_events)

    def _is_actually_new_event(self, event: dict[str, Any]) -> bool:
        """Check if event is actually new based on creation date and volume."""
        # Check creation date
        created_at_str = event.get("createdAt") or event.get("startDate")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_hours = (now - created_at).total_seconds() / 3600
                if age_hours > self.new_event_age_hours:
                    return False
            except (ValueError, AttributeError):
                pass

        # High volume events are likely old events appearing for first time
        volume = float(event.get("volume", 0) or 0)
        if volume > self.high_volume_threshold:
            return False

        return True

    async def _post_to_channel(self, event: dict[str, Any]) -> None:
        """Post event to Telegram channel."""
        if not self.send_to_channel:
            return

        formatted = format_event(event)
        notification = f"<b>New Polymarket Event</b>\n\n{formatted}"

        try:
            await self.send_to_channel(notification)
            logger.info(f"Posted event to channel: {event.get('title', 'N/A')[:50]}")

            # Save to posted events for extension sync
            async with self.db.session() as session:
                repo = Repository(session)
                await repo.add_posted_event(event)
                await repo.cleanup_old_posted_events(50)

        except Exception as e:
            logger.error(f"Failed to post to channel: {e}")

    async def _notify_users(self, events: list[dict[str, Any]]) -> None:
        """Notify users about new events based on their filters."""
        async with self.db.session() as session:
            repo = Repository(session)
            users = await repo.get_active_users()

            for user in users:
                user_keywords = await repo.get_user_keywords(user.telegram_id)
                user_categories = await repo.get_user_categories(user.telegram_id)

                for event in events:
                    # Check filters
                    if not matches_keywords(event, user_keywords):
                        continue
                    if not matches_category(event, user_categories):
                        continue

                    # Send notification
                    formatted = format_event(event)
                    notification = f"<b>New Event Matching Your Filters</b>\n\n{formatted}"

                    try:
                        await self.send_notification(user.telegram_id, notification)
                        await asyncio.sleep(0.1)  # Rate limit
                    except Exception as e:
                        logger.error(f"Failed to notify user {user.telegram_id}: {e}")
