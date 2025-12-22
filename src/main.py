"""Main entry point for Polydictions bot."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api import APIServer
from src.bot import PolydictionsBot
from src.config import get_settings
from src.database import init_db_manager


def setup_logging() -> None:
    """Configure logging."""
    settings = get_settings()

    logging.basicConfig(
        format=settings.log_format,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Reduce noise from libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


async def main() -> None:
    """Main application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    settings = get_settings()
    logger.info("Starting Polydictions v2.0.0")

    # Initialize database
    db = init_db_manager(settings.database_url)
    await db.init_db()
    logger.info("Database initialized")

    # Create bot
    bot = PolydictionsBot(db)

    # Create API server
    api_server = APIServer(db=db, polymarket=bot.polymarket)
    await api_server.start()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await api_server.stop()
        await db.close()
        logger.info("Shutdown complete")


def run() -> None:
    """Run the application."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
