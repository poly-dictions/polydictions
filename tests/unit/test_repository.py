"""Tests for database repository."""

import pytest
import pytest_asyncio

from src.database import DatabaseManager, Repository


@pytest_asyncio.fixture
async def test_db():
    """Create in-memory database for testing."""
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.close()


@pytest.mark.asyncio
class TestUserOperations:
    """Tests for user-related repository operations."""

    async def test_create_user(self, test_db: DatabaseManager):
        """Test user creation."""
        async with test_db.session() as session:
            repo = Repository(session)
            user = await repo.create_user(123456)
            assert user.telegram_id == 123456

    async def test_get_user(self, test_db: DatabaseManager):
        """Test getting user."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            user = await repo.get_user(123456)
            assert user is not None
            assert user.telegram_id == 123456

    async def test_get_nonexistent_user(self, test_db: DatabaseManager):
        """Test getting nonexistent user."""
        async with test_db.session() as session:
            repo = Repository(session)
            user = await repo.get_user(999999)
            assert user is None

    async def test_get_or_create_user_new(self, test_db: DatabaseManager):
        """Test get_or_create creates new user."""
        async with test_db.session() as session:
            repo = Repository(session)
            user, created = await repo.get_or_create_user(123456)
            assert created is True
            assert user.telegram_id == 123456

    async def test_get_or_create_user_existing(self, test_db: DatabaseManager):
        """Test get_or_create returns existing user."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            user, created = await repo.get_or_create_user(123456)
            assert created is False

    async def test_set_user_paused(self, test_db: DatabaseManager):
        """Test setting user paused status."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            result = await repo.set_user_paused(123456, True)
            assert result is True

            user = await repo.get_user(123456)
            assert user.is_paused is True


@pytest.mark.asyncio
class TestKeywordOperations:
    """Tests for keyword-related repository operations."""

    async def test_set_keywords(self, test_db: DatabaseManager):
        """Test setting user keywords."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            result = await repo.set_user_keywords(123456, ["btc", "eth"])
            assert result is True

    async def test_get_keywords(self, test_db: DatabaseManager):
        """Test getting user keywords."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.set_user_keywords(123456, ["btc", "eth"])
            keywords = await repo.get_user_keywords(123456)
            assert len(keywords) == 2
            assert "btc" in keywords

    async def test_clear_keywords(self, test_db: DatabaseManager):
        """Test clearing user keywords."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.set_user_keywords(123456, ["btc", "eth"])
            await repo.clear_user_keywords(123456)
            keywords = await repo.get_user_keywords(123456)
            assert len(keywords) == 0


@pytest.mark.asyncio
class TestWatchlistOperations:
    """Tests for watchlist-related repository operations."""

    async def test_add_to_watchlist(self, test_db: DatabaseManager):
        """Test adding to watchlist."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            result = await repo.add_to_watchlist(123456, "btc-price-2025")
            assert result is True

    async def test_add_duplicate_to_watchlist(self, test_db: DatabaseManager):
        """Test adding duplicate to watchlist."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_to_watchlist(123456, "btc-price-2025")
            result = await repo.add_to_watchlist(123456, "btc-price-2025")
            assert result is False

    async def test_remove_from_watchlist(self, test_db: DatabaseManager):
        """Test removing from watchlist."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_to_watchlist(123456, "btc-price-2025")
            result = await repo.remove_from_watchlist(123456, "btc-price-2025")
            assert result is True

    async def test_get_watchlist(self, test_db: DatabaseManager):
        """Test getting watchlist."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_to_watchlist(123456, "btc-price-2025")
            await repo.add_to_watchlist(123456, "eth-price-2025")
            watchlist = await repo.get_user_watchlist(123456)
            assert len(watchlist) == 2


@pytest.mark.asyncio
class TestAlertOperations:
    """Tests for alert-related repository operations."""

    async def test_add_alert(self, test_db: DatabaseManager):
        """Test adding price alert."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            result = await repo.add_alert(123456, "btc-price-2025", ">", 70.0)
            assert result is True

    async def test_add_duplicate_alert(self, test_db: DatabaseManager):
        """Test adding duplicate alert."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_alert(123456, "btc-price-2025", ">", 70.0)
            result = await repo.add_alert(123456, "btc-price-2025", ">", 70.0)
            assert result is False

    async def test_get_alerts(self, test_db: DatabaseManager):
        """Test getting user alerts."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_alert(123456, "btc-price-2025", ">", 70.0)
            await repo.add_alert(123456, "eth-price-2025", "<", 30.0)
            alerts = await repo.get_user_alerts(123456)
            assert len(alerts) == 2

    async def test_remove_alert(self, test_db: DatabaseManager):
        """Test removing alert by index."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.create_user(123456)
            await repo.add_alert(123456, "btc-price-2025", ">", 70.0)
            result = await repo.remove_alert(123456, 0)
            assert result is True

            alerts = await repo.get_user_alerts(123456)
            assert len(alerts) == 0


@pytest.mark.asyncio
class TestSeenEventsOperations:
    """Tests for seen events operations."""

    async def test_mark_event_seen(self, test_db: DatabaseManager):
        """Test marking event as seen."""
        async with test_db.session() as session:
            repo = Repository(session)
            await repo.mark_event_seen("event-123")
            is_seen = await repo.is_event_seen("event-123")
            assert is_seen is True

    async def test_event_not_seen(self, test_db: DatabaseManager):
        """Test event not seen."""
        async with test_db.session() as session:
            repo = Repository(session)
            is_seen = await repo.is_event_seen("event-456")
            assert is_seen is False

    async def test_cleanup_old_events(self, test_db: DatabaseManager):
        """Test cleanup of old seen events."""
        async with test_db.session() as session:
            repo = Repository(session)
            # Add many events
            for i in range(15):
                await repo.mark_event_seen(f"event-{i}")

            # Cleanup to keep only 10
            deleted = await repo.cleanup_old_seen_events(max_count=10)
            assert deleted == 5
