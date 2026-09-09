from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import Card, CardSource, ReviewQueueItem, Source, StoryCluster, new_id

client = TestClient(app)
ADMIN = {"X-Admin-Key": "change-me-local-only"}


def _seed_card(db, status: str, category: str = "national") -> Card:
    source = Source(
        id=new_id(),
        name="Example Gazette",
        category=category,
        region="Example State",
        rss_url="https://example.invalid/rss.xml",
        trust_tier=2,
        is_active=True,
    )
    cluster = StoryCluster(id=new_id(), title_hint="Example Corp plant", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Example Corp opens plant",
        summary="Example Corp opened a bicycle-parts plant in Exampleville.",
        category=category,
        verified_status=status,
        state="Example State",
        published_at=datetime.now(timezone.utc) if status == "published" else None,
    )
    db.add_all([source, cluster, card])
    db.flush()
    db.add(
        CardSource(
            id=new_id(),
            card_id=card.id,
            source_id=source.id,
            name=source.name,
            url="https://example.invalid/story",
            trust_tier=2,
        )
    )
    db.commit()
    return card


def test_feed_excludes_unpublished(db):
    _seed_card(db, "published")
    _seed_card(db, "pending_review")
    _seed_card(db, "rejected")
    response = client.get("/feed")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert all(item["verified_status"] == "published" for item in body["items"])


def test_feed_excludes_dev_testing_cards(db):
    """DoD: Cards created via newsapi_dev_only (created_by='dev_testing') are excluded from /feed by default."""
    live_card = _seed_card(db, "published")
    live_card.created_by = "live_pipeline"

    dev_card = _seed_card(db, "published")
    dev_card.created_by = "dev_testing"
    dev_card.headline = "Dev Testing Card Only"
    db.commit()

    response = client.get("/feed")
    assert response.status_code == 200
    body = response.json()
    headlines = [item["headline"] for item in body["items"]]
    assert dev_card.headline not in headlines
    assert any(item["id"] == live_card.id for item in body["items"])


def test_feed_filters_category(db):
    _seed_card(db, "published", "tech")
    _seed_card(db, "published", "national")
    response = client.get("/feed", params={"categories": "tech"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "tech"


def test_card_sources_404_for_unpublished(db):
    card = _seed_card(db, "pending_review")
    response = client.get(f"/card/{card.id}/sources")
    assert response.status_code == 404


def test_admin_approve_then_feed(db):
    card = _seed_card(db, "pending_review")
    item = ReviewQueueItem(
        id=new_id(),
        card_id=card.id,
        reasons=["banned_words:shocking"],
        source_excerpts="Example Corp announced a plant.",
        status="pending",
    )
    db.add(item)
    db.commit()
    approve = client.post(f"/admin/review/{item.id}/approve", headers=ADMIN)
    assert approve.status_code == 200
    feed = client.get("/feed")
    ids = [i["id"] for i in feed.json()["items"]]
    assert card.id in ids


def test_admin_reject_never_in_feed(db):
    card = _seed_card(db, "pending_review")
    item = ReviewQueueItem(
        id=new_id(),
        card_id=card.id,
        reasons=["sensitivity_keyword"],
        source_excerpts="Example Corp announced a plant.",
        status="pending",
    )
    db.add(item)
    db.commit()
    reject = client.post(f"/admin/review/{item.id}/reject", headers=ADMIN)
    assert reject.status_code == 200
    feed = client.get("/feed")
    ids = [i["id"] for i in feed.json()["items"]]
    assert card.id not in ids
