"""Keyword and category filter command handlers."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from pydantic import ValidationError

from src.config.constants import AVAILABLE_CATEGORIES
from src.database import Repository
from src.utils.validators import CategoriesInput, KeywordsInput, parse_keywords

logger = logging.getLogger(__name__)
router = Router(name="filters")


@router.message(Command("keywords"))
async def cmd_keywords(message: Message, repo: Repository) -> None:
    """Handle /keywords command - set keyword filters."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split(maxsplit=1)

    # Show current keywords if no input
    if len(parts) < 2:
        current = await repo.get_user_keywords(user_id)
        if current:
            keywords_text = ", ".join(current)
            help_text = (
                f"<b>Your current keywords:</b>\n{keywords_text}\n\n"
                "<b>How to use:</b>\n"
                "/keywords btc, eth, election - Set keywords\n"
                "/keywords clear - Remove all filters\n\n"
                "<b>Filter options:</b>\n"
                "• Simple words: btc, eth, sports\n"
                "• Phrases: \"united states\", \"world cup\"\n"
                "• OR logic: keywords separated by commas\n\n"
                "<b>Examples:</b>\n"
                "• <code>btc, eth</code> - any event with btc OR eth\n"
                "• <code>\"united states\", election</code> - phrase + word\n"
                "• <code>sports, football, basketball</code> - any sports event\n\n"
                "Only events matching your keywords will be sent!"
            )
        else:
            help_text = (
                "<b>Keyword Filters</b>\n\n"
                "Filter events by keywords to see only what matters!\n\n"
                "<b>How to use:</b>\n"
                "/keywords btc, eth, election - Set keywords\n"
                "/keywords clear - Remove all filters\n\n"
                "<b>Filter options:</b>\n"
                "• Simple words: btc, eth, sports\n"
                "• Phrases: \"united states\", \"world cup\"\n"
                "• OR logic: keywords separated by commas\n\n"
                "<b>Examples:</b>\n"
                "• <code>btc, eth</code> - any event with btc OR eth\n"
                "• <code>\"united states\", election</code> - phrase + word\n"
                "• <code>sports, football, basketball</code> - any sports event\n\n"
                "Currently no filters set - you'll receive all events."
            )

        await message.answer(help_text)
        return

    keyword_input = parts[1].strip()

    # Clear keywords
    if keyword_input.lower() == "clear":
        await repo.clear_user_keywords(user_id)
        await message.answer("All keyword filters removed. You'll receive all events.")
        return

    # Parse and validate keywords
    keywords = parse_keywords(keyword_input)

    try:
        validated = KeywordsInput(keywords=keywords)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        await message.answer(f"Invalid keywords: {error_msg}")
        return

    if not validated.keywords:
        await message.answer("Please provide at least one valid keyword.")
        return

    # Ensure user exists and save keywords
    await repo.get_or_create_user(user_id)
    await repo.set_user_keywords(user_id, validated.keywords)

    keywords_display = "\n".join([f"  • {k}" for k in validated.keywords])
    await message.answer(
        f"<b>Keywords saved!</b>\n\n"
        f"You will only receive events matching:\n{keywords_display}\n\n"
        f"Use /keywords clear to remove filters."
    )
    logger.info(f"User {user_id} set keywords: {validated.keywords}")


@router.message(Command("category"))
async def cmd_category(message: Message, repo: Repository) -> None:
    """Handle /category command - set category filters."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        current_cats = await repo.get_user_categories(user_id)
        all_cats = ", ".join(AVAILABLE_CATEGORIES)

        if current_cats:
            msg = f"<b>Your categories:</b> {', '.join(current_cats)}\n\n"
        else:
            msg = "<b>No category filters set</b>\n\n"

        msg += f"<b>Available categories:</b>\n{all_cats}\n\n"
        msg += "<b>Usage:</b>\n"
        msg += "/category crypto politics\n"
        msg += "/category clear - Remove filters"

        await message.answer(msg)
        return

    categories_input = parts[1].strip()

    # Clear categories
    if categories_input.lower() == "clear":
        await repo.clear_user_categories(user_id)
        await message.answer("Category filters cleared. You'll receive all events.")
        logger.info(f"User {user_id} cleared category filters")
        return

    # Parse and validate
    categories = categories_input.split()

    try:
        validated = CategoriesInput(categories=categories)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        await message.answer(f"Invalid categories: {error_msg}")
        return

    # Ensure user exists and save categories
    await repo.get_or_create_user(user_id)
    await repo.set_user_categories(user_id, validated.categories)

    await message.answer(
        f"<b>Category filters set!</b>\n\n"
        f"You'll only receive events in:\n{', '.join(validated.categories)}"
    )
    logger.info(f"User {user_id} set categories: {validated.categories}")


@router.message(Command("categories"))
async def cmd_categories(message: Message) -> None:
    """Handle /categories command - show all available categories."""
    msg = "<b>Available Categories:</b>\n\n"
    msg += "\n".join([f"• {cat}" for cat in AVAILABLE_CATEGORIES])
    msg += "\n\n<b>Usage:</b>\n/category crypto politics"

    await message.answer(msg)
