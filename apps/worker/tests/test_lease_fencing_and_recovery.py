from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import Article, Card, IngestionLease, IngestionRequest, StoryCluster, Source, new_id
from worker.coordination import (
    StaleLeaseError,
    acquire_lease,
    acquire_lease_with_generation,
    atomic_claim_request_with_lease,
    atomic_create_ingestion_request_if_allowed,
    check_trigger_rate_limit_and_concurrency,
    create_ingestion_request,
    heartbeat_lease,
    heartbeat_request,
    is_lease_valid,
    recover_abandoned_requests,
    release_lease,
    renew_lease,
    utc_now,
    validate_lease_fencing,
)
from worker.pipeline import process_eligible_clusters


def test_lease_generation_increments_on_takeover(db: Session):
    """Proves lease generation monotonically increments when an expired lease is taken over."""
    db.query(IngestionLease).delete()
    db.commit()

    w1 = "worker-alpha"
    w2 = "worker-beta"

    # Worker 1 acquires new lease -> generation = 1
    acquired, gen1 = acquire_lease_with_generation(db, lease_name="test_lease", holder_id=w1, ttl_seconds=10)
    assert acquired is True
    assert gen1 == 1

    # Worker 1 can validate fencing at generation 1
    assert validate_lease_fencing(db, lease_name="test_lease", holder_id=w1, expected_generation=1) is True

    # Worker 1 renews lease with matching generation
    assert renew_lease(db, lease_name="test_lease", holder_id=w1, ttl_seconds=20, expected_generation=1) is True

    # Stale generation check fails
    assert validate_lease_fencing(db, lease_name="test_lease", holder_id=w1, expected_generation=999) is False

    # Simulate lease expiry for Worker 1
    past_time = utc_now() - timedelta(seconds=5)
    lease = db.query(IngestionLease).filter_by(lease_name="test_lease").first()
    lease.expires_at = past_time
    db.commit()

    # Worker 2 takes over expired lease -> generation increments to 2
    acquired2, gen2 = acquire_lease_with_generation(db, lease_name="test_lease", holder_id=w2, ttl_seconds=60)
    assert acquired2 is True
    assert gen2 == 2

    # Worker 2 holds lease at generation 2
    assert validate_lease_fencing(db, lease_name="test_lease", holder_id=w2, expected_generation=2) is True

    # Stale Worker 1 attempting renewal or fencing check fails completely
    assert validate_lease_fencing(db, lease_name="test_lease", holder_id=w1, expected_generation=1) is False
    assert renew_lease(db, lease_name="test_lease", holder_id=w1, expected_generation=1) is False
    assert heartbeat_lease(db, lease_name="test_lease", holder_id=w1, expected_generation=1) is False


def test_stale_worker_publication_aborts_with_fencing_error(db: Session):
    """Proves that a stale worker whose lease generation was superseded is blocked from publishing cards."""
    db.query(IngestionLease).delete()
    db.query(Card).delete()
    db.query(Article).delete()
    db.query(StoryCluster).delete()
    db.commit()

    # Set up source, article, and eligible story cluster
    src = Source(
        id=new_id(),
        name="Test Fencing News",
        category="national",
        trust_tier="1",
        is_active=True,
    )
    db.add(src)
    cluster = StoryCluster(
        id=new_id(),
        title_hint="Test Fencing Cluster Event",
        eligible=True,
        flagged_conflict=False,
    )
    db.add(cluster)
    art = Article(
        id=new_id(),
        source_id=src.id,
        cluster_id=cluster.id,
        url="https://fencing.example.com/item-1",
        title="Major Milestone Reached in Tech Event",
        raw_text="Full reporting on the major milestone event with verifiable details.",
        category="national",
    )
    db.add(art)
    db.commit()

    # Worker 1 acquired lease at generation 1
    w1 = "worker-slow-1"
    acquire_lease_with_generation(db, lease_name="canonical_ingestion", holder_id=w1, ttl_seconds=10)

    # Worker 2 preempts and takes over lease at generation 2
    past_time = utc_now() - timedelta(seconds=1)
    lease = db.query(IngestionLease).filter_by(lease_name="canonical_ingestion").first()
    lease.expires_at = past_time
    db.commit()

    w2 = "worker-fast-2"
    acquire_lease_with_generation(db, lease_name="canonical_ingestion", holder_id=w2, ttl_seconds=300)

    # Stale Worker 1 wakes up and attempts to publish cards with its stale generation (1)
    class DummyLLM:
        def complete_json(self, *args, **kwargs):
            return {
                "headline": "Major Milestone Reached in Tech Event",
                "summary": "Full reporting on the major milestone event.",
                "category": "national",
                "priority_score": 5,
                "content_type": "NEWS",
                "conflicts": [],
                "key_facts": ["Milestone reached", "Technical success confirmed"],
            }
        def complete_text(self, *args, **kwargs):
            return "{\"consistent\": true}"

    with pytest.raises(StaleLeaseError) as exc_info:
        process_eligible_clusters(
            db,
            DummyLLM(),
            expected_lease_holder=w1,
            expected_lease_generation=1,
            lease_name="canonical_ingestion",
        )

    assert "superseded" in str(exc_info.value).lower()

    # Verify no cards were published by the stale worker
    cards = db.query(Card).filter(Card.cluster_id == cluster.id).all()
    assert len(cards) == 0

    # Legitimate Worker 2 can publish cards with its valid generation (2)
    published = process_eligible_clusters(
        db,
        DummyLLM(),
        expected_lease_holder=w2,
        expected_lease_generation=2,
        lease_name="canonical_ingestion",
    )
    assert len(published) == 1
    cards_after = db.query(Card).filter(Card.cluster_id == cluster.id).all()
    assert len(cards_after) == 1


