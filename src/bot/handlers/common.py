"""Common bot handlers (start, help, pause, resume)."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.database import Repository

logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message, repo: Repository) -> None:
    """Handle /start command - subscribe user."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    _, created = await repo.get_or_create_user(user_id)

    text = (
        "<b>Welcome to Polydictions Bot</b>\n\n"
        "Track and analyze Polymarket events.\n\n"
        "<b>Main Commands:</b>\n"
        "/deal &lt;link&gt; - Analyze event\n"
        "/start - Subscribe to notifications\n"
        "/pause - Pause notifications\n"
        "/resume - Resume notifications\n\n"
        "<b>Filters:</b>\n"
        "/keywords - Filter by keywords\n"
        "/category - Filter by category\n"
        "/categories - Show all categories\n\n"
        "<b>Watchlist:</b>\n"
        "/watch &lt;slug&gt; - Add to watchlist\n"
        "/watchlist - Show watchlist\n"
        "/unwatch &lt;slug&gt; - Remove from watchlist\n\n"
        "<b>Price Alerts:</b>\n"
        "/alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
        "/alerts - Show alerts\n"
        "/rmalert &lt;#&gt; - Remove alert\n\n"
    )

    if created:
        text += "You're now subscribed to new events!\n"
        logger.info(f"New user subscribed: {user_id}")
    else:
        text += "Welcome back!\n"

    text += "Use /help for more info"
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    text = (
        "<b>Polydictions Bot</b>\n\n"
        "<b>Main Commands:</b>\n"
        "/deal &lt;link&gt; - Analyze event with Market Context\n"
        "/start - Subscribe to notifications\n"
        "/pause - Pause notifications\n"
        "/resume - Resume notifications\n\n"
        "<b>Filters:</b>\n"
        "/keywords - Filter by keywords\n"
        "/category - Filter by category (crypto, politics, sports)\n"
        "/categories - Show all categories\n\n"
        "<b>Watchlist:</b>\n"
        "/watch &lt;slug&gt; - Add to watchlist\n"
        "/watchlist - Show watchlist\n"
        "/unwatch &lt;slug&gt; - Remove from watchlist\n"
        "/interval &lt;min&gt; - Set update interval\n\n"
        "<b>Price Alerts:</b>\n"
        "/alert &lt;slug&gt; &gt; &lt;%&gt; - Set alert\n"
        "/alerts - Show alerts\n"
        "/rmalert &lt;#&gt; - Remove alert\n\n"
        "<b>Features:</b>\n"
        "• AI-powered Market Context\n"
        "• Event statistics & odds\n"
        "• Price alerts\n"
        "• Watchlist tracking\n"
        "• Smart filtering"
    )
    await message.answer(text)


@router.message(Command("pause"))
async def cmd_pause(message: Message, repo: Repository) -> None:
    """Handle /pause command - pause notifications."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user = await repo.get_user(user_id)

    if not user:
        await message.answer("You're not subscribed. Use /start to subscribe.")
        return

    if user.is_paused:
        await message.answer("You're already paused. Use /resume to resume notifications.")
        return

    await repo.set_user_paused(user_id, True)
    await message.answer(
        "<b>Notifications paused</b>\n\n"
        "You won't receive any new event notifications.\n\n"
        "Use /resume when you want to resume notifications."
    )
    logger.info(f"User {user_id} paused notifications")


@router.message(Command("resume"))
async def cmd_resume(message: Message, repo: Repository) -> None:
    """Handle /resume command - resume notifications."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user = await repo.get_user(user_id)

    if not user:
        await message.answer("You're not subscribed. Use /start to subscribe.")
        return

    if not user.is_paused:
        await message.answer("You're not paused. Notifications are already active!")
        return

    await repo.set_user_paused(user_id, False)

    keywords = await repo.get_user_keywords(user_id)
    keywords_info = ""
    if keywords:
        keywords_info = f"\n\nActive filters: {', '.join(keywords)}"

    await message.answer(
        f"<b>Notifications resumed</b>\n\n"
        f"You'll receive new event notifications again!{keywords_info}"
    )
    logger.info(f"User {user_id} resumed notifications")
