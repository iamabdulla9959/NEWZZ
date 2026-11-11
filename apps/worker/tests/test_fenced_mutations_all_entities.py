from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import (
    Article,
    Card,
    CardSource,
    IngestionLease,
    IngestionRequest,
    Source,
    StoryCluster,
    WorkerRun,
    new_id,
)
from worker.coordination import (
    acquire_lease_with_generation,
    atomic_claim_request_with_lease,
    finish_request,
    validate_lease_fencing,
    IngestionHeartbeat,
    StaleLeaseError,
    utc_now,
)
from worker.ingest import ingest_rss_source
from worker.pipeline import process_eligible_clusters


class MockLLM:
    def complete_json(self, *args, **kwargs):
        return {
            "headline": "Fencing Test Headline",
            "summary": "Summary of event.",
            "category": "national",
            "priority_score": 7,
            "content_type": "NEWS",
            "conflicts": [],
            "key_facts": ["Fact 1"],
        }

    def complete_text(self, *args, **kwargs):
        return '{"consistent": true}'


def test_stale_worker_cannot_insert_articles(db: Session, monkeypatch):
    """Proves Worker A (holding stale generation 1) cannot insert or commit articles
    when Worker B has claimed generation 2.
    """
    # 1. Worker A acquires gen 1
    w_a = "worker-stale-a"
    ok, gen_a = acquire_lease_with_generation(db, holder_id=w_a, ttl_seconds=1)
    assert ok is True and gen_a == 1

    # Lease expires
    time.sleep(1.1)

    # 2. Worker B claims gen 2
    w_b = "worker-fresh-b"
    ok, gen_b = acquire_lease_with_generation(db, holder_id=w_b, ttl_seconds=300)
    assert ok is True and gen_b == 2

    # 3. Source setup
    src = Source(id=new_id(), name="Fenced Source Wire", category="national", rss_url="http://mock.feed", trust_tier="1", is_active=True)
    db.add(src)
    db.commit()

    # Mock feedparser response with an article
    class MockEntry(dict):
        pass
    entry = MockEntry({
        "link": "https://example.com/stale-worker-article-99",
        "title": "Stale Worker Article Title",
        "summary": "Full text of article that should be blocked by lease fencing.",
        "published": "Fri, 31 Oct 2026 12:00:00 GMT",
    })
    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda content: type("Obj", (), {"entries": [entry]})())
    
    class MockClient:
        def get(self, url, **kwargs):
            return type("Resp", (), {"status_code": 200, "content": b"<xml/>", "raise_for_status": lambda *a, **k: None})()
        def close(self):
            pass

    # 4. Worker A attempts to ingest using its stale generation 1
    with pytest.raises(StaleLeaseError) as exc_info:
        ingest_rss_source(
            db,
            src,
            client=MockClient(),
            expected_lease_holder=w_a,
            expected_lease_generation=gen_a,
        )
    assert "Lease superseded" in str(exc_info.value)

    # Verify article was NOT committed to the database
    articles = db.query(Article).filter(Article.url == "https://example.com/stale-worker-article-99").all()
    assert len(articles) == 0, "Stale worker article MUST NOT be committed"


def test_stale_worker_cannot_create_or_publish_cards_and_sources(db: Session):
    """Proves Worker A (stale gen 1) cannot create Cards or CardSources after Worker B takes gen 2."""
    w_a = "worker-stale-card"
    acquire_lease_with_generation(db, holder_id=w_a, ttl_seconds=1)
    time.sleep(1.1)

    w_b = "worker-fresh-card"
    acquire_lease_with_generation(db, holder_id=w_b, ttl_seconds=300)

    # Story cluster exists and is eligible
    cluster = StoryCluster(id=new_id(), title_hint="Cluster for fencing test", eligible=True)
    db.add(cluster)
    s1 = Source(id=new_id(), name="Wire 1", category="national", trust_tier="1", is_active=True)
    s2 = Source(id=new_id(), name="Wire 2", category="national", trust_tier="1", is_active=True)
    db.add(s1)
    db.add(s2)
    a1 = Article(id=new_id(), source_id=s1.id, cluster_id=cluster.id, url="http://test.com/a1", title="Title A", raw_text="text a", category="national")
    a2 = Article(id=new_id(), source_id=s2.id, cluster_id=cluster.id, url="http://test.com/a2", title="Title B", raw_text="text b", category="national")
    db.add(a1)
    db.add(a2)
    db.commit()

    # Worker A attempts publication under stale gen 1 -> must raise StaleLeaseError
    with pytest.raises(StaleLeaseError):
        process_eligible_clusters(
            db,
            MockLLM(),
            expected_lease_holder=w_a,
            expected_lease_generation=1,
        )

    # Verify no Card or CardSource exists
    assert len(db.query(Card).all()) == 0
    assert len(db.query(CardSource).all()) == 0


def test_stale_worker_cannot_finish_ingestion_request(db: Session):
    """Proves Worker A cannot finish an IngestionRequest if generation advanced."""
    past = utc_now() - timedelta(seconds=100)
    req = IngestionRequest(
        id=new_id(),
        status="running",
        trigger_origin="manual_api",
        attempt_count=1,
        started_at=past,
        last_heartbeat_at=past,
        lease_generation=2,  # Taken over at gen 2
    )
    db.add(req)
    db.commit()

    # Stale Worker A (thinking it still has gen 1) tries to mark it succeeded
    res = finish_request(
        db,
        request_id=req.id,
        worker_id="worker-stale-finish",
        status="succeeded",
        expected_generation=1,
    )
    assert res is False, "finish_request MUST return False when generation does not match"

    db.refresh(req)
    assert req.status == "running", "Request status must remain untouched by stale worker"


def test_heartbeat_thread_isolation_and_exception_propagation(db: Session):
    """Proves IngestionHeartbeat uses independent session and propagates thread failure."""
    from app.db import SessionLocal

    # Test that Heartbeat raises StaleLeaseError on exit if lease was stolen
    w_a = "worker-heartbeat-test"
    ok, gen = acquire_lease_with_generation(db, holder_id=w_a, ttl_seconds=300)
    assert ok is True

    with pytest.raises(StaleLeaseError):
        with IngestionHeartbeat(
            session_factory=SessionLocal,
            holder_id=w_a,
            generation=gen,
            interval_seconds=0.1,
            ttl_seconds=300,
        ) as hb:
            time.sleep(0.2)
            assert hb.is_valid is True

            # External process / takeover steals the lease
            w_b = "worker-interloper"
            lease = db.query(IngestionLease).filter(IngestionLease.lease_name == "canonical_ingestion").first()
            lease.holder_id = w_b
            lease.lease_generation = gen + 1
            db.commit()

            # Wait for next heartbeat pulse
            time.sleep(0.3)
            assert hb.is_valid is False
            hb.check_health()
