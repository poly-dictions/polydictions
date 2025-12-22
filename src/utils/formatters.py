"""Formatting utilities for messages and data."""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def format_money(value: float | int | str | None) -> str:
    """Format money value to readable string."""
    try:
        num = float(value) if value else 0
        return f"${num:,.0f}"
    except (ValueError, TypeError):
        return "$0"


def format_date(date_str: str | None) -> str:
    """Format ISO date string to readable format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except (ValueError, AttributeError):
        return date_str or "N/A"


def _calculate_totals(markets: list[dict[str, Any]]) -> tuple[float, float]:
    """Calculate total liquidity and volume from markets."""
    total_liquidity = 0.0
    total_volume = 0.0

    for market in markets:
        try:
            liquidity = float(market.get("liquidityNum", market.get("liquidity", 0)) or 0)
            total_liquidity += liquidity
        except (ValueError, TypeError):
            pass

        try:
            volume = float(market.get("volumeNum", market.get("volume", 0)) or 0)
            total_volume += volume
        except (ValueError, TypeError):
            pass

    return total_liquidity, total_volume


def _parse_json_field(value: Any) -> list[Any]:
    """Parse JSON field that might be string or already parsed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def format_event(event_data: dict[str, Any]) -> str:
    """Format event data to HTML message for Telegram."""
    try:
        title = event_data.get("title", "Unknown Event")
        slug = event_data.get("slug", "")
        markets = event_data.get("markets", [])

        if not markets:
            return "No market data available"

        # Get totals
        event_liquidity = event_data.get("liquidity")
        event_volume = event_data.get("volume")

        if event_liquidity is not None and event_volume is not None:
            total_liquidity = float(event_liquidity)
            total_volume = float(event_volume)
        else:
            total_liquidity, total_volume = _calculate_totals(markets)

        # Get end date
        end_date = event_data.get("endDate")
        if not end_date and markets:
            end_date = markets[0].get("endDate") or markets[0].get("end_date_iso")
        formatted_date = format_date(end_date)

        # Build message
        lines = [
            f"<b>{title}</b>\n",
            f"<b>Link:</b> https://polymarket.com/event/{slug}\n",
            f"<b>Market stats:</b>",
            f"<b>Closes:</b> {formatted_date}",
            f"<b>Total Liquidity:</b> {format_money(total_liquidity)}",
            f"<b>Total Volume:</b> {format_money(total_volume)}\n",
        ]

        # Format outcomes
        if len(markets) == 1:
            lines.extend(_format_single_market(markets[0]))
        else:
            lines.extend(_format_multiple_markets(markets))

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting event: {e}")
        return "Error formatting event data"


def _format_single_market(market: dict[str, Any]) -> list[str]:
    """Format a single market's outcomes."""
    lines = []
    outcomes = _parse_json_field(market.get("outcomes", []))
    outcome_prices = _parse_json_field(market.get("outcomePrices", []))

    if len(outcomes) == 2:
        lines.append("<b>Current Odds:</b>")
        for idx, outcome in enumerate(outcomes):
            name = outcome.get("name", outcome) if isinstance(outcome, dict) else outcome
            if outcome_prices and idx < len(outcome_prices):
                price = float(outcome_prices[idx])
                percentage = price * 100 if price <= 1 else price
                lines.append(f"  • {name}: {percentage:.1f}%")
    else:
        lines.append("<b>Options:</b>")
        for idx, outcome in enumerate(outcomes):
            name = outcome.get("name", outcome) if isinstance(outcome, dict) else outcome
            if outcome_prices and idx < len(outcome_prices):
                price = float(outcome_prices[idx])
                percentage = price * 100 if price <= 1 else price
                lines.append(f"  {idx + 1}. {name}: {percentage:.1f}%")

    return lines


def _format_multiple_markets(markets: list[dict[str, Any]]) -> list[str]:
    """Format multiple markets."""
    lines = []

    # Filter markets with valid data
    valid_markets = []
    for market in markets:
        market_outcomes = _parse_json_field(market.get("outcomes", []))
        market_prices = _parse_json_field(market.get("outcomePrices", []))
        if market_outcomes and market_prices:
            valid_markets.append(market)

    lines.append(f"<b>Markets ({len(valid_markets)}):</b>")

    for idx, market in enumerate(valid_markets, 1):
        question = market.get("question", f"Market {idx}")
        lines.append(f"  {idx}. {question}")

        market_outcomes = _parse_json_field(market.get("outcomes", []))
        market_prices = _parse_json_field(market.get("outcomePrices", []))

        if market_outcomes and market_prices:
            for o_idx, outcome in enumerate(market_outcomes[:5]):
                o_name = outcome.get("name", outcome) if isinstance(outcome, dict) else outcome
                if o_idx < len(market_prices):
                    o_price = float(market_prices[o_idx])
                    o_percentage = o_price * 100 if o_price <= 1 else o_price
                    lines.append(f"     • {o_name}: {o_percentage:.1f}%")

    return lines
