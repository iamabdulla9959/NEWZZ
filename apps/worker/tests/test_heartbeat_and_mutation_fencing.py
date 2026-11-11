from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Article, Card, CardSource, IngestionLease, IngestionRequest, ReviewQueueItem, Source, StoryCluster, WorkerRun, new_id
from worker.coordination import (
    IngestionHeartbeat,
    StaleLeaseError,
    acquire_lease_with_generation,
    atomic_claim_request_with_lease,
    finish_request,
    heartbeat_lease,
    heartbeat_request,
    recover_abandoned_requests,
    release_lease,
    renew_lease,
    utc_now,
    validate_lease_fencing,
)
from worker.pipeline import process_eligible_clusters
from worker.main import run_rss_once, process_pending_requests


def test_ingestion_heartbeat_actively_refreshes_lease_and_request(db: Session):
    """Proves that IngestionHeartbeat background thread continuously updates last_heartbeat_at
    and extends lease expires_at during a multi-second execution window.
    """
    db.query(IngestionLease).delete()
    db.query(IngestionRequest).delete()
    db.commit()

    worker_id = "heartbeat-test-worker"
    req = IngestionRequest(
        id=new_id(),
        status="pending",
        trigger_origin="manual_api",
        attempt_count=0,
        created_at=utc_now(),
    )
    db.add(req)
    db.commit()

    claimed_req, gen = atomic_claim_request_with_lease(db, worker_id=worker_id, ttl_seconds=30)
    assert claimed_req is not None
    initial_heartbeat = claimed_req.last_heartbeat_at

    lease = db.query(IngestionLease).filter_by(lease_name="canonical_ingestion").first()
    initial_expiry = lease.expires_at

    # Start IngestionHeartbeat with short 1.0s interval
    with IngestionHeartbeat(
        session_factory=SessionLocal,
        lease_name="canonical_ingestion",
        holder_id=worker_id,
        generation=gen,
        request_id=claimed_req.id,
        interval_seconds=1.0,
        ttl_seconds=60,
    ) as hb:
        assert hb.is_valid is True
        # Sleep for 2.5 seconds to allow at least 2 background heartbeat pulses
        time.sleep(2.5)
        assert hb.is_valid is True

    # Re-query from database to verify persistent timestamps were updated
    db.refresh(claimed_req)
    db.refresh(lease)

    assert claimed_req.last_heartbeat_at > initial_heartbeat, "last_heartbeat_at was not updated by background thread"
    assert lease.expires_at > initial_expiry, "lease.expires_at was not extended by background thread"


def test_finish_request_rejects_stale_worker(db: Session):
    """Proves that finish_request rejects attempts by a stale worker to mark a request
    as succeeded or modify its state once its generation has been superseded.
    """
    db.query(IngestionLease).delete()
    db.query(IngestionRequest).delete()
    db.commit()

    # Worker 1 claims request at generation 1
    w1 = "worker-alpha"
    req = IngestionRequest(id=new_id(), status="pending", trigger_origin="manual_api")
    db.add(req)
    db.commit()

    claimed, gen1 = atomic_claim_request_with_lease(db, worker_id=w1)
    assert gen1 == 1

    # Simulate Worker 1 stall: lease expires
    past = utc_now() - timedelta(seconds=1)
    lease = db.query(IngestionLease).filter_by(lease_name="canonical_ingestion").first()
    lease.expires_at = past
    db.commit()

    # Worker 2 recovers and takes over lease at generation 2
    w2 = "worker-beta"
    acquired, gen2 = acquire_lease_with_generation(db, lease_name="canonical_ingestion", holder_id=w2)
    assert acquired is True
    assert gen2 == 2

    # Worker 1 attempts to finish request using stale generation 1 -> MUST BE REJECTED
    res1 = finish_request(
        db,
        request_id=req.id,
        worker_id=w1,
        status="succeeded",
        result_summary={"worker": "w1_stale"},
        expected_generation=1,
    )
    assert res1 is False, "Stale worker was allowed to finish request!"

    db.refresh(req)
    assert req.result_summary is None or req.result_summary.get("worker") != "w1_stale"

    # Worker 2 can legitimately finish request at generation 2
    # Update request lease_generation to 2
    req.lease_generation = 2
    db.commit()

    res2 = finish_request(
        db,
        request_id=req.id,
        worker_id=w2,
        status="succeeded",
        result_summary={"worker": "w2_legit"},
        expected_generation=2,
    )
    assert res2 is True
    db.refresh(req)
    assert req.status == "succeeded"
    assert req.result_summary["worker"] == "w2_legit"


def test_fencing_blocks_stale_clustering(db: Session):
    """Proves that run_rss_once aborts before modifying story clusters if lease generation is superseded."""
    db.query(IngestionLease).delete()
    db.commit()

    w1 = "worker-stall-clustering"
    acquire_lease_with_generation(db, lease_name="canonical_ingestion", holder_id=w1, ttl_seconds=5)

    # Worker 2 preempts
    past = utc_now() - timedelta(seconds=1)
    lease = db.query(IngestionLease).filter_by(lease_name="canonical_ingestion").first()
    lease.expires_at = past
    db.commit()

    w2 = "worker-active-clustering"
    acquire_lease_with_generation(db, lease_name="canonical_ingestion", holder_id=w2, ttl_seconds=300)

    # Worker 1 running with stale generation 1 must raise StaleLeaseError
    with pytest.raises(StaleLeaseError) as exc_info:
        run_rss_once(require_lease=False, worker_id=w1, lease_generation=1)

    assert "superseded" in str(exc_info.value).lower()

