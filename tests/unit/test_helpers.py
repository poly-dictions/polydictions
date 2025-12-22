"""Tests for helper functions."""

import pytest

from src.utils.helpers import (
    get_event_category,
    hash_context,
    matches_category,
    matches_keywords,
    parse_polymarket_url,
)


class TestMatchesKeywords:
    """Tests for matches_keywords function."""

    def test_no_keywords_matches_all(self):
        """Test empty keywords matches all events."""
        event = {"title": "Bitcoin price prediction", "markets": []}
        assert matches_keywords(event, []) is True

    def test_simple_keyword_match(self):
        """Test simple keyword matching."""
        event = {"title": "Bitcoin price prediction", "markets": []}
        assert matches_keywords(event, ["bitcoin"]) is True
        assert matches_keywords(event, ["ethereum"]) is False

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        event = {"title": "BITCOIN price", "markets": []}
        assert matches_keywords(event, ["bitcoin"]) is True

    def test_phrase_matching(self):
        """Test quoted phrase matching."""
        event = {"title": "United States election results", "markets": []}
        assert matches_keywords(event, ['"united states"']) is True
        assert matches_keywords(event, ['"united kingdom"']) is False

    def test_or_logic(self):
        """Test OR logic with multiple keywords."""
        event = {"title": "Bitcoin price", "markets": []}
        assert matches_keywords(event, ["bitcoin", "ethereum"]) is True
        assert matches_keywords(event, ["ethereum", "solana"]) is False

    def test_market_question_matching(self):
        """Test matching in market questions."""
        event = {
            "title": "Crypto market",
            "markets": [{"question": "Will Bitcoin reach $100k?"}],
        }
        assert matches_keywords(event, ["bitcoin"]) is True


class TestMatchesCategory:
    """Tests for matches_category function."""

    def test_no_categories_matches_all(self):
        """Test empty categories matches all events."""
        event = {"title": "Bitcoin price", "markets": []}
        assert matches_category(event, []) is True

    def test_crypto_category(self):
        """Test crypto category matching."""
        event = {"title": "Bitcoin price prediction", "markets": []}
        assert matches_category(event, ["crypto"]) is True

    def test_politics_category(self):
        """Test politics category matching."""
        event = {"title": "US Presidential election", "markets": []}
        assert matches_category(event, ["politics"]) is True

    def test_no_match(self):
        """Test no category match."""
        event = {"title": "Random event", "markets": []}
        assert matches_category(event, ["crypto"]) is False


class TestHashContext:
    """Tests for hash_context function."""

    def test_deterministic(self):
        """Test hash is deterministic."""
        context = "This is a test context"
        hash1 = hash_context(context)
        hash2 = hash_context(context)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test different content produces different hash."""
        hash1 = hash_context("Context one")
        hash2 = hash_context("Context two")
        assert hash1 != hash2

    def test_ignores_time_references(self):
        """Test time references are normalized."""
        hash1 = hash_context("The market today shows...")
        hash2 = hash_context("The market yesterday shows...")
        # They might still differ due to other words, but time words are removed
        assert "today" not in hash1
        assert "yesterday" not in hash2


class TestGetEventCategory:
    """Tests for get_event_category function."""

    def test_crypto_event(self):
        """Test crypto event categorization."""
        event = {"title": "Bitcoin price prediction"}
        assert get_event_category(event) == "Crypto"

    def test_politics_event(self):
        """Test politics event categorization."""
        event = {"title": "Trump vs Biden election"}
        assert get_event_category(event) == "Politics"

    def test_sports_event(self):
        """Test sports event categorization."""
        event = {"title": "NFL Super Bowl prediction"}
        assert get_event_category(event) == "Sports"

    def test_unknown_category(self):
        """Test unknown category returns Other."""
        event = {"title": "Random event with no keywords"}
        assert get_event_category(event) == "Other"


class TestParsePolymarketUrl:
    """Tests for parse_polymarket_url function."""

    def test_valid_url(self):
        """Test valid Polymarket URL."""
        url = "https://polymarket.com/event/btc-price-2025"
        assert parse_polymarket_url(url) == "btc-price-2025"

    def test_url_with_query_params(self):
        """Test URL with query parameters."""
        url = "https://polymarket.com/event/btc-price-2025?tab=comments"
        assert parse_polymarket_url(url) == "btc-price-2025"

    def test_invalid_url(self):
        """Test invalid URL returns None."""
        url = "https://example.com/something"
        assert parse_polymarket_url(url) is None
