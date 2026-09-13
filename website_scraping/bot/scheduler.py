import asyncio
import logging
import uuid
from typing import List, Optional
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError

from bot.config import Config
from bot.database import Database
from bot.feed_engine import FeedEngine
from bot.formatters import format_article_markdown_v2

logger = logging.getLogger("scheduler")


class AggregatorScheduler:
    """
    Orchestrates periodic feed polling, deduplication, and subscriber broadcasts.
    """

    def __init__(self, config: Config, db: Database, feed_engine: FeedEngine, bot: Optional[Bot] = None):
        self.config = config
        self.db = db
        self.feed_engine = feed_engine
        self.bot = bot
        self._is_running = False

    def set_bot(self, bot: Bot):
        self.bot = bot

    async def poll_feeds_once(self) -> int:
        """
        Executes one full ingestion cycle across all configured feeds.
        Returns the number of genuinely new articles discovered and stored.
        """
        correlation_id = uuid.uuid4().hex[:8]
        logger.info(f"[{correlation_id}] === Starting scheduled feed ingestion cycle ===")
        total_new_items = []

        for source in self.config.feeds:
            articles, error = self.feed_engine.fetch_source(source, correlation_id)
            if error:
                self.db.record_fetch_metadata(source.name, status="ERROR", error=error)
            else:
                self.db.record_fetch_metadata(source.name, status="OK", items_found=len(articles))
                # Insert batch with deduplication (link UNIQUE)
                newly_inserted = self.db.insert_articles(articles)
                if newly_inserted:
                    logger.info(
                        f"[{correlation_id}] {len(newly_inserted)} new article(s) inserted from {source.name}"
                    )
                    total_new_items.extend(newly_inserted)

            # Polite pacing between feeds to avoid burst traffic
            await asyncio.sleep(1.0)

        logger.info(
            f"[{correlation_id}] Cycle completed. Total fresh articles across all sources: {len(total_new_items)}"
        )

        # Broadcast new articles to active subscribers
        if total_new_items and self.bot:
            await self._broadcast_to_subscribers(total_new_items, correlation_id)

        return len(total_new_items)

    async def _broadcast_to_subscribers(self, new_articles: List[dict], correlation_id: str):
        if not self.bot:
            return

        subscribers = self.db.get_all_subscriptions()
        if not subscribers:
            logger.info(f"[{correlation_id}] No active subscribers to notify.")
            return

        logger.info(
            f"[{correlation_id}] Broadcasting {len(new_articles)} new articles to {len(subscribers)} subscriber(s)..."
        )

        # Limit broadcast batch to the 5 most recent articles to avoid flooding chats
        articles_to_send = new_articles[:5]

        for chat_id in subscribers:
            for article in articles_to_send:
                formatted_text = format_article_markdown_v2(article)
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=formatted_text,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=False,
                    )
                    # Comply with Telegram's broadcast rate limits (~30 msgs/sec globally)
                    await asyncio.sleep(0.1)

                except RetryAfter as e:
                    delay_seconds = float(e.retry_after) if isinstance(e.retry_after, (int, float)) else 5.0
                    logger.warning(f"[{correlation_id}] Telegram rate limit. Sleeping {delay_seconds}s...")
                    await asyncio.sleep(delay_seconds)
                    # Retry once
                    try:
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=formatted_text,
                            parse_mode=ParseMode.MARKDOWN_V2,
                        )
                    except Exception as retry_err:
                        logger.error(f"[{correlation_id}] Failed delivery to {chat_id} after backoff: {retry_err}")

                except Forbidden:
                    # Bot was blocked by user or removed from chat; prune subscription
                    logger.info(f"[{correlation_id}] Chat {chat_id} blocked the bot; removing subscription.")
                    self.db.remove_subscription(chat_id)
                    break

                except TelegramError as tg_err:
                    logger.error(f"[{correlation_id}] Telegram delivery error for chat {chat_id}: {tg_err}")

    async def start_periodic_loop(self):
        """Asynchronous scheduler loop running at FETCH_INTERVAL_MIN intervals."""
        self._is_running = True
        logger.info(
            f"Background feed poller activated (interval: {self.config.fetch_interval_min} minutes)."
        )

        # 1. Run once immediately on startup
        try:
            await self.poll_feeds_once()
        except Exception as e:
            logger.error(f"Initial feed fetch cycle encountered error: {e}", exc_info=True)

        # 2. Continuous loop
        interval_seconds = self.config.fetch_interval_min * 60
        while self._is_running:
            try:
                await asyncio.sleep(interval_seconds)
                if self._is_running:
                    await self.poll_feeds_once()
            except asyncio.CancelledError:
                logger.info("Aggregator scheduler loop received cancellation.")
                break
            except Exception as loop_err:
                logger.error(f"Unexpected error in scheduler loop: {loop_err}", exc_info=True)

    def stop(self):
        self._is_running = False
