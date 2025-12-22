"""Error handling middleware for aiogram."""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)


class ErrorsMiddleware(BaseMiddleware):
    """Middleware for handling errors in bot handlers."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Handle errors during event processing."""
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Error handling update: {e}",
                exc_info=True,
                extra={
                    "update_id": event.update_id,
                    "user_id": self._get_user_id(event),
                },
            )

            # Try to send error message to user
            await self._send_error_message(event)

            return None

    def _get_user_id(self, event: Update) -> int | None:
        """Extract user ID from update."""
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        return None

    async def _send_error_message(self, event: Update) -> None:
        """Send error message to user."""
        try:
            message = event.message or (event.callback_query.message if event.callback_query else None)
            if message:
                await message.answer(
                    "An error occurred while processing your request. Please try again later."
                )
        except Exception:
            # Ignore errors when trying to send error message
            pass
