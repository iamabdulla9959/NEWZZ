import asyncio
import logging
import os
import sys
from telegram.ext import Application

from bot.config import load_config
from bot.database import Database
from bot.feed_engine import FeedEngine
from bot.handlers import register_handlers
from bot.scheduler import AggregatorScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


async def post_init_callback(application: Application):
    """Called after application initialization to attach the bot to the scheduler and start polling."""
    scheduler: AggregatorScheduler = application.bot_data["scheduler"]
    scheduler.set_bot(application.bot)
    # Start the periodic background feed poller
    asyncio.create_task(scheduler.start_periodic_loop())
    logger.info("Background feed poller task launched in asyncio loop.")


def main():
    config = load_config()

    if not config.telegram_bot_token or config.telegram_bot_token.startswith("YOUR_"):
        logger.error(
            "CRITICAL: TELEGRAM_BOT_TOKEN is not set or contains placeholder.\n"
            "Please provide a valid bot token from @BotFather via the TELEGRAM_BOT_TOKEN environment variable.\n"
            "Example:\n"
            "  export TELEGRAM_BOT_TOKEN='123456789:ABCdefGHIjklMNOpqrsTUVwxyz'\n"
            "  python main.py"
        )
        sys.exit(1)

    logger.info(f"Initializing SQLite database at '{config.db_path}' ...")
    db = Database(config.db_path)

    logger.info(f"Configuring FeedEngine with User-Agent: {config.user_agent}")
    feed_engine = FeedEngine(
        user_agent=config.user_agent,
        timeout_seconds=config.request_timeout_seconds,
    )

    scheduler = AggregatorScheduler(
        config=config,
        db=db,
        feed_engine=feed_engine,
    )

    logger.info("Building Telegram Application...")
    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(post_init_callback)
        .build()
    )

    # Store references in bot_data for handlers
    application.bot_data["config"] = config
    application.bot_data["db"] = db
    application.bot_data["scheduler"] = scheduler

    register_handlers(application)

    logger.info("Starting Telegram Bot polling (Press Ctrl+C to terminate)...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
