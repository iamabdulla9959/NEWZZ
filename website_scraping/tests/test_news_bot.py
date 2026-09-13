import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from bot.config import Config, FeedSource, load_config
from bot.database import Database
from bot.feed_engine import FeedEngine
from bot.formatters import (
    escape_markdown_v2,
    escape_markdown_v2_url,
    format_article_markdown_v2,
    strip_html,
)


# ────────────────────────────────────────────────────────
# 1. FORMATTER & MARKDOWN-V2 TESTS
# ────────────────────────────────────────────────────────

def test_strip_html():
    raw = "<p>This is <b>bold</b> &amp; <i>italic</i> news.<br><a href='http://x.com'>Link</a></p>"
    clean = strip_html(raw)
    assert "<" not in clean
    assert ">" not in clean
    assert "This is bold & italic news. Link" == clean


def test_escape_markdown_v2():
    raw = "Breaking: Oil hits $100! (Dow -2.5% [Market Crash]) _test_ *bold* ~strike~"
    escaped = escape_markdown_v2(raw)
    # Check that punctuation is escaped with backslash
    for char in ["!", "(", ")", "-", "[", "]", "_", "*", "~", "."]:
        assert f"\\{char}" in escaped


def test_format_article_markdown_v2():
    article = {
        "title": "Quantum Leap in Computing: 99.9% Gate Fidelity!",
        "source": "BBC News",
        "published_date": "2026-09-12T10:00:00Z",
        "summary": "A <p>major milestone</p> was reached by physicists across international labs.",
        "link": "https://www.bbc.com/news/technology-12345?ref=bot",
    }
    formatted = format_article_markdown_v2(article)

    # Check structural formatting
    assert formatted.startswith("*Quantum Leap in Computing: 99\\.9% Gate Fidelity\\!*")
    assert "_BBC News — 2026\\-09\\-12T10:00:00Z_" in formatted
    assert "[Read more](https://www.bbc.com/news/technology-12345?ref=bot)" in formatted
    assert "A major milestone was reached by physicists" in formatted


def test_format_article_summary_truncation():
    long_summary = "A" * 500
    article = {
        "title": "Short Title",
        "source": "News Source",
        "published_date": "Today",
        "summary": long_summary,
        "link": "https://example.com/item",
    }
    formatted = format_article_markdown_v2(article)
    # The summary portion must be truncated to <= 300 chars (escaped as \.\.\.)
    assert "\\.\\.\\." in formatted


# ────────────────────────────────────────────────────────
# 2. DATABASE & DEDUPLICATION TESTS
# ────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path=db_path)
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)


def test_database_insert_and_deduplication(temp_db):
    articles = [
        {
            "source": "BBC News",
            "title": "Headline 1",
            "link": "https://bbc.com/article1",
            "summary": "Summary 1",
            "author": "Alice",
            "published_date": "2026-09-12T08:00:00Z",
            "fetched_at": "2026-09-12T10:00:00Z",
        },
        {
            "source": "Al Jazeera",
            "title": "Headline 2",
            "link": "https://aljazeera.com/article2",
            "summary": "Summary 2",
            "author": "Bob",
            "published_date": "2026-09-12T09:00:00Z",
            "fetched_at": "2026-09-12T10:00:00Z",
        },
    ]

    # First insert: both should be newly inserted
    new_items_first = temp_db.insert_articles(articles)
    assert len(new_items_first) == 2

    # Second insert with same links + 1 new link: only the 1 new item is returned
    extra_article = {
        "source": "The Hindu",
        "title": "Headline 3",
        "link": "https://thehindu.com/article3",
        "summary": "Summary 3",
        "author": "Charlie",
        "published_date": "2026-09-12T10:00:00Z",
        "fetched_at": "2026-09-12T10:00:00Z",
    }
    batch_with_dupes = articles + [extra_article]
    new_items_second = temp_db.insert_articles(batch_with_dupes)

    assert len(new_items_second) == 1
    assert new_items_second[0]["link"] == "https://thehindu.com/article3"


