import time
from datetime import timedelta
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.config import settings
from app.models import IngestionRequest, new_id
from app.coordination import utc_now
from app.db import SessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_requests_db():
    """Clear IngestionRequest rows before and after each test."""
    db = SessionLocal()
    try:
        db.query(IngestionRequest).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(IngestionRequest).delete()
        db.commit()
    finally:
        db.close()


def test_crawl_trigger_rejects_missing_token():
    """Trigger without authorization must return 401 Unauthorized."""
    response = client.post("/crawl/trigger")
    assert response.status_code == 401
    assert "Administrative credentials required" in response.json()["detail"]


def test_crawl_trigger_rejects_invalid_token():
    """Trigger with invalid credentials must return 403 Forbidden."""
    headers = {"Authorization": "Bearer wrong-secret-token"}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 403
    assert "Invalid administrative credentials" in response.json()["detail"]


def test_crawl_trigger_accepts_valid_bearer_token():
    """Trigger with valid Bearer token creates a persistent pending IngestionRequest and returns 200/202."""
    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "request_id" in data
    assert "queued for worker execution" in data["message"]


def test_crawl_trigger_accepts_valid_x_admin_key_header():
    """Trigger with valid X-Admin-Key header creates an IngestionRequest."""
    headers = {"X-Admin-Key": settings.admin_api_key}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "request_id" in data


def test_crawl_trigger_production_fails_closed_when_key_unconfigured(monkeypatch):
    """In production, trigger must fail closed if admin key is empty or default placeholder."""
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "change-me-local-only")
    monkeypatch.setattr(settings, "internal_ingestion_key", "")

    headers = {"Authorization": "Bearer change-me-local-only"}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 403
    assert "Administrative trigger disabled" in response.json()["detail"]


def test_crawl_trigger_rate_limiting_cooldown():
    """Subsequent trigger requests within cooldown period return 429 Too Many Requests."""
    db = SessionLocal()
    try:
        # Simulate request created 2 seconds ago
        db.add(IngestionRequest(
            id=new_id(),
            status="succeeded",
            trigger_origin="manual_api",
            created_at=utc_now() - timedelta(seconds=2),
        ))
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]


def test_crawl_trigger_prevents_concurrent_runs():
    """If a request is already running, trigger returns 409 Conflict."""
    db = SessionLocal()
    try:
        db.add(IngestionRequest(
            id=new_id(),
            status="running",
            trigger_origin="manual_api",
            created_at=utc_now(),
        ))
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}
    response = client.post("/crawl/trigger", headers=headers)
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_crawl_status_rejects_missing_token():
    """GET /crawl/status/{request_id} without credentials must return 401 Unauthorized."""
    response = client.get("/crawl/status/req-12345")
    assert response.status_code == 401
    assert "Administrative credentials required" in response.json()["detail"]


def test_crawl_status_rejects_invalid_token():
    """GET /crawl/status/{request_id} with invalid credentials must return 403 Forbidden."""
    headers = {"Authorization": "Bearer bad-token"}
    response = client.get("/crawl/status/req-12345", headers=headers)
    assert response.status_code == 403
    assert "Invalid administrative credentials" in response.json()["detail"]


def test_crawl_status_accepts_valid_token():
    """GET /crawl/status/{request_id} with valid credentials returns 200 for existing request."""
    db = SessionLocal()
    req_id = new_id()
    try:
        db.add(IngestionRequest(
            id=req_id,
            status="running",
            trigger_origin="manual_api",
            attempt_count=1,
            created_at=utc_now(),
        ))
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {settings.admin_api_key}"}
    response = client.get(f"/crawl/status/{req_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == req_id
    assert data["status"] == "running"

