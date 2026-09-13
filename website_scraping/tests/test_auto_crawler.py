import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from auto_news_crawler import (
    GLOBAL_CATEGORY_FEEDS,
    INDIA_CATEGORY_FEEDS,
    INDIAN_STATES,
    append_articles_to_file,
    extract_publisher,
    load_existing_links,
    parse_feed_articles,
)


def test_coverage_definitions():
    """Verify that all 28 Indian states and core categories are defined."""
    assert len(INDIAN_STATES) == 28
    assert "Karnataka" in INDIAN_STATES
    assert "Maharashtra" in INDIAN_STATES
    assert "West Bengal" in INDIAN_STATES

    expected_cats = {"Technology", "Science", "Politics", "Business", "Health", "Sports", "Education"}
    global_cats = {cat for cat, _ in GLOBAL_CATEGORY_FEEDS}
    india_cats = {cat for cat, _ in INDIA_CATEGORY_FEEDS}
    assert expected_cats.issubset(global_cats)
    assert expected_cats.issubset(india_cats)


def test_load_existing_links():
    """Verify deduplication link loader handles empty, valid, and malformed files."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
        tmp.write(json.dumps({"link": "https://example.com/article-1"}) + "\n")
        tmp.write("invalid json line\n")
        tmp.write(json.dumps({"link": "https://example.com/article-2"}) + "\n")
        tmp_path = tmp.name

    try:
        links = load_existing_links(tmp_path)
        assert len(links) == 2
        assert "https://example.com/article-1" in links
        assert "https://example.com/article-2" in links
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_append_articles_to_file():
    """Verify appending fresh articles in JSON lines format."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
        tmp_path = tmp.name

    try:
        articles = [
            {"title": "News 1", "link": "https://example.com/1", "scope": "Global", "category": "Tech"},
            {"title": "News 2", "link": "https://example.com/2", "scope": "India", "category": "Tech"},
        ]
        append_articles_to_file(tmp_path, articles)

        with open(tmp_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) == 2
        assert lines[0]["title"] == "News 1"
        assert lines[1]["scope"] == "India"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_extract_publisher():
    """Verify publisher name extraction from RSS source object or title."""
    entry_with_source = MagicMock()
    entry_with_source.source.title = "BBC News"
    assert extract_publisher(entry_with_source, "Default") == "BBC News"

    entry_with_title = MagicMock(spec=["title"])
    entry_with_title.title = "Breaking Discovery in AI - TechCrunch"
    assert extract_publisher(entry_with_title, "Default") == "TechCrunch"


def test_parse_feed_articles_deduplication():
    """Verify duplicate links are strictly omitted during feed ingestion."""
    mock_feed = MagicMock()
    entry1 = MagicMock()
    entry1.link = "https://example.com/seen"
    entry1.title = "Old News"

    entry2 = MagicMock()
    entry2.link = "https://example.com/fresh"
    entry2.title = "Fresh News - Reuters"
    entry2.summary = "A fresh summary"
    entry2.author = "Reporter"
    entry2.published = "2026-09-13T00:00:00Z"

    mock_feed.entries = [entry1, entry2]

    seen_links = {"https://example.com/seen"}

    with patch("feedparser.parse", return_value=mock_feed):
        new_items = parse_feed_articles(
            feed_url="https://fake-feed.xml",
            scope="Global",
            category="Tech",
            state=None,
            default_source="Tech News",
            seen_links=seen_links,
        )

    assert len(new_items) == 1
    assert new_items[0]["link"] == "https://example.com/fresh"
    assert new_items[0]["title"] == "Fresh News"
    assert "https://example.com/fresh" in seen_links
