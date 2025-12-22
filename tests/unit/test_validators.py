"""Tests for input validators."""

import pytest
from pydantic import ValidationError

from src.utils.validators import (
    AlertInput,
    CategoriesInput,
    IntervalInput,
    KeywordsInput,
    WatchInput,
    parse_keywords,
    validate_polymarket_url,
)


class TestKeywordsInput:
    """Tests for KeywordsInput validator."""

    def test_valid_keywords(self):
        """Test valid keyword input."""
        result = KeywordsInput(keywords=["btc", "eth", "crypto"])
        assert len(result.keywords) == 3
        assert "btc" in result.keywords

    def test_keywords_lowercased(self):
        """Test keywords are lowercased."""
        result = KeywordsInput(keywords=["BTC", "ETH"])
        assert result.keywords == ["btc", "eth"]

    def test_empty_keywords_filtered(self):
        """Test empty keywords are filtered."""
        result = KeywordsInput(keywords=["btc", "", "  ", "eth"])
        assert result.keywords == ["btc", "eth"]

    def test_keyword_too_short(self):
        """Test keyword too short validation."""
        with pytest.raises(ValidationError):
            KeywordsInput(keywords=["a"])

    def test_keyword_too_long(self):
        """Test keyword too long validation."""
        with pytest.raises(ValidationError):
            KeywordsInput(keywords=["a" * 100])


class TestAlertInput:
    """Tests for AlertInput validator."""

    def test_valid_alert(self):
        """Test valid alert input."""
        result = AlertInput(
            event_slug="btc-price-2025",
            condition=">",
            threshold=70.0,
        )
        assert result.event_slug == "btc-price-2025"
        assert result.condition == ">"
        assert result.threshold == 70.0

    def test_invalid_condition(self):
        """Test invalid condition."""
        with pytest.raises(ValidationError):
            AlertInput(event_slug="test", condition="=", threshold=50)

    def test_threshold_out_of_range(self):
        """Test threshold validation."""
        with pytest.raises(ValidationError):
            AlertInput(event_slug="test", condition=">", threshold=150)

    def test_invalid_slug_format(self):
        """Test slug format validation."""
        with pytest.raises(ValidationError):
            AlertInput(event_slug="test/invalid", condition=">", threshold=50)


class TestCategoriesInput:
    """Tests for CategoriesInput validator."""

    def test_valid_categories(self):
        """Test valid categories."""
        result = CategoriesInput(categories=["crypto", "politics"])
        assert len(result.categories) == 2

    def test_invalid_category(self):
        """Test invalid category rejected."""
        with pytest.raises(ValidationError):
            CategoriesInput(categories=["invalid_category"])

    def test_mixed_valid_invalid(self):
        """Test mixed categories - only valid kept."""
        result = CategoriesInput(categories=["crypto", "invalid", "sports"])
        assert result.categories == ["crypto", "sports"]


class TestIntervalInput:
    """Tests for IntervalInput validator."""

    def test_valid_interval(self):
        """Test valid interval."""
        result = IntervalInput(minutes=5)
        assert result.minutes == 5

    def test_minimum_interval(self):
        """Test minimum interval validation."""
        with pytest.raises(ValidationError):
            IntervalInput(minutes=2)

    def test_maximum_interval(self):
        """Test maximum interval validation."""
        with pytest.raises(ValidationError):
            IntervalInput(minutes=2000)


class TestWatchInput:
    """Tests for WatchInput validator."""

    def test_valid_slug(self):
        """Test valid slug."""
        result = WatchInput(event_slug="btc-price-2025")
        assert result.event_slug == "btc-price-2025"

    def test_slug_lowercased(self):
        """Test slug lowercased."""
        result = WatchInput(event_slug="BTC-PRICE-2025")
        assert result.event_slug == "btc-price-2025"


class TestParseKeywords:
    """Tests for parse_keywords function."""

    def test_simple_keywords(self):
        """Test parsing simple keywords."""
        result = parse_keywords("btc, eth, crypto")
        assert len(result) == 3

    def test_quoted_phrases(self):
        """Test parsing quoted phrases."""
        result = parse_keywords('"united states", election')
        assert '"united states"' in result
        assert "election" in result


class TestValidatePolymarketUrl:
    """Tests for validate_polymarket_url function."""

    def test_full_url(self):
        """Test full Polymarket URL."""
        result = validate_polymarket_url("https://polymarket.com/event/btc-price-2025")
        assert result == "btc-price-2025"

    def test_slug_only(self):
        """Test slug input."""
        result = validate_polymarket_url("btc-price-2025")
        assert result == "btc-price-2025"

    def test_invalid_url(self):
        """Test invalid URL."""
        result = validate_polymarket_url("https://example.com/test")
        assert result is None

    def test_too_short(self):
        """Test too short input."""
        result = validate_polymarket_url("ab")
        assert result is None
