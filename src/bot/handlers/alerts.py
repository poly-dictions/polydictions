"""Price alert command handlers."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from pydantic import ValidationError

from src.database import Repository
from src.utils.validators import AlertInput

logger = logging.getLogger(__name__)
router = Router(name="alerts")


@router.message(Command("alert"))
async def cmd_alert(message: Message, repo: Repository) -> None:
    """Handle /alert command - set price alert."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split()

    if len(parts) < 4:
        await message.answer(
            "Invalid format.\n\n"
            "<b>Usage:</b>\n"
            "/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;\n"
            "/alert &lt;event-slug&gt; &lt; &lt;threshold&gt;\n\n"
            "<b>Examples:</b>\n"
            "/alert btc-price-2025 &gt; 70\n"
            "/alert election-winner &lt; 30"
        )
        return

    try:
        validated = AlertInput(
            event_slug=parts[1],
            condition=parts[2],
            threshold=float(parts[3]),
        )
    except ValueError:
        await message.answer("Threshold must be a number between 0 and 100")
        return
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        await message.answer(f"Invalid input: {error_msg}")
        return

    # Ensure user exists
    await repo.get_or_create_user(user_id)

    if await repo.add_alert(
        user_id,
        validated.event_slug,
        validated.condition,
        validated.threshold,
        validated.outcome_index,
    ):
        await message.answer(
            f"<b>Alert set!</b>\n\n"
            f"Event: {validated.event_slug}\n"
            f"Condition: {validated.condition} {validated.threshold}%\n\n"
            f"You'll be notified when the price crosses this threshold."
        )
        logger.info(
            f"User {user_id} set alert: {validated.event_slug} "
            f"{validated.condition} {validated.threshold}%"
        )
    else:
        await message.answer("This alert already exists.")


@router.message(Command("alerts"))
async def cmd_alerts(message: Message, repo: Repository) -> None:
    """Handle /alerts command - show user's alerts."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    alerts = await repo.get_user_alerts(user_id)

    if not alerts:
        await message.answer(
            "<b>No alerts set</b>\n\n"
            "Set alerts with:\n/alert &lt;event-slug&gt; &gt; &lt;threshold&gt;"
        )
        return

    lines = ["<b>Your Price Alerts:</b>\n"]
    for idx, alert in enumerate(alerts):
        status = "Triggered" if alert.is_triggered else "Active"
        lines.append(f"{idx + 1}. {alert.event_slug}")
        lines.append(f"   {alert.condition} {alert.threshold}% - {status}\n")

    lines.append(f"\n<b>Total:</b> {len(alerts)} alerts")
    lines.append("\nUse /rmalert &lt;number&gt; to remove")

    await message.answer("\n".join(lines))


@router.message(Command("rmalert"))
async def cmd_rmalert(message: Message, repo: Repository) -> None:
    """Handle /rmalert command - remove price alert."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split()

    if len(parts) < 2:
        await message.answer(
            "Please provide alert number.\n\nExample:\n/rmalert 1"
        )
        return

    try:
        index = int(parts[1]) - 1  # Convert to 0-based index
    except ValueError:
        await message.answer("Invalid number")
        return

    if await repo.remove_alert(user_id, index):
        await message.answer("Alert removed!")
        logger.info(f"User {user_id} removed alert {index + 1}")
    else:
        await message.answer("Alert not found.")
