from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import WorkerRun, new_id

client = TestClient(app)


def test_health_returns_200_when_db_reachable():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_status_and_geocoder_provider():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["geocoder_provider"] in {"nominatim", "locationiq"}


def test_health_ingestion_returns_status():
    db = SessionLocal()
    try:
        db.add(WorkerRun(id=new_id(), sources_polled=5, articles_ingested=12, errors=None, duration_seconds=1.23))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["sources_polled"] == 5
    assert data["articles_ingested"] == 12
