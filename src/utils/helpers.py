"""Helper utilities for event processing."""

import hashlib
import re
from typing import Any

from src.config.constants import CATEGORY_KEYWORDS


def parse_polymarket_url(url: str) -> str | None:
    """Extract event slug from Polymarket URL."""
    pattern = r"polymarket\.com/event/([a-zA-Z0-9\-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def matches_keywords(event_data: dict[str, Any], keywords: list[str]) -> bool:
    """
    Check if event matches any of the user's keywords.

    Supports:
    - Simple word matching (case-insensitive)
    - Phrase matching with quotes
    - OR logic (any keyword matches)

    Examples:
    - btc, eth -> matches events with 'btc' OR 'eth'
    - "united states", election -> matches phrase "united states" OR word "election"
    """
    if not keywords:
        return True  # No filters = show all events

    title = event_data.get("title", "").lower()
    markets = event_data.get("markets", [])
    market_text = " ".join([m.get("question", "").lower() for m in markets])
    searchable = f"{title} {market_text}"

    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue

        # Check if it's a phrase (has quotes)
        if (keyword.startswith('"') and keyword.endswith('"')) or (
            keyword.startswith("'") and keyword.endswith("'")
        ):
            # Phrase matching - remove quotes
            phrase = keyword[1:-1].lower()
            if phrase in searchable:
                return True
        else:
            # Simple word matching
            if keyword.lower() in searchable:
                return True

    return False


def matches_category(event_data: dict[str, Any], user_categories: list[str]) -> bool:
    """
    Check if event matches user's category filters.

    Returns True if:
    - User has no category filters (show all)
    - Event matches any of user's selected categories
    """
    if not user_categories:
        return True  # No filters = show all

    title = event_data.get("title", "").lower()
    markets = event_data.get("markets", [])
    market_text = " ".join([m.get("question", "").lower() for m in markets])
    searchable = f"{title} {market_text}"

    for category in user_categories:
        keywords = CATEGORY_KEYWORDS.get(category.lower(), [])
        for keyword in keywords:
            if keyword in searchable:
                return True

    return False


def hash_context(context: str) -> str:
    """
    Create hash of context for comparison.

    Normalizes the text to reduce false positives from minor variations.
    """
    # Normalize: lowercase, remove extra whitespace
    normalized = " ".join(context.lower().split())

    # Remove time references that change frequently
    normalized = re.sub(
        r"\b(today|yesterday|this week|last week|recently|currently)\b", "", normalized
    )

    # Remove common filler words
    normalized = re.sub(r"\b(the|a|an|is|are|was|were|has|have|had|been|being)\b", "", normalized)

    # Keep only first 200 chars for comparison (main content)
    normalized = normalized[:200]

    return hashlib.md5(normalized.encode()).hexdigest()


def get_event_category(event_data: dict[str, Any]) -> str:
    """Determine event's primary category."""
    title = (event_data.get("title", "") or event_data.get("question", "")).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title:
                return category.capitalize()

    return "Other"
