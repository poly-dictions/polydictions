"""Bot command handlers."""

from src.bot.handlers.common import router as common_router
from src.bot.handlers.deal import router as deal_router
from src.bot.handlers.watchlist import router as watchlist_router
from src.bot.handlers.alerts import router as alerts_router
from src.bot.handlers.filters import router as filters_router

__all__ = [
    "common_router",
    "deal_router",
    "watchlist_router",
    "alerts_router",
    "filters_router",
]
