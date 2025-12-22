"""Rate limiting middleware for aiogram."""

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from src.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware for rate limiting user requests."""

    def __init__(self) -> None:
        settings = get_settings()
        self.max_requests = settings.rate_limit_requests
        self.period = settings.rate_limit_period

        # Store request timestamps per user: {user_id: [timestamps]}
        self._requests: Dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Check rate limit before handling event."""
        user_id = self._get_user_id(event)

        if user_id and not self._check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            await self._send_rate_limit_message(event)
            return None

        return await handler(event, data)

    def _get_user_id(self, event: Update) -> int | None:
        """Extract user ID from update."""
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        return None

    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit. Returns True if allowed."""
        current_time = time.time()
        cutoff_time = current_time - self.period

        # Clean old requests
        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > cutoff_time
        ]

        # Check limit
        if len(self._requests[user_id]) >= self.max_requests:
            return False

        # Record this request
        self._requests[user_id].append(current_time)
        return True

    async def _send_rate_limit_message(self, event: Update) -> None:
        """Send rate limit message to user."""
        try:
            message = event.message or (event.callback_query.message if event.callback_query else None)
            if message:
                await message.answer(
                    "Too many requests. Please wait a moment before trying again."
                )
        except Exception:
            pass

    def cleanup(self) -> None:
        """Clean up old request records."""
        current_time = time.time()
        cutoff_time = current_time - self.period

        for user_id in list(self._requests.keys()):
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] if ts > cutoff_time
            ]
            if not self._requests[user_id]:
                del self._requests[user_id]
