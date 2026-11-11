import time
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.main import app
from app.config import settings
from app.models import IngestionLease, IngestionRequest, new_id
from app.coordination import (
    acquire_lease,
    renew_lease,
    release_lease,
    is_lease_valid,
    check_trigger_rate_limit_and_concurrency,
    create_ingestion_request,
    claim_pending_request,
    finish_request,
    utc_now,
)

client = TestClient(app)


def test_lease_lifecycle_and_mutual_exclusion(db: Session):
    w1 = "worker-process-1"
    w2 = "worker-process-2"

    # Worker 1 acquires lease
    assert acquire_lease(db, lease_name="test_lease", holder_id=w1, ttl_seconds=60) is True
    assert is_lease_valid(db, lease_name="test_lease", holder_id=w1) is True

    # Worker 2 attempts to acquire same lease -> must be denied
    assert acquire_lease(db, lease_name="test_lease", holder_id=w2, ttl_seconds=60) is False
    assert is_lease_valid(db, lease_name="test_lease", holder_id=w2) is False

    # Worker 1 renews lease
    assert renew_lease(db, lease_name="test_lease", holder_id=w1, ttl_seconds=120) is True

    # Worker 1 releases lease
    assert release_lease(db, lease_name="test_lease", holder_id=w1) is True
    assert is_lease_valid(db, lease_name="test_lease", holder_id=w1) is False

    # Now Worker 2 can acquire lease
    assert acquire_lease(db, lease_name="test_lease", holder_id=w2, ttl_seconds=60) is True
    assert is_lease_valid(db, lease_name="test_lease", holder_id=w2) is True


def test_lease_expiry_and_crash_recovery(db: Session):
    crashed_worker = "worker-crashed-pid-999"
    new_worker = "worker-recovery-pid-1000"

    # Simulate crashed worker holding a lease that has expired
    past_time = utc_now() - timedelta(seconds=10)
    lease = IngestionLease(
        lease_name="crash_test_lease",
        holder_id=crashed_worker,
        acquired_at=past_time - timedelta(seconds=300),
        renewed_at=past_time - timedelta(seconds=100),
        expires_at=past_time,
        is_active=True,
    )
    db.add(lease)
    db.commit()

    # Expired lease is not valid for crashed worker
    assert is_lease_valid(db, lease_name="crash_test_lease", holder_id=crashed_worker) is False

    # New worker automatically recovers and claims the expired lease
    assert acquire_lease(db, lease_name="crash_test_lease", holder_id=new_worker, ttl_seconds=60) is True
    assert is_lease_valid(db, lease_name="crash_test_lease", holder_id=new_worker) is True


def test_ingestion_request_lifecycle(db: Session):
    worker_id = "worker-test-executor"

    # 1. API creates pending request
    req = create_ingestion_request(db, trigger_origin="manual_api")
    assert req.status == "pending"
    assert req.worker_id is None

    # 2. Worker claims pending request
    claimed = claim_pending_request(db, worker_id=worker_id)
    assert claimed is not None
    assert claimed.id == req.id
    assert claimed.status == "running"
    assert claimed.worker_id == worker_id
    assert claimed.started_at is not None

    # 3. Another claim attempt returns None (atomic claim)
    assert claim_pending_request(db, worker_id="other-worker") is None

    # 4. Worker finishes request
    summary = {"articles_ingested": 15, "clusters_created": 3}
    finish_request(db, req.id, worker_id=worker_id, status="succeeded", result_summary=summary)

    db.refresh(claimed)
    assert claimed.status == "succeeded"
    assert claimed.completed_at is not None
    assert claimed.result_summary == summary


def test_api_trigger_creates_persistent_request_and_queries_status(db: Session):
    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}

    # Clean existing requests
    db.query(IngestionRequest).delete()
    db.commit()

    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "request_id" in data
    req_id = data["request_id"]

    # Verify request queryable via GET /crawl/status/{request_id}
    status_resp = client.get(f"/crawl/status/{req_id}", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["request_id"] == req_id
    assert status_data["status"] == "pending"
    assert status_data["trigger_origin"] == "manual_api"


def test_api_trigger_shared_concurrency_lock_returns_409(db: Session):
    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}

    # Simulate an active pending request in the DB
    db.query(IngestionRequest).delete()
    db.add(IngestionRequest(id=new_id(), status="running", trigger_origin="manual_api"))
    db.commit()

    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_api_trigger_shared_rate_limiting_returns_429(db: Session):
    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}

    # Simulate completed request just created 2 seconds ago
    db.query(IngestionRequest).delete()
    db.add(IngestionRequest(
        id=new_id(),
        status="succeeded",
        trigger_origin="manual_api",
        created_at=utc_now() - timedelta(seconds=2),
    ))
    db.commit()

    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]

