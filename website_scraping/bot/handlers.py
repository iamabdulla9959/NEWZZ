import logging
from typing import Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import Config
from bot.database import Database
from bot.formatters import escape_markdown_v2, format_article_markdown_v2

logger = logging.getLogger("handlers")

# In-memory session tracking for users currently awaiting a search query: {chat_id: True}
AWAITING_SEARCH: Dict[int, bool] = {}


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Constructs the root inline navigation keyboard."""
    keyboard = [
        [InlineKeyboardButton("📰 Latest Headlines", callback_data="menu_latest")],
        [InlineKeyboardButton("🌐 Browse by Source", callback_data="menu_by_source")],
        [InlineKeyboardButton("🔍 Search Articles", callback_data="menu_search")],
        [
            InlineKeyboardButton("🔔 Subscribe", callback_data="menu_subscribe"),
            InlineKeyboardButton("🔕 Unsubscribe", callback_data="menu_unsubscribe"),
        ],
        [InlineKeyboardButton("📊 Telemetry & Stats", callback_data="menu_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_back_button(target: str = "menu_main", label: str = "⬅️ Back to Main Menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=target)]])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrypoint /start command showing the main inline menu."""
    text = (
        "🤖 *Welcome to NewsScraperBot*\n\n"
        "A compliant, syndication\\-driven news aggregator consuming official RSS/Atom feeds\\.\n\n"
        "Select an option below to browse or search live reporting:"
    )
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    elif update.callback_query and isinstance(update.callback_query.message, Message):
        await update.callback_query.edit_message_text(
            text,
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def menu_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central callback query router for all inline buttons."""
    query = update.callback_query
    if not query or not isinstance(query.message, Message):
        return

    await query.answer()
    data = query.data or ""
    db: Database = context.bot_data["db"]
    config: Config = context.bot_data["config"]
    message = query.message
    chat_id = message.chat_id

    # Reset any pending search state when navigating menu buttons
    AWAITING_SEARCH[chat_id] = False

    if data == "menu_main":
        await start_command(update, context)

    elif data == "menu_latest":
        articles = db.get_latest_articles(limit=5)
        if not articles:
            await query.edit_message_text(
                "📭 _No articles cached yet\\. The background engine is currently syncing feeds\\._",
                reply_markup=build_back_button(),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        await message.reply_text(
            f"📰 *Latest {len(articles)} Headlines across all sources:*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        for art in articles:
            await message.reply_text(
                format_article_markdown_v2(art),
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=False,
            )
        await message.reply_text(
            "Navigation:",
            reply_markup=build_back_button(),
        )

    elif data == "menu_by_source":
        # Render submenu listing all configured publishers
        buttons = []
        for s in config.feeds:
            buttons.append([InlineKeyboardButton(f"📰 {s.name}", callback_data=f"src:{s.name}")])
        buttons.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")])

        await query.edit_message_text(
            "🌐 *Select a News Publisher:*",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    elif data.startswith("src:"):
        source_name = data[4:]
        articles = db.get_latest_articles(limit=5, source=source_name)
        esc_source = escape_markdown_v2(source_name)

        if not articles:
            await query.edit_message_text(
                f"📭 _No recent articles found for {esc_source}\\._",
                reply_markup=build_back_button(target="menu_by_source", label="⬅️ Back to Sources"),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        await message.reply_text(
            f"🌐 *Top Headlines from {esc_source}:*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        for art in articles:
            await message.reply_text(
                format_article_markdown_v2(art),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        await message.reply_text(
            "Navigation:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Sources", callback_data="menu_by_source")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
        )

    elif data == "menu_search":
        AWAITING_SEARCH[chat_id] = True
        await query.edit_message_text(
            "🔍 *Search News Database*\n\n"
            "Please send a keyword or phrase in your next message to search article titles and summaries\\.\n\n"
            "_Example: quantum, election, climate, inflation_",
            reply_markup=build_back_button(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    elif data == "menu_subscribe":
        newly_added = db.add_subscription(chat_id)
        if newly_added:
            text = "🔔 *Subscribed\\!*\n\nYou will now automatically receive push notifications when new articles are syndicated \\(every 15 min\\)\\."
        else:
            text = "ℹ️ *You are already subscribed to periodic news alerts\\.*"

        await query.edit_message_text(
            text,
            reply_markup=build_back_button(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    elif data == "menu_unsubscribe":
        removed = db.remove_subscription(chat_id)
        if removed:
            text = "🔕 *Unsubscribed\\.*\n\nYou will no longer receive periodic news push notifications\\."
        else:
            text = "ℹ️ *You are not currently subscribed\\.*"

        await query.edit_message_text(
            text,
            reply_markup=build_back_button(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    elif data == "menu_stats":
        stats = db.get_stats()
        esc_total = escape_markdown_v2(str(stats["total_articles"]))
        esc_subs = escape_markdown_v2(str(stats["active_subscriptions"]))

        source_lines = []
        for src, count in stats["source_counts"].items():
            meta = stats["metadata"].get(src, {})
            last_dt = meta.get("last_fetched", "Never")
            source_lines.append(
                f"• *{escape_markdown_v2(src)}*: {count} articles \\(last: {escape_markdown_v2(last_dt)}\\)"
            )

        sources_block = "\n".join(source_lines) if source_lines else "_No sources fetched yet\\._"

        report = (
            "📊 *NewsScraperBot Telemetry & Health*\n\n"
            f"• *Total Ingested Articles*: {esc_total}\n"
            f"• *Active Chat Subscriptions*: {esc_subs}\n\n"
            "*Source Breakdown:*\n"
            f"{sources_block}\n\n"
            "• *Sync Frequency*: Every 15 minutes\n"
            "• *Data Engine*: Syndicated RSS/Atom \\(no raw HTML scraping\\)"
        )

        await query.edit_message_text(
            report,
            reply_markup=build_back_button(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages, routing them to search if user clicked [Search]."""
    if not update.effective_chat or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    if not AWAITING_SEARCH.get(chat_id, False):
        # User sent free text without asking for search; gently redirect to menu
        await update.message.reply_text(
            "ℹ️ Please use the menu buttons below to interact with the bot:",
            reply_markup=build_main_menu_keyboard(),
        )
        return

    # Clear awaiting search flag
    AWAITING_SEARCH[chat_id] = False
    query_text = update.message.text.strip()
    db: Database = context.bot_data["db"]

    results = db.search_articles(query_text, limit=5)
    esc_q = escape_markdown_v2(query_text)

    if not results:
        await update.message.reply_text(
            f"🔍 No articles matched your search for *'{esc_q}'*\\.\n\nTry a broader query or browse by publisher\\.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Try Another Search", callback_data="menu_search")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await update.message.reply_text(
        f"🔍 Found {len(results)} matching article\\(s\\) for *'{esc_q}'*:",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    for art in results:
        await update.message.reply_text(
            format_article_markdown_v2(art),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    await update.message.reply_text(
        "Navigation:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Search Again", callback_data="menu_search")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]),
    )


def register_handlers(app):
    """Attaches all Telegram handlers to the Application."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(menu_callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
