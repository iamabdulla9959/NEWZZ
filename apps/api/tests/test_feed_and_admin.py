from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import Card, CardSource, ReviewQueueItem, Source, StoryCluster, new_id

client = TestClient(app)
ADMIN = {"X-Admin-Key": "change-me-local-only"}


def _seed_card(db, status: str, category: str = "national") -> Card:
    canonical_cat = {
        "tech": "Technology",
        "technology": "Technology",
        "international": "World",
        "world": "World",
        "global": "World",
        "national": "National",
        "politics": "Politics",
        "business": "Business",
        "science": "Science",
        "health": "Health",
        "sports": "Sports",
        "entertainment": "Entertainment",
        "environment": "Environment",
        "state": "State",
        "education": "Education",
    }.get(category.strip().lower(), category.strip().capitalize())
    source = Source(
        id=new_id(),
        name="Example Gazette",
        category=canonical_cat,
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
        category=canonical_cat,
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
    # Short name query "tech"
    response = client.get("/feed", params={"categories": "tech"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"].lower() in ("tech", "technology")
    # Full name query "technology" must also match seamlessly via synonym expansion
    response_full = client.get("/feed", params={"categories": "technology"})
    assert response_full.status_code == 200
    body_full = response_full.json()
    assert body_full["total"] == 1
    assert body_full["items"][0]["category"].lower() in ("tech", "technology")


def test_feed_district_category_does_not_silently_return_national_fallback(db):
    _seed_card(db, "published", "national")

    response = client.get(
        "/feed",
        params={
            "categories": "district",
            "district": "Exampleville",
            "state": "Example State",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["fallback_used"] is False
    assert body["fallback_level"] is None


def test_feed_excludes_non_news_content(db):
    promotional = _seed_card(db, "published", "national")
    promotional.content_type = "PROMOTIONAL"
    db.commit()
    response = client.get("/feed")
    assert response.status_code == 200
    assert promotional.id not in [item["id"] for item in response.json()["items"]]


def test_empty_feed_explains_no_eligible_stories(db):
    response = client.get("/feed", params={"categories": "politics"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["empty_reason"] == "no_eligible_stories"


def test_feed_returns_only_the_best_card_for_each_story_cluster(db):
    first = _seed_card(db, "published", "international")
    duplicate = _seed_card(db, "published", "international")
    duplicate.cluster_id = first.cluster_id
    duplicate.headline = first.headline
    first.verification_score = 40.0
    duplicate.verification_score = 90.0
    db.commit()

    response = client.get("/feed", params={"categories": "international"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [duplicate.id]


def test_priority_score_neutrality_does_not_override_objective_importance(db):
    """Verify objective importance decisively defeats low-importance stories even with high priority."""
    high_obj = _seed_card(db, "published", "national")
    low_obj_high_priority = _seed_card(db, "published", "national")
    high_obj.headline = "Massive Earthquake: Death toll rises to 150 as emergency rescue deploys"
    high_obj.summary = "National disaster response force deploys as thousands displaced in severe disaster."
    low_obj_high_priority.headline = "Local art exhibition opens in city center"
    low_obj_high_priority.summary = "Paintings and modern sculpture showcased for visitors."
    db.commit()

    response = client.get("/feed", params={"categories": "national"})

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == high_obj.id


def test_feed_raises_genuinely_urgent_civic_news_above_lifestyle_news(db):
    lifestyle = _seed_card(db, "published", "international")
    urgent = _seed_card(db, "published", "international")
    lifestyle.headline = "Museum painting is recovered after a private sale"
    urgent.headline = "State election declared an emergency after flooding"
    db.commit()

    response = client.get("/feed", params={"categories": "international"})

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == urgent.id


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


def test_feed_state_priority_orders_user_state_first(db):
    # Seed a card for Bihar with a dramatic flood headline (high importance)
    c_bihar = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline="Major floods worsen across northern districts",
        summary="Severe flooding affects thousands.",
        category="State",
        state="Bihar",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    # Seed a card for Telangana with a local civic headline
    c_telangana = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline="Telangana Assembly session begins with civic reforms discussion",
        summary="Local leaders convene to discuss state developmental initiatives.",
        category="State",
        state="Telangana",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([c_bihar, c_telangana])
    db.commit()

    # Query feed requesting state=Telangana
    res = client.get("/feed?category=state&state=Telangana")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    assert len(items) >= 1
    # Telangana story must be the top story
    assert items[0]["id"] == c_telangana.id
    assert items[0]["state"] == "Telangana"

