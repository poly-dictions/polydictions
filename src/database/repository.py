"""Repository pattern for database operations."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Keyword,
    NewsCache,
    PostedEvent,
    PriceAlert,
    SeenEvent,
    User,
    UserCategory,
    WatchlistItem,
)

logger = logging.getLogger(__name__)


class Repository:
    """Repository for all database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==================== User Operations ====================

    async def get_user(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, telegram_id: int) -> User:
        """Create a new user."""
        user = User(telegram_id=telegram_id)
        self.session.add(user)
        await self.session.flush()
        logger.info(f"Created user {telegram_id}")
        return user

    async def get_or_create_user(self, telegram_id: int) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, created)."""
        user = await self.get_user(telegram_id)
        if user:
            return user, False
        user = await self.create_user(telegram_id)
        return user, True

    async def get_all_users(self) -> list[User]:
        """Get all subscribed users."""
        result = await self.session.execute(select(User))
        return list(result.scalars().all())

    async def get_active_users(self) -> list[User]:
        """Get all active (non-paused) users."""
        result = await self.session.execute(select(User).where(User.is_paused == False))
        return list(result.scalars().all())

    async def set_user_paused(self, telegram_id: int, is_paused: bool) -> bool:
        """Set user's paused status."""
        user = await self.get_user(telegram_id)
        if not user:
            return False
        user.is_paused = is_paused
        logger.info(f"User {telegram_id} paused={is_paused}")
        return True

    async def set_user_interval(self, telegram_id: int, interval: int) -> bool:
        """Set user's news check interval (in seconds)."""
        user = await self.get_user(telegram_id)
        if not user:
            return False
        user.news_interval = interval
        return True

    # ==================== Seen Events Operations ====================

    async def is_event_seen(self, event_id: str) -> bool:
        """Check if event has been seen."""
        result = await self.session.execute(
            select(SeenEvent).where(SeenEvent.event_id == event_id)
        )
        return result.scalar_one_or_none() is not None

    async def mark_event_seen(self, event_id: str) -> None:
        """Mark event as seen."""
        if not await self.is_event_seen(event_id):
            self.session.add(SeenEvent(event_id=event_id))

    async def get_seen_events_count(self) -> int:
        """Get count of seen events."""
        result = await self.session.execute(select(func.count(SeenEvent.id)))
        return result.scalar() or 0

    async def cleanup_old_seen_events(self, max_count: int = 10000) -> int:
        """Remove old seen events to prevent unbounded growth."""
        count = await self.get_seen_events_count()
        if count <= max_count:
            return 0

        to_delete = count - max_count
        subquery = (
            select(SeenEvent.id)
            .order_by(SeenEvent.created_at.asc())
            .limit(to_delete)
        )
        result = await self.session.execute(
            delete(SeenEvent).where(SeenEvent.id.in_(subquery))
        )
        deleted = result.rowcount
        logger.info(f"Cleaned up {deleted} old seen events")
        return deleted

    # ==================== Keywords Operations ====================

    async def get_user_keywords(self, telegram_id: int) -> list[str]:
        """Get user's keywords."""
        user = await self.get_user(telegram_id)
        if not user:
            return []
        result = await self.session.execute(
            select(Keyword.keyword).where(Keyword.user_id == user.id)
        )
        return list(result.scalars().all())

    async def set_user_keywords(self, telegram_id: int, keywords: list[str]) -> bool:
        """Set user's keywords (replaces existing)."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        # Delete existing keywords
        await self.session.execute(delete(Keyword).where(Keyword.user_id == user.id))

        # Add new keywords
        for kw in keywords:
            self.session.add(Keyword(user_id=user.id, keyword=kw.strip().lower()))

        logger.info(f"User {telegram_id} set {len(keywords)} keywords")
        return True

    async def clear_user_keywords(self, telegram_id: int) -> bool:
        """Clear all user's keywords."""
        user = await self.get_user(telegram_id)
        if not user:
            return False
        await self.session.execute(delete(Keyword).where(Keyword.user_id == user.id))
        return True

    # ==================== Categories Operations ====================

    async def get_user_categories(self, telegram_id: int) -> list[str]:
        """Get user's category filters."""
        user = await self.get_user(telegram_id)
        if not user:
            return []
        result = await self.session.execute(
            select(UserCategory.category).where(UserCategory.user_id == user.id)
        )
        return list(result.scalars().all())

    async def set_user_categories(self, telegram_id: int, categories: list[str]) -> bool:
        """Set user's categories (replaces existing)."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        await self.session.execute(delete(UserCategory).where(UserCategory.user_id == user.id))

        for cat in categories:
            self.session.add(UserCategory(user_id=user.id, category=cat.strip().lower()))

        logger.info(f"User {telegram_id} set {len(categories)} categories")
        return True

    async def clear_user_categories(self, telegram_id: int) -> bool:
        """Clear user's categories."""
        user = await self.get_user(telegram_id)
        if not user:
            return False
        await self.session.execute(delete(UserCategory).where(UserCategory.user_id == user.id))
        return True

    # ==================== Watchlist Operations ====================

    async def get_user_watchlist(self, telegram_id: int) -> list[str]:
        """Get user's watchlist slugs."""
        user = await self.get_user(telegram_id)
        if not user:
            return []
        result = await self.session.execute(
            select(WatchlistItem.event_slug).where(WatchlistItem.user_id == user.id)
        )
        return list(result.scalars().all())

    async def add_to_watchlist(self, telegram_id: int, event_slug: str) -> bool:
        """Add event to user's watchlist."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        # Check if already exists
        existing = await self.session.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user.id, WatchlistItem.event_slug == event_slug
            )
        )
        if existing.scalar_one_or_none():
            return False

        self.session.add(WatchlistItem(user_id=user.id, event_slug=event_slug))
        logger.info(f"User {telegram_id} added {event_slug} to watchlist")
        return True

    async def remove_from_watchlist(self, telegram_id: int, event_slug: str) -> bool:
        """Remove event from user's watchlist."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        result = await self.session.execute(
            delete(WatchlistItem).where(
                WatchlistItem.user_id == user.id, WatchlistItem.event_slug == event_slug
            )
        )
        return result.rowcount > 0

    async def get_all_watched_slugs(self) -> dict[int, list[str]]:
        """Get all watchlist items grouped by user telegram_id."""
        result = await self.session.execute(
            select(User.telegram_id, WatchlistItem.event_slug)
            .join(WatchlistItem, User.id == WatchlistItem.user_id)
        )

        watchlists: dict[int, list[str]] = {}
        for telegram_id, slug in result:
            if telegram_id not in watchlists:
                watchlists[telegram_id] = []
            watchlists[telegram_id].append(slug)

        return watchlists

    # ==================== Price Alerts Operations ====================

    async def get_user_alerts(self, telegram_id: int) -> list[PriceAlert]:
        """Get user's price alerts."""
        user = await self.get_user(telegram_id)
        if not user:
            return []
        result = await self.session.execute(
            select(PriceAlert).where(PriceAlert.user_id == user.id)
        )
        return list(result.scalars().all())

    async def add_alert(
        self,
        telegram_id: int,
        event_slug: str,
        condition: str,
        threshold: float,
        outcome_index: int = 0,
    ) -> bool:
        """Add a price alert."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        # Check if alert already exists
        existing = await self.session.execute(
            select(PriceAlert).where(
                PriceAlert.user_id == user.id,
                PriceAlert.event_slug == event_slug,
                PriceAlert.condition == condition,
                PriceAlert.threshold == threshold,
                PriceAlert.outcome_index == outcome_index,
            )
        )
        if existing.scalar_one_or_none():
            return False

        self.session.add(
            PriceAlert(
                user_id=user.id,
                event_slug=event_slug,
                condition=condition,
                threshold=threshold,
                outcome_index=outcome_index,
            )
        )
        logger.info(f"User {telegram_id} added alert: {event_slug} {condition} {threshold}")
        return True

    async def remove_alert(self, telegram_id: int, alert_index: int) -> bool:
        """Remove alert by index (0-based)."""
        alerts = await self.get_user_alerts(telegram_id)
        if alert_index < 0 or alert_index >= len(alerts):
            return False

        alert = alerts[alert_index]
        await self.session.delete(alert)
        return True

    async def get_all_active_alerts(self) -> list[tuple[int, PriceAlert]]:
        """Get all active (non-triggered) alerts with user telegram_id."""
        result = await self.session.execute(
            select(User.telegram_id, PriceAlert)
            .join(PriceAlert, User.id == PriceAlert.user_id)
            .where(PriceAlert.is_triggered == False)
        )
        return [(telegram_id, alert) for telegram_id, alert in result]

    async def mark_alert_triggered(self, alert_id: int) -> None:
        """Mark alert as triggered."""
        result = await self.session.execute(
            select(PriceAlert).where(PriceAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_triggered = True
            alert.triggered_at = datetime.utcnow()

    # ==================== News Cache Operations ====================

    async def get_news_cache(self, event_slug: str) -> NewsCache | None:
        """Get cached news for event."""
        result = await self.session.execute(
            select(NewsCache).where(NewsCache.event_slug == event_slug)
        )
        return result.scalar_one_or_none()

    async def update_news_cache(
        self, event_slug: str, context_hash: str, context_preview: str
    ) -> bool:
        """Update news cache. Returns True if content changed."""
        cache = await self.get_news_cache(event_slug)

        if cache:
            if cache.context_hash == context_hash:
                return False  # No change
            cache.context_hash = context_hash
            cache.context_preview = context_preview[:500]
        else:
            self.session.add(
                NewsCache(
                    event_slug=event_slug,
                    context_hash=context_hash,
                    context_preview=context_preview[:500],
                )
            )

        return True

    # ==================== Posted Events Operations ====================

    async def add_posted_event(self, event_data: dict[str, Any]) -> None:
        """Add posted event for Chrome extension sync."""
        self.session.add(
            PostedEvent(
                event_id=str(event_data.get("id", "")),
                event_slug=event_data.get("slug", ""),
                title=event_data.get("title", "")[:500] if event_data.get("title") else None,
                volume=float(event_data.get("volume") or 0),
                liquidity=float(event_data.get("liquidity") or 0),
            )
        )

    async def get_posted_events(self, limit: int = 50) -> list[PostedEvent]:
        """Get recent posted events."""
        result = await self.session.execute(
            select(PostedEvent).order_by(PostedEvent.posted_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def cleanup_old_posted_events(self, keep_count: int = 50) -> int:
        """Keep only the most recent posted events."""
        count_result = await self.session.execute(select(func.count(PostedEvent.id)))
        count = count_result.scalar() or 0

        if count <= keep_count:
            return 0

        subquery = (
            select(PostedEvent.id)
            .order_by(PostedEvent.posted_at.asc())
            .limit(count - keep_count)
        )
        result = await self.session.execute(
            delete(PostedEvent).where(PostedEvent.id.in_(subquery))
        )
        return result.rowcount
