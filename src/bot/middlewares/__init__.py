"""Bot middlewares."""

from src.bot.middlewares.errors import ErrorsMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.database import DatabaseMiddleware

__all__ = ["ErrorsMiddleware", "RateLimitMiddleware", "DatabaseMiddleware"]
