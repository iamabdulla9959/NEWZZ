import httpx
from sqlalchemy.orm import Session

from app.models import Article, Source, new_id
from worker.currents import CurrentsClient, ingest_currents_source


def test_currents_ingestion_maps_article_and_district(db: Session):
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["authorization"] = request.headers.get("authorization", "")
        assert "apikey" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "news": [
                    {
                        "title": "Example district opens health centre",
                        "description": "A new health centre opened in Example district.",
                        "url": "https://example.invalid/currents-story",
                        "published": "2026-09-09T10:00:00Z",
                    }
                ],
            },
        )

    source = Source(
        id=new_id(),
        name="Currents Example",
        category="health",
        region="IN",
        district="Exampleville",
        source_type="currents_api",
        trust_tier="2",
    )
    db.add(source)
    db.commit()

    client = CurrentsClient(
        api_key="test-currents-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    created, requests, errors = ingest_currents_source(db, source, client)

    assert created == 1
    assert requests == 1
    assert errors == []
    assert seen_headers["authorization"] == "test-currents-key"
    article = db.query(Article).one()
    assert article.district == "Exampleville"
    assert article.published_at is not None