def test_atomic_claim_fails_safe_when_lease_held(db: Session):
    """Proves that a pending IngestionRequest is NEVER claimed or marked running if lease cannot be acquired."""
    db.query(IngestionLease).delete()
    db.query(IngestionRequest).delete()
    db.commit()

    # Worker A holds active lease
    acquire_lease(db, lease_name="canonical_ingestion", holder_id="worker-A", ttl_seconds=300)

    # User queues an IngestionRequest
    req = create_ingestion_request(db, trigger_origin="manual_api")
    assert req.status == "pending"

    # Worker B tries to claim request -> lease cannot be acquired
    claimed, gen = atomic_claim_request_with_lease(db, worker_id="worker-B", lease_name="canonical_ingestion")
    assert claimed is None
    assert gen is None

    # Request MUST still be in 'pending' status untouched
    db.refresh(req)
    assert req.status == "pending"
    assert req.worker_id is None
    assert req.started_at is None
    assert req.attempt_count == 0


def test_abandoned_request_crash_recovery(db: Session):
    """Proves recovery of an IngestionRequest stranded in 'running' state after worker crash."""
    db.query(IngestionLease).delete()
    db.query(IngestionRequest).delete()
    db.commit()

    crashed_worker = "crashed-worker-pid-8888"
    past = utc_now() - timedelta(seconds=400)

    # Stranded request from crashed worker
    req = IngestionRequest(
        id=new_id(),
        status="running",
        trigger_origin="manual_api",
        worker_id=crashed_worker,
        attempt_count=1,
        started_at=past,
        last_heartbeat_at=past,
        lease_generation=1,
        created_at=past,
    )
    db.add(req)
    db.commit()

    # Concurrency check should block initially if not recovered
    # But recover_abandoned_requests resets it to 'pending'
    recovered = recover_abandoned_requests(db, max_age_seconds=300, max_retries=3)
    assert recovered == 1

    db.refresh(req)
    assert req.status == "pending"
    assert req.worker_id is None
    assert req.started_at is None
    assert req.attempt_count == 1  # Preserves attempt history

    # Now a healthy worker can claim and execute it
    healthy_worker = "healthy-worker-pid-9999"
    claimed, gen = atomic_claim_request_with_lease(db, worker_id=healthy_worker)
    assert claimed is not None
    assert claimed.id == req.id
    assert claimed.status == "running"
    assert claimed.worker_id == healthy_worker
    assert claimed.attempt_count == 2
    assert claimed.lease_generation == gen


def test_abandoned_request_exceeds_max_retries_fails_closed(db: Session):
    """Proves that repeatedly crashing requests fail closed after max_retries instead of looping infinitely."""
    db.query(IngestionLease).delete()
    db.query(IngestionRequest).delete()
    db.commit()

    past = utc_now() - timedelta(seconds=500)
    req = IngestionRequest(
        id=new_id(),
        status="running",
        trigger_origin="manual_api",
        worker_id="crashed-worker-repeated",
        attempt_count=3,  # Already at max retries
        started_at=past,
        last_heartbeat_at=past,
        created_at=past,
    )
    db.add(req)
    db.commit()

    recovered = recover_abandoned_requests(db, max_age_seconds=300, max_retries=3)
    assert recovered == 1

    db.refresh(req)
    assert req.status == "failed"
    assert req.completed_at is not None
    assert "exceeded maximum retry attempts (3)" in req.error_message

    # Concurrency is now unblocked for new requests
    allowed, reason, _ = check_trigger_rate_limit_and_concurrency(db, cooldown_seconds=10)
    assert allowed is True
    assert reason is None
