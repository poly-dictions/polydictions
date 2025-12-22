"""Polymarket API service with proper SSL handling."""

import asyncio
import logging
from typing import Any, Optional

from src.config import get_settings
from src.utils.http import HttpClient

logger = logging.getLogger(__name__)


class PolymarketService:
    """Service for interacting with Polymarket API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = settings.polymarket_api_url
        self.grok_url = settings.polymarket_grok_url
        self.http_timeout = settings.http_timeout
        self.context_timeout = settings.market_context_timeout
        self._http_client: Optional[HttpClient] = None

    async def _get_client(self) -> HttpClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = HttpClient(timeout=self.http_timeout)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

    async def fetch_event_by_slug(self, slug: str) -> Optional[dict[str, Any]]:
        """Fetch event data by slug."""
        client = await self._get_client()
        url = f"{self.api_url}/events"
        params = {"slug": slug}

        result = await client.get(url, params=params, timeout=15)

        if isinstance(result, list) and len(result) > 0:
            return result[0]

        logger.warning(f"Event not found: {slug}")
        return None

    async def fetch_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent active events sorted by creation date."""
        client = await self._get_client()
        url = f"{self.api_url}/events"
        params = {
            "limit": str(limit),
            "offset": "0",
            "closed": "false",
            "active": "true",
            "order": "createdAt",
            "ascending": "false",
        }

        result = await client.get(url, params=params, timeout=15)

        if isinstance(result, list):
            return result

        logger.warning("Failed to fetch recent events")
        return []

    async def fetch_hot_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch hot events sorted by volume."""
        client = await self._get_client()
        url = f"{self.api_url}/events"
        params = {
            "limit": str(limit),
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }

        result = await client.get(url, params=params, timeout=30)

        if isinstance(result, list):
            return result

        return []

    async def fetch_market_context(
        self, event_slug: str, retry: int = 0
    ) -> Optional[str]:
        """
        Fetch Market Context from Polymarket Grok API.
        Provides AI-generated context about the market/event.
        """
        if not event_slug:
            logger.error("Cannot fetch Market Context: event_slug is empty")
            return None

        client = await self._get_client()
        url = f"{self.grok_url}?prompt={event_slug}"

        logger.info(f"Fetching Market Context for: {event_slug} (attempt {retry + 1}/2)")

        try:
            result = await client.post(url, timeout=self.context_timeout)

            if isinstance(result, str) and len(result) > 50:
                # Remove sources block if present
                if "__SOURCES__" in result:
                    result = result.split("__SOURCES__")[0].strip()
                logger.info(f"Got Market Context for {event_slug} ({len(result)} chars)")
                return result

            # Retry if response is too short
            if retry < 1:
                logger.warning(f"Context too short ({len(result) if result else 0} chars), retrying...")
                await asyncio.sleep(2)
                return await self.fetch_market_context(event_slug, retry + 1)

        except asyncio.TimeoutError:
            logger.error(f"Market Context request timed out (attempt {retry + 1}/2)")
            if retry < 1:
                await asyncio.sleep(2)
                return await self.fetch_market_context(event_slug, retry + 1)

        except Exception as e:
            logger.error(f"Error fetching Market Context: {e}")

        return None

    async def __aenter__(self) -> "PolymarketService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
