from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


client = TestClient(app)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "display_name": "Example Road, Exampleville",
            "address": {
                "city_district": "Exampleville",
                "state": "Example State",
            },
        }


def test_reverse_location_maps_nominatim_fields(monkeypatch):
    monkeypatch.setattr(settings, "locationiq_api_key", "")
    monkeypatch.setattr("app.routers.location.httpx.get", lambda *args, **kwargs: FakeResponse())

    response = client.get("/location/reverse", params={"latitude": 20, "longitude": 77})
    assert response.status_code == 200
    assert response.json()["district"] == "Exampleville"
    assert response.json()["state"] == "Example State"
