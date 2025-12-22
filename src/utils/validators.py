"""Input validators using Pydantic."""

import re
from typing import List

from pydantic import BaseModel, Field, field_validator

from src.config.constants import (
    AVAILABLE_CATEGORIES,
    MAX_KEYWORD_LENGTH,
    MAX_KEYWORDS,
)


class KeywordsInput(BaseModel):
    """Validator for keyword filters input."""

    keywords: List[str] = Field(max_length=MAX_KEYWORDS)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        validated = []
        for keyword in v:
            keyword = keyword.strip()
            if not keyword:
                continue
            if len(keyword) > MAX_KEYWORD_LENGTH:
                raise ValueError(f"Keyword too long (max {MAX_KEYWORD_LENGTH} chars)")
            if len(keyword) < 2:
                raise ValueError("Keyword too short (min 2 chars)")
            # Allow alphanumeric, spaces, quotes, and hyphens
            if not re.match(r'^[\w\s\-"\'\u0400-\u04FF]+$', keyword, re.UNICODE):
                raise ValueError("Invalid characters in keyword")
            validated.append(keyword.lower())
        return validated


class AlertInput(BaseModel):
    """Validator for price alert input."""

    event_slug: str = Field(min_length=3, max_length=200)
    condition: str = Field(pattern=r"^[<>]$")
    threshold: float = Field(ge=0, le=100)
    outcome_index: int = Field(default=0, ge=0)

    @field_validator("event_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip()
        # Allow alphanumeric and hyphens
        if not re.match(r"^[a-zA-Z0-9\-]+$", v):
            raise ValueError("Invalid slug format (use alphanumeric and hyphens only)")
        return v.lower()


class CategoriesInput(BaseModel):
    """Validator for category filters input."""

    categories: List[str]

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: List[str]) -> List[str]:
        validated = []
        for cat in v:
            cat = cat.strip().lower()
            if cat and cat in AVAILABLE_CATEGORIES:
                validated.append(cat)
        if not validated:
            raise ValueError(f"Invalid categories. Available: {', '.join(AVAILABLE_CATEGORIES)}")
        return validated


class IntervalInput(BaseModel):
    """Validator for news update interval."""

    minutes: int = Field(ge=3, le=1440)  # 3 minutes to 24 hours


class WatchInput(BaseModel):
    """Validator for watchlist input."""

    event_slug: str = Field(min_length=3, max_length=200)

    @field_validator("event_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip()
        # Allow alphanumeric and hyphens
        if not re.match(r"^[a-zA-Z0-9\-]+$", v):
            raise ValueError("Invalid slug format")
        return v.lower()


def parse_keywords(input_text: str) -> List[str]:
    """Parse comma-separated keywords, handling quoted phrases."""
    keywords = []
    # Split by comma, but preserve quoted strings
    pattern = r'"[^"]+"|\'[^\']+\'|[^,]+'
    matches = re.findall(pattern, input_text)

    for match in matches:
        keyword = match.strip()
        if keyword:
            keywords.append(keyword)

    return keywords


def validate_polymarket_url(url: str) -> str | None:
    """Validate and extract slug from Polymarket URL."""
    pattern = r"polymarket\.com/event/([a-zA-Z0-9\-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1).lower()

    # Try treating input as slug directly
    url = url.strip()
    if re.match(r"^[a-zA-Z0-9\-]+$", url) and len(url) >= 3:
        return url.lower()

    return None
