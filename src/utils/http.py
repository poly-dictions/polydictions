"""HTTP client with proper SSL handling."""

import logging
from typing import Any, Optional

import aiohttp
import certifi

logger = logging.getLogger(__name__)


class HttpClient:
    """Async HTTP client with proper SSL certificate verification."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper SSL."""
        if self._session is None or self._session.closed:
            # Use certifi for proper SSL certificate verification
            ssl_context = aiohttp.TCPConnector(ssl=certifi.where())
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=ssl_context,
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        """Make GET request and return JSON response."""
        session = await self._get_session()
        request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None

        try:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=request_timeout,
            ) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"GET {url} returned status {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error on GET {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error on GET {url}: {e}")
            return None

    async def post(
        self,
        url: str,
        data: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[str | dict[str, Any]]:
        """Make POST request and return response."""
        session = await self._get_session()
        request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None

        default_headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if headers:
            default_headers.update(headers)

        try:
            async with session.post(
                url,
                data=data,
                json=json,
                headers=default_headers,
                timeout=request_timeout,
            ) as response:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        return await response.json()
                    return await response.text()
                logger.warning(f"POST {url} returned status {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error on POST {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error on POST {url}: {e}")
            return None

    async def __aenter__(self) -> "HttpClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
