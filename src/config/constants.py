"""Application constants and category definitions."""

from typing import Final

# Category keywords mapping
CATEGORY_KEYWORDS: Final[dict[str, list[str]]] = {
    "crypto": [
        "btc",
        "bitcoin",
        "eth",
        "ethereum",
        "crypto",
        "solana",
        "xrp",
        "blockchain",
        "defi",
        "nft",
        "token",
        "coin",
        "doge",
        "bnb",
        "ada",
        "dot",
    ],
    "politics": [
        "election",
        "president",
        "senate",
        "congress",
        "vote",
        "trump",
        "biden",
        "political",
        "government",
        "democrat",
        "republican",
        "governor",
    ],
    "sports": [
        "nfl",
        "nba",
        "mlb",
        "nhl",
        "football",
        "basketball",
        "baseball",
        "hockey",
        "soccer",
        "vs.",
        "vs",
        "game",
        "match",
        "championship",
        "super bowl",
        "ufc",
        "boxing",
    ],
    "finance": [
        "stock",
        "market",
        "fed",
        "rate",
        "inflation",
        "gdp",
        "economy",
        "treasury",
        "dollar",
        "recession",
        "s&p",
        "nasdaq",
        "dow",
    ],
    "tech": [
        "ai",
        "apple",
        "google",
        "meta",
        "tesla",
        "microsoft",
        "amazon",
        "tech",
        "software",
        "app",
        "nvidia",
        "openai",
    ],
    "entertainment": [
        "movie",
        "oscar",
        "grammy",
        "emmy",
        "celebrity",
        "actor",
        "music",
        "album",
        "box office",
    ],
}

AVAILABLE_CATEGORIES: Final[list[str]] = list(CATEGORY_KEYWORDS.keys())

# Minimum interval for news updates (seconds)
MIN_NEWS_INTERVAL: Final[int] = 180  # 3 minutes

# Default interval for news updates (seconds)
DEFAULT_NEWS_INTERVAL: Final[int] = 300  # 5 minutes

# Maximum watchlist items per user
MAX_WATCHLIST_ITEMS: Final[int] = 50

# Maximum keywords per user
MAX_KEYWORDS: Final[int] = 20

# Maximum keyword length
MAX_KEYWORD_LENGTH: Final[int] = 50

# Maximum alerts per user
MAX_ALERTS_PER_USER: Final[int] = 20

# Posted events to keep for Chrome extension sync
MAX_POSTED_EVENTS: Final[int] = 50
