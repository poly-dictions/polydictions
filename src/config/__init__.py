"""Configuration module with Pydantic Settings."""

from src.config.settings import Settings, get_settings
from src.config.constants import CATEGORY_KEYWORDS, AVAILABLE_CATEGORIES

__all__ = [
    "Settings",
    "get_settings",
    "CATEGORY_KEYWORDS",
    "AVAILABLE_CATEGORIES",
]