def test_database_search_and_filter(temp_db):
    articles = [
        {
            "source": "The New York Times",
            "title": "Renewable Solar Energy Breakthrough",
            "link": "https://nytimes.com/solar",
            "summary": "Solar efficiency jumps to 40% using perovskite tandem cells.",
            "author": "Elena",
            "published_date": "2026-09-10T12:00:00Z",
            "fetched_at": "2026-09-10T12:00:00Z",
        },
        {
            "source": "BBC News",
            "title": "Deep Space Satellite Launch",
            "link": "https://bbc.com/space",
            "summary": "Heavy rocket deploys telescope into Lagrange point 2.",
            "author": "David",
            "published_date": "2026-09-11T12:00:00Z",
            "fetched_at": "2026-09-11T12:00:00Z",
        },
    ]
    temp_db.insert_articles(articles)

    # Search in title
    solar_results = temp_db.search_articles("solar")
    assert len(solar_results) == 1
    assert solar_results[0]["source"] == "The New York Times"

    # Search in summary (case-insensitive)
    telescope_results = temp_db.search_articles("TELESCOPE")
    assert len(telescope_results) == 1
    assert telescope_results[0]["title"] == "Deep Space Satellite Launch"

    # Filter by source
    nyt_only = temp_db.get_latest_articles(limit=5, source="The New York Times")
    assert len(nyt_only) == 1
    assert nyt_only[0]["link"] == "https://nytimes.com/solar"


def test_database_subscriptions(temp_db):
    assert temp_db.add_subscription(12345) is True
    assert temp_db.is_subscribed(12345) is True
    assert 12345 in temp_db.get_all_subscriptions()

    # Re-subscribing should return False
    assert temp_db.add_subscription(12345) is False

    # Unsubscribe
    assert temp_db.remove_subscription(12345) is True
    assert temp_db.is_subscribed(12345) is False


# ────────────────────────────────────────────────────────
# 3. FEED ENGINE & ERROR HANDLING TESTS
# ────────────────────────────────────────────────────────

def test_feed_engine_normalization():
    engine = FeedEngine(user_agent="TestBot/1.0")

    mock_parsed_feed = MagicMock()
    mock_parsed_feed.status = 200
    mock_parsed_feed.bozo = False

    entry1 = MagicMock()
    entry1.link = "https://bbc.com/news/1"
    entry1.title = "Mock Headline 1"
    entry1.summary = "<p>Mock summary text</p>"
    entry1.author = "Reporter Alice"
    entry1.published = "Sat, 12 Sep 2026 12:00:00 GMT"

    mock_parsed_feed.entries = [entry1]

    with patch("feedparser.parse", return_value=mock_parsed_feed):
        with patch.object(engine, "is_allowed_by_robots", return_value=True):
            source = FeedSource("BBC News", "http://feeds.bbci.co.uk/news/rss.xml")
            items, error = engine.fetch_source(source, correlation_id="test1234")

            assert error is None
            assert len(items) == 1
            item = items[0]
            assert item["source"] == "BBC News"
            assert item["title"] == "Mock Headline 1"
            assert item["link"] == "https://bbc.com/news/1"
            assert item["summary"] == "<p>Mock summary text</p>"
            assert item["author"] == "Reporter Alice"
            assert item["published_date"] == "Sat, 12 Sep 2026 12:00:00 GMT"
            assert "fetched_at" in item


def test_feed_engine_error_resilience():
    engine = FeedEngine(user_agent="TestBot/1.0")

    # Simulate HTTP 429 Rate Limit
    mock_429 = MagicMock()
    mock_429.status = 429
    mock_429.entries = []

    with patch("feedparser.parse", return_value=mock_429):
        with patch.object(engine, "is_allowed_by_robots", return_value=True):
            source = FeedSource("RateLimitedSource", "https://example.com/rss")
            items, error = engine.fetch_source(source, correlation_id="test429")
            assert items == []
            assert error is not None and "HTTP 429" in error

    # Simulate HTTP 500 Server Error
    mock_500 = MagicMock()
    mock_500.status = 500
    mock_500.entries = []

    with patch("feedparser.parse", return_value=mock_500):
        with patch.object(engine, "is_allowed_by_robots", return_value=True):
            source = FeedSource("ServerErrorSource", "https://example.com/rss")
            items, error = engine.fetch_source(source, correlation_id="test500")
            assert items == []
            assert error is not None and "HTTP 500" in error
