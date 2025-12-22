"""Price alert monitoring service."""

import asyncio
import logging
from typing import Any, Callable, Coroutine

from src.config import get_settings
from src.database import DatabaseManager, Repository
from src.services.polymarket import PolymarketService

logger = logging.getLogger(__name__)


class AlertMonitorService:
    """Service for monitoring price alerts."""

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

        settings = get_settings()
        self.check_interval = settings.alert_check_interval

    async def start(self) -> None:
        """Start the alert monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitor started")

    async def stop(self) -> None:
        """Stop the alert monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Alert monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_alerts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert monitoring: {e}")

    async def _check_alerts(self) -> None:
        """Check all active alerts and trigger if conditions met."""
        async with self.db.session() as session:
            repo = Repository(session)
            active_alerts = await repo.get_all_active_alerts()

            if not active_alerts:
                return

            # Group alerts by event_slug
            alerts_by_slug: dict[str, list[tuple[int, Any]]] = {}
            for telegram_id, alert in active_alerts:
                if alert.event_slug not in alerts_by_slug:
                    alerts_by_slug[alert.event_slug] = []
                alerts_by_slug[alert.event_slug].append((telegram_id, alert))

            logger.debug(f"Checking {len(active_alerts)} alerts for {len(alerts_by_slug)} events")

            # Check each event
            for slug, slug_alerts in alerts_by_slug.items():
                await self._check_event_alerts(repo, slug, slug_alerts)
                await asyncio.sleep(0.5)  # Rate limit API calls

    async def _check_event_alerts(
        self,
        repo: Repository,
        slug: str,
        alerts: list[tuple[int, Any]],
    ) -> None:
        """Check alerts for a specific event."""
        event_data = await self.polymarket.fetch_event_by_slug(slug)
        if not event_data:
            logger.warning(f"Could not fetch event for alert check: {slug}")
            return

        markets = event_data.get("markets", [])
        if not markets:
            return

        for telegram_id, alert in alerts:
            try:
                await self._check_single_alert(repo, telegram_id, alert, markets)
            except Exception as e:
                logger.error(f"Error checking alert {alert.id}: {e}")

    async def _check_single_alert(
        self,
        repo: Repository,
        telegram_id: int,
        alert: Any,
        markets: list[dict[str, Any]],
    ) -> None:
        """Check a single alert against current prices."""
        if alert.outcome_index >= len(markets):
            return

        market = markets[0]  # Use first market for now
        prices_raw = market.get("outcomePrices", [])

        # Parse prices
        if isinstance(prices_raw, str):
            import json
            try:
                prices = json.loads(prices_raw)
            except json.JSONDecodeError:
                return
        else:
            prices = prices_raw

        if alert.outcome_index >= len(prices):
            return

        current_price = float(prices[alert.outcome_index]) * 100

        # Check condition
        should_trigger = False
        if alert.condition == ">" and current_price > alert.threshold:
            should_trigger = True
        elif alert.condition == "<" and current_price < alert.threshold:
            should_trigger = True

        if should_trigger:
            await self._trigger_alert(repo, telegram_id, alert, current_price)

    async def _trigger_alert(
        self,
        repo: Repository,
        telegram_id: int,
        alert: Any,
        current_price: float,
    ) -> None:
        """Trigger an alert and notify user."""
        # Mark as triggered
        await repo.mark_alert_triggered(alert.id)

        # Send notification
        msg = (
            f"<b>Price Alert Triggered!</b>\n\n"
            f"<b>Event:</b> {alert.event_slug}\n"
            f"<b>Current price:</b> {current_price:.1f}%\n"
            f"<b>Condition:</b> {alert.condition} {alert.threshold}%\n\n"
            f"<a href='https://polymarket.com/event/{alert.event_slug}'>View Event</a>"
        )

        try:
            await self.send_notification(telegram_id, msg)
            logger.info(f"Alert triggered for user {telegram_id}: {alert.event_slug}")
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
