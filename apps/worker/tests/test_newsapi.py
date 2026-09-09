from __future__ import annotations

import os
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Card, Source, StoryCluster, new_id
from worker.newsapi import (
    NEWSAPI_CATEGORY_MAPPING,
    NewsApiClient,
    is_newsapi_dev_enabled,
    poll_newsapi_dev_sources,
)
from worker.pipeline import _build_card


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_newsapi_disabled_by_default(monkeypatch):
    """DoD: NewsAPI is strictly gated behind ENABLE_NEWSAPI_DEV_SOURCE=true."""
    monkeypatch.delenv("ENABLE_NEWSAPI_DEV_SOURCE", raising=False)
    assert not is_newsapi_dev_enabled()

    client = NewsApiClient(api_key="test-key")
    items, reqs, errors = client.fetch_top_headlines(category="tech")
    assert items == []
    assert reqs == 0
    assert any("disabled" in err.lower() for err in errors)


def test_newsapi_client_key_never_logged_and_tracks_requests(monkeypatch):
    """DoD: API key is never in __repr__ and requests are tracked."""
    secret_key = "super-secret-newsapi-key-12345"
    client = NewsApiClient(api_key=secret_key)
    repr_str = repr(client)
    assert secret_key not in repr_str
    assert "key_set=True" in repr_str
    assert "dev_only=True" in repr_str

    monkeypatch.setenv("ENABLE_NEWSAPI_DEV_SOURCE", "true")

    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "url": "https://example.com/art1",
                "title": "Test NewsAPI Title",
                "description": "Desc",
                "content": "Content",
                "publishedAt": "2026-09-07T12:00:00Z",
            }
        ],
    }
    mock_http.get.return_value = mock_resp

    client = NewsApiClient(api_key=secret_key, http_client=mock_http)
    items, reqs, errors = client.fetch_top_headlines(category="tech", country="in")

    assert len(items) == 1
    assert reqs == 1
    assert errors == []

    # Verify call parameters and header auth
    mock_http.get.assert_called_once()
    _, kwargs = mock_http.get.call_args
    assert kwargs["params"]["category"] == "technology"
    assert kwargs["params"]["country"] == "in"
    assert kwargs["headers"]["X-Api-Key"] == secret_key


def test_main_production_scheduler_never_invokes_newsapi():
    """DoD: Grep confirms main.py's production scheduler never invokes NewsAPI client regardless of DB state."""
    main_py_path = os.path.join(os.path.dirname(__file__), "..", "worker", "main.py")
    with open(main_py_path, "r", encoding="utf-8") as f:
        content = f.read()

    # The production scheduler job IDs
    assert "scheduler.add_job" in content
    # Ensure no newsapi jobs are registered with scheduler
    assert "newsapi_ingest" not in content
    assert "poll_newsapi" not in content
    assert "run_newsapi" not in content
    assert "NewsApiClient" not in content


def test_pipeline_tags_card_as_dev_testing_for_newsapi_source(test_db):
    """DoD: Any Card generated from newsapi_dev_only articles must be tagged created_by='dev_testing'."""
    src = Source(
        id=new_id(),
        name="NewsAPI Dev Tech",
        category="tech",
        region=None,
        rss_url=None,
        trust_tier="2",
        source_type="newsapi_dev_only",
        is_active=True,
    )
    test_db.add(src)
    test_db.commit()

    cluster = StoryCluster(id=new_id())
    test_db.add(cluster)

    art = Article(
        id=new_id(),
        source_id=src.id,
        cluster_id=cluster.id,
        url="https://newsapi.org/test/1",
        title="NewsAPI Dev Story",
        raw_text="NewsAPI raw text content",
        category="tech",
    )
    test_db.add(art)
    test_db.commit()

    card = _build_card(cluster, [art], {"headline": "NewsAPI Headline", "summary": "NewsAPI Summary"})
    assert card.created_by == "dev_testing"
    assert card.headline == "NewsAPI Headline"


def test_poll_newsapi_dev_sources_respects_env_flag(test_db, monkeypatch):
    """poll_newsapi_dev_sources returns 0 and does not touch DB when disabled."""
    monkeypatch.setenv("ENABLE_NEWSAPI_DEV_SOURCE", "false")
    polled, created, reqs, errs = poll_newsapi_dev_sources(test_db, api_key="dummy")
    assert polled == 0
    assert created == 0
    assert reqs == 0
    assert errs == []
