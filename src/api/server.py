"""HTTP API server for Chrome extension sync with authentication and rate limiting."""

import hashlib
import hmac
import logging
import time
from collections import defaultdict
from typing import Any, Optional

from aiohttp import web

from src.config import get_settings
from src.database import DatabaseManager, Repository
from src.services.polymarket import PolymarketService

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for API endpoints."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for given client."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old requests
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]

        # Check limit
        if len(self._requests[client_id]) >= self.max_requests:
            return False

        # Record request
        self._requests[client_id].append(now)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """Get seconds until next request is allowed."""
        if not self._requests[client_id]:
            return 0
        oldest = min(self._requests[client_id])
        retry_after = int(oldest + self.window_seconds - time.time())
        return max(0, retry_after)

    def cleanup(self) -> None:
        """Remove stale entries to prevent memory growth."""
        now = time.time()
        cutoff = now - self.window_seconds
        stale_keys = [
            key for key, timestamps in self._requests.items()
            if not timestamps or max(timestamps) < cutoff
        ]
        for key in stale_keys:
            del self._requests[key]


class APIServer:
    """HTTP API server with authentication, rate limiting, and CORS for Chrome extension sync."""

    def __init__(self, db: DatabaseManager, polymarket: PolymarketService) -> None:
        self.db = db
        self.polymarket = polymarket
        self.settings = get_settings()

        # Rate limiters with different limits per endpoint type
        self._global_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100/min per IP
        self._auth_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10/min for auth failures

        self.app = web.Application(
            middlewares=[
                self._rate_limit_middleware,
                self._cors_middleware,
                self._auth_middleware,
            ]
        )
        self._runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up API routes."""
        self.app.router.add_get("/health", self._health_check)
        self.app.router.add_get("/api/watchlist/{user_id}", self._get_watchlist)
        self.app.router.add_post("/api/watchlist/{user_id}", self._update_watchlist)
        self.app.router.add_get("/api/events", self._get_events)
        self.app.router.add_get("/api/new-markets", self._get_new_markets)
        self.app.router.add_options("/{path:.*}", self._handle_options)

    def _get_client_ip(self, request: web.Request) -> str:
        """Extract client IP from request, considering proxies."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        peername = request.transport.get_extra_info("peername") if request.transport else None
        if peername:
            return peername[0]

        return "unknown"

    @web.middleware
    async def _rate_limit_middleware(
        self,
        request: web.Request,
        handler: Any,
    ) -> web.Response:
        """Rate limiting middleware to prevent abuse."""
        # Skip rate limiting for health checks
        if request.path == "/health":
            return await handler(request)

        client_ip = self._get_client_ip(request)

        # Check global rate limit
        if not self._global_limiter.is_allowed(client_ip):
            retry_after = self._global_limiter.get_retry_after(client_ip)
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return web.json_response(
                {
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                status=429,
                headers={"Retry-After": str(retry_after)},
            )

        return await handler(request)

    @web.middleware
    async def _cors_middleware(
        self,
        request: web.Request,
        handler: Any,
    ) -> web.Response:
        """CORS middleware with strict origin validation."""
        origin = request.headers.get("Origin", "")
        response = await handler(request)

        # Determine if origin is allowed
        is_allowed = False

        # Check explicitly allowed origins
        allowed_origins = self.settings.allowed_origins_list
        if origin in allowed_origins:
            is_allowed = True

        # Check Chrome extension origins - ONLY allow specific extension IDs
        elif origin.startswith("chrome-extension://"):
            extension_id = origin.replace("chrome-extension://", "").split("/")[0]
            allowed_extensions = self.settings.allowed_extension_ids_list

            if allowed_extensions and extension_id in allowed_extensions:
                is_allowed = True
                logger.debug(f"Allowed Chrome extension: {extension_id}")
            else:
                logger.warning(
                    f"Blocked unauthorized Chrome extension: {extension_id}. "
                    f"Add to ALLOWED_EXTENSION_IDS if legitimate."
                )

        # Set CORS headers only for allowed origins
        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-Telegram-User-Id, X-Auth-Hash"
            )
        else:
            # Log blocked cross-origin requests (except empty origins from same-origin)
            if origin:
                logger.warning(f"CORS blocked origin: {origin}")

        return response

    @web.middleware
    async def _auth_middleware(
        self,
        request: web.Request,
        handler: Any,
    ) -> web.Response:
        """Authentication middleware with logging for security monitoring."""
        client_ip = self._get_client_ip(request)

        # Skip auth for health check and OPTIONS
        if request.path == "/health" or request.method == "OPTIONS":
            return await handler(request)

        # Skip auth for GET events and new-markets (public data)
        if request.path in ("/api/events", "/api/new-markets") and request.method == "GET":
            return await handler(request)

        # Require auth for user-specific endpoints
        if "/watchlist/" in request.path:
            user_id = request.headers.get("X-Telegram-User-Id")
            auth_hash = request.headers.get("X-Auth-Hash")

            if not user_id or not auth_hash:
                # Check rate limit for auth failures to prevent brute force
                if not self._auth_limiter.is_allowed(client_ip):
                    retry_after = self._auth_limiter.get_retry_after(client_ip)
                    logger.warning(
                        f"Auth rate limit exceeded for IP {client_ip} - "
                        f"too many failed attempts"
                    )
                    return web.json_response(
                        {"error": "Too many authentication attempts", "retry_after": retry_after},
                        status=429,
                        headers={"Retry-After": str(retry_after)},
                    )

                logger.warning(
                    f"Missing auth headers from IP {client_ip} for {request.path}"
                )
                return web.json_response(
                    {"error": "Missing authentication headers"},
                    status=401,
                )

            # Verify hash
            if not self._verify_auth(user_id, auth_hash):
                # Rate limit failed auth attempts
                if not self._auth_limiter.is_allowed(client_ip):
                    retry_after = self._auth_limiter.get_retry_after(client_ip)
                    logger.warning(
                        f"Auth rate limit exceeded for IP {client_ip} - "
                        f"too many failed attempts"
                    )
                    return web.json_response(
                        {"error": "Too many authentication attempts", "retry_after": retry_after},
                        status=429,
                        headers={"Retry-After": str(retry_after)},
                    )

                logger.warning(
                    f"Invalid auth hash from IP {client_ip} for user_id={user_id}"
                )
                return web.json_response(
                    {"error": "Invalid authentication"},
                    status=401,
                )

            # Verify user_id in path matches header
            path_user_id = request.match_info.get("user_id")
            if path_user_id != user_id:
                logger.warning(
                    f"User ID mismatch from IP {client_ip}: "
                    f"path={path_user_id}, header={user_id}"
                )
                return web.json_response(
                    {"error": "User ID mismatch"},
                    status=403,
                )

        return await handler(request)

    def _verify_auth(self, user_id: str, auth_hash: str) -> bool:
        """Verify authentication hash."""
        # Generate expected hash: HMAC-SHA256(secret_key, user_id)
        expected = hmac.new(
            self.settings.api_secret_key.encode(),
            user_id.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, auth_hash)

    async def _handle_options(self, request: web.Request) -> web.Response:
        """Handle CORS preflight requests."""
        return web.Response(status=200)

    async def _health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})

    async def _get_watchlist(self, request: web.Request) -> web.Response:
        """Get user's watchlist."""
        user_id = request.match_info.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)

        try:
            telegram_id = int(user_id)
            async with self.db.session() as session:
                repo = Repository(session)
                watchlist = await repo.get_user_watchlist(telegram_id)

            return web.json_response({"success": True, "watchlist": watchlist})
        except ValueError:
            return web.json_response({"error": "Invalid user_id"}, status=400)
        except Exception as e:
            logger.error(f"Error getting watchlist: {e}")
            return web.json_response({"success": False, "error": "Internal error"}, status=500)

    async def _update_watchlist(self, request: web.Request) -> web.Response:
        """Update user's watchlist from extension."""
        user_id = request.match_info.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)

        try:
            telegram_id = int(user_id)
            body = await request.json()
            slugs = body.get("slugs", [])

            if not isinstance(slugs, list):
                return web.json_response({"error": "slugs must be a list"}, status=400)

            async with self.db.session() as session:
                repo = Repository(session)

                # Ensure user exists
                await repo.get_or_create_user(telegram_id)

                # Get current watchlist
                current = await repo.get_user_watchlist(telegram_id)

                # Remove items not in new list
                for slug in current:
                    if slug not in slugs:
                        await repo.remove_from_watchlist(telegram_id, slug)

                # Add new items
                for slug in slugs:
                    if slug not in current:
                        await repo.add_to_watchlist(telegram_id, slug)

            return web.json_response({"success": True})
        except ValueError:
            return web.json_response({"error": "Invalid user_id"}, status=400)
        except Exception as e:
            logger.error(f"Error updating watchlist: {e}")
            return web.json_response({"success": False, "error": "Internal error"}, status=500)

    async def _get_events(self, request: web.Request) -> web.Response:
        """Proxy to Polymarket API with caching."""
        limit = request.query.get("limit", "200")

        try:
            limit_int = min(int(limit), 500)  # Cap at 500
            events = await self.polymarket.fetch_hot_events(limit=limit_int)
            return web.json_response(events)
        except ValueError:
            return web.json_response({"error": "Invalid limit"}, status=400)
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return web.json_response({"error": "Failed to fetch events"}, status=500)

    async def _get_new_markets(self, request: web.Request) -> web.Response:
        """Get recently posted new markets (same as Telegram channel)."""
        try:
            async with self.db.session() as session:
                repo = Repository(session)
                events = await repo.get_posted_events(limit=50)

            # Convert to dict format
            events_data = [
                {
                    "id": e.event_id,
                    "slug": e.event_slug,
                    "title": e.title,
                    "volume": e.volume,
                    "liquidity": e.liquidity,
                    "posted_at": e.posted_at.isoformat() if e.posted_at else None,
                }
                for e in events
            ]

            return web.json_response({"success": True, "events": events_data})
        except Exception as e:
            logger.error(f"Error getting new markets: {e}")
            return web.json_response({"success": False, "error": "Internal error"}, status=500)

    async def start(self) -> None:
        """Start the API server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()

        site = web.TCPSite(
            self._runner,
            self.settings.api_host,
            self.settings.api_port,
        )
        await site.start()

        logger.info(
            f"API server started on http://{self.settings.api_host}:{self.settings.api_port}"
        )

    async def stop(self) -> None:
        """Stop the API server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("API server stopped")
