"""Deal command handler for analyzing events."""

import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.services.polymarket import PolymarketService
from src.utils.formatters import format_event
from src.utils.validators import validate_polymarket_url

logger = logging.getLogger(__name__)
router = Router(name="deal")


class DealStates(StatesGroup):
    """States for deal command flow."""

    waiting_for_link = State()


@router.message(Command("deal"))
async def cmd_deal(
    message: Message,
    state: FSMContext,
    polymarket: PolymarketService,
) -> None:
    """Handle /deal command - analyze event."""
    if not message.from_user:
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "<b>Send me a Polymarket link</b>\n\n"
            "Example:\nhttps://polymarket.com/event/your-event-slug"
        )
        await state.set_state(DealStates.waiting_for_link)
        return

    url = parts[1].strip()
    await _process_deal(message, url, polymarket)


@router.message(StateFilter(DealStates.waiting_for_link))
async def handle_deal_link(
    message: Message,
    state: FSMContext,
    polymarket: PolymarketService,
) -> None:
    """Handle link sent after /deal command."""
    await state.clear()

    if not message.text:
        await message.answer("Please send a valid Polymarket URL.")
        return

    await _process_deal(message, message.text.strip(), polymarket)


async def _process_deal(
    message: Message,
    url_or_slug: str,
    polymarket: PolymarketService,
) -> None:
    """Process event analysis."""
    slug = validate_polymarket_url(url_or_slug)

    if not slug:
        await message.answer(
            "Invalid link. Please send a valid Polymarket URL.\n\n"
            "Example: https://polymarket.com/event/your-event-slug"
        )
        return

    processing = await message.answer("Fetching event data...")

    try:
        event_data = await polymarket.fetch_event_by_slug(slug)

        if not event_data:
            await processing.edit_text("Event not found")
            return

        # Send basic info first
        basic_msg = format_event(event_data)
        await processing.edit_text(basic_msg)

        # Fetch Market Context
        context_msg = await message.answer("Generating Market Context... (this may take 10-30 seconds)")

        event_slug = event_data.get("slug", "")
        market_context = await polymarket.fetch_market_context(event_slug)

        if market_context:
            await _send_context(context_msg, message, market_context)
        else:
            await context_msg.edit_text(
                "Market Context generation failed.\n\n"
                "This can happen if:\n"
                "• The event is too new\n"
                "• The API is temporarily unavailable\n"
                "• The event doesn't have enough data"
            )

        logger.info(f"User {message.from_user.id if message.from_user else 'N/A'} checked event: {slug}")

    except Exception as e:
        logger.error(f"Error in /deal: {e}")
        await processing.edit_text(f"Error: {str(e)}")


async def _send_context(
    context_msg: Any,
    message: Message,
    market_context: str,
) -> None:
    """Send market context, splitting if necessary."""
    context_text = f"<b>Market Context:</b>\n\n{market_context}"

    if len(context_text) <= 4000:
        await context_msg.edit_text(context_text)
        return

    # Split into chunks
    await context_msg.edit_text("<b>Market Context:</b>\n\n(Message too long, sending in parts...)")
    chunks = [market_context[i : i + 3900] for i in range(0, len(market_context), 3900)]

    for idx, chunk in enumerate(chunks):
        if idx == 0:
            await context_msg.edit_text(f"<b>Market Context (Part {idx + 1}):</b>\n\n{chunk}")
        else:
            await message.answer(f"<b>Market Context (Part {idx + 1}):</b>\n\n{chunk}")
