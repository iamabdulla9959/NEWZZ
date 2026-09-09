from datetime import datetime, timezone
import json
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Source, StoryCluster, WorkerRun
from worker.newsdata import (
    DAILY_CREDIT_CEILING,
    NEWSDATA_POLL_INTERVAL_MINUTES,
    NewsDataClient,
    get_daily_credits_used,
    ingest_newsdata_source,
    poll_newsdata_sources,
)
from worker.pipeline import cluster_unassigned_articles


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_poll_interval_constant():
    """Verify schedule interval is a named tuneable constant between 60 and 90 minutes."""
    assert 60 <= NEWSDATA_POLL_INTERVAL_MINUTES <= 90


def test_newsdata_ingestion_and_pipeline_flow(memory_db):
    """DoD 1: Running worker against NewsData populates Articles and flows through clustering."""
    db = memory_db
    source = Source(
        id="src-nd-tech",
        name="NewsData.io Technology",
        category="tech",
        region=None,
        trust_tier="2",
        source_type="newsdata_api",
        is_active=True,
    )
    db.add(source)
    db.commit()

    sample_response = {
        "status": "success",
        "totalResults": 2,
        "results": [
            {
                "article_id": "nd-art-1",
                "title": "Quantum Chip Achieves Quantum Supremacy In Lab",
                "link": "https://example.com/nd-1",
                "description": "Researchers revealed a breakthrough superconductor chip.",
                "content": "A detailed report on the new semiconductor design and benchmarks.",
                "pubDate": "2026-09-07 08:00:00",
                "language": "english",
                "category": ["technology"],
            },
            {
                "article_id": "nd-art-2",
                "title": "Quantum Chip Achieves Quantum Supremacy In Lab Breakthrough",
                "link": "https://example.com/nd-2",
                "description": "Lab scientists demonstrated quantum supremacy on complex algorithms.",
                "content": "Scientists have shown superconductor quantum supremacy in benchmarks.",
                "pubDate": "2026-09-07 08:30:00",
                "language": "english",
                "category": ["technology"],
            },
        ],
    }

    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=sample_response)
    )
    http_client = httpx.Client(transport=mock_transport)
    nd_client = NewsDataClient(api_key="secret-key-placeholder", http_client=http_client)

    created, credits_used, errors = ingest_newsdata_source(db, source, client=nd_client)
    assert created == 2
    assert credits_used == 1
    assert len(errors) == 0

    articles = db.query(Article).all()
    assert len(articles) == 2
    assert articles[0].source_id == "src-nd-tech"
    assert articles[0].category == "tech"
    assert "superconductor" in articles[0].raw_text

    # Flow into clustering pipeline like any RSS article
    clustered_count = cluster_unassigned_articles(db)
    assert clustered_count == 2
    # Both articles describe the same quantum event with high keyword overlap
    assert articles[0].cluster_id is not None
    assert articles[0].cluster_id == articles[1].cluster_id


def test_credit_usage_tracking_and_ceiling(memory_db):
    """DoD 2: worker_runs shows credit usage per run specifically for newsdata_api."""
    db = memory_db

    # 1. Log a previous run with credits used
    prev_run = WorkerRun(
        id="run-1",
        provider="newsdata_api",
        sources_polled=2,
        articles_ingested=10,
        credits_used=2,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(prev_run)
    db.commit()

    assert get_daily_credits_used(db) == 2

    # 2. Test ceiling enforcement
    ceiling_run = WorkerRun(
        id="run-2",
        provider="newsdata_api",
        sources_polled=10,
        articles_ingested=50,
        credits_used=DAILY_CREDIT_CEILING - 2,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(ceiling_run)
    db.commit()

    assert get_daily_credits_used(db) == DAILY_CREDIT_CEILING

    # Now poll_newsdata_sources must skip and not execute requests
    mock_client = MagicMock()
    polled, created, credits, errors = poll_newsdata_sources(db, client=mock_client)
    assert polled == 0
    assert created == 0
    assert credits == 0
    assert any("Daily credit ceiling reached" in e for e in errors)
    mock_client.fetch_latest.assert_not_called()


def test_newsdata_polls_two_targeted_queries_per_category(memory_db):
    sources = [
        Source(id="src-nd-national", name="NewsData.io National", category="national", region="IN", trust_tier="2", source_type="newsdata_api", is_active=True),
        Source(id="src-nd-tech", name="NewsData.io Technology", category="tech", region=None, trust_tier="2", source_type="newsdata_api", is_active=True),
        Source(id="src-nd-science", name="NewsData.io Science", category="science", region=None, trust_tier="2", source_type="newsdata_api", is_active=True),
    ]
    memory_db.add_all(sources)
    memory_db.commit()
    mock_client = MagicMock()
    mock_client.fetch_latest.return_value = ([], 1, [])

    polled, created, credits, errors = poll_newsdata_sources(memory_db, client=mock_client)

    assert (polled, created, credits, errors) == (6, 0, 6, [])
    queries = [call.kwargs["query"] for call in mock_client.fetch_latest.call_args_list]
    assert queries == [
        "India politics",
        "India national news",
        "technology",
        "AI startups",
        "science",
        "space research",
    ]


def test_simulated_429_rate_limit_backoff(memory_db):
    """DoD 3: A simulated 429 response is logged as an error, not a crash, and backs off."""
    db = memory_db
    source = Source(
        id="src-nd-1",
        name="NewsData.io National",
        category="national",
        region="IN",
        trust_tier="2",
        source_type="newsdata_api",
        is_active=True,
    )
    source2 = Source(
        id="src-nd-2",
        name="NewsData.io Tech",
        category="tech",
        trust_tier="2",
        source_type="newsdata_api",
        is_active=True,
    )
    db.add_all([source, source2])
    db.commit()

    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(429, json={"status": "error", "results": {"message": "You have exceeded your request limit.", "code": "RateLimitExceeded"}})
    )
    http_client = httpx.Client(transport=mock_transport)
    nd_client = NewsDataClient(api_key="secret-key-placeholder", http_client=http_client)

    # Must not raise an exception
    polled, created, credits, errors = poll_newsdata_sources(db, client=nd_client)

    # Assert 429 is logged as an error
    assert any("429" in e or "limit" in e.lower() for e in errors)
    assert created == 0
    # Polled only 1 source because it backed off immediately instead of looping aggressively on source2
    assert polled == 1


def test_api_key_not_exposed_in_logs_or_output():
    """DoD 4: Verify API key is never leaked in client representation or logged errors."""
    key = "pub_super_secret_key_12345"
    client = NewsDataClient(api_key=key)

    repr_str = repr(client)
    str_str = str(client)
    assert key not in repr_str
    assert key not in str_str

    # Test error output when server returns 401/403
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"status": "error", "results": {"message": "Unauthorized"}})
    )
    http_client = httpx.Client(transport=mock_transport)
    client_with_http = NewsDataClient(api_key=key, http_client=http_client)
    _, _, errors = client_with_http.fetch_latest(category="tech")
    for err in errors:
        assert key not in err
