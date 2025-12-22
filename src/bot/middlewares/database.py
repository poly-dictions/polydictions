"""Database middleware for providing repository access in handlers."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from src.database import DatabaseManager, Repository


class DatabaseMiddleware(BaseMiddleware):
    """Middleware for injecting database repository into handler data."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Inject repository into handler data."""
        async with self.db.session() as session:
            repo = Repository(session)
            data["repo"] = repo
            data["db"] = self.db
            return await handler(event, data)
