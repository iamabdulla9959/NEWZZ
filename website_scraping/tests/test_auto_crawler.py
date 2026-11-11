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
    """Verify that all 36 Indian jurisdictions (28 states + 8 UTs) and core categories are defined."""
    assert len(INDIAN_STATES) == 36
    assert "Karnataka" in INDIAN_STATES
    assert "Maharashtra" in INDIAN_STATES
    assert "West Bengal" in INDIAN_STATES

    expected_common = {"Technology", "Science", "Business", "Health", "Sports"}
    global_cats = {cat for cat, _ in GLOBAL_CATEGORY_FEEDS}
    india_cats = {cat for cat, _ in INDIA_CATEGORY_FEEDS}
    assert expected_common.issubset(global_cats)
    assert expected_common.issubset(india_cats)
    assert "World" in global_cats
    assert "Politics" in india_cats


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
    """Verify appending fresh articles in valid standard JSON array format."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
        tmp_path = tmp.name

    try:
        articles = [
            {"title": "News 1", "link": "https://example.com/1", "scope": "Global", "category": "Tech"},
            {"title": "News 2", "link": "https://example.com/2", "scope": "India", "category": "Tech"},
        ]
        append_articles_to_file(tmp_path, articles)

        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["title"] == "News 1"
        assert data[1]["scope"] == "India"
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


def test_generate_factual_article_summary_no_synthetic_boilerplate():
    """Verify that summary generation never produces canned synthetic boilerplate."""
    from auto_news_crawler import generate_factual_article_summary

    summary, key_facts, words = generate_factual_article_summary(
        headline="SpaceX launches commercial communications satellite",
        state="National",
        category="Technology",
        source_name="Reuters",
        raw_snippet="Falcon 9 deployed the satellite into geostationary transfer orbit on Tuesday morning.",
    )

    forbidden_patterns = [
        "administrative authorities and civic departments",
        "from a wider standpoint",
        "moving forward, this announcement establishes",
        "official monitoring teams confirmed",
        "dispatches from",
        "authorities and relevant agencies continue to monitor",
        "reports corroborated across",
    ]
    lower_sum = summary.lower()
    for pat in forbidden_patterns:
        assert pat not in lower_sum, f"Summary contained forbidden boilerplate: {pat}"

    assert "Falcon 9 deployed the satellite" in summary
    assert any("Reuters" in kf for kf in key_facts)


def test_generate_factual_article_summary_insufficient_content_fallback():
    """Verify safe fallback without hallucination when article content is minimal or missing."""
    from auto_news_crawler import generate_factual_article_summary

    summary, key_facts, words = generate_factual_article_summary(
        headline="Local road construction approved",
        state="Goa",
        category="State",
        source_name="Goa Herald",
        raw_snippet="",
    )

    assert "Reporting from Goa Herald: Local road construction approved." == summary
    assert "Goa Herald" in key_facts[1]
    assert words > 0

