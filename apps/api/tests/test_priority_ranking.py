from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import Card, CardSource, Source, StoryCluster, UserPreferences, new_id
from worker.scoring import calculate_objective_score, count_impact_keywords


client = TestClient(app)


@pytest.fixture
def ranking_cards(db: Session) -> list[Card]:
    now = datetime.now(timezone.utc)
    cluster = StoryCluster(id=new_id(), title_hint="Cluster for ranking tests", eligible=True)
    source = Source(id=new_id(), name="Daily News", category="national", trust_tier="2")
    db.add_all([cluster, source])
    db.flush()

    # Create 3 cards in different categories with equal baseline objective impact
    # so that personal relevance (category preference) determines the relative ordering
    headline = "Quarterly Activity Report: Operations continuing as planned"
    summary = "Quarterly activity report released covering routine operations."
    card_tech = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline=f"{headline} - Technology",
        summary=summary,
        category="technology",
        verified_status="published",
        published_at=now,
    )
    card_business = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline=f"{headline} - Business",
        summary=summary,
        category="business",
        verified_status="published",
        published_at=now,
    )
    card_sports = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline=f"{headline} - Sports",
        summary=summary,
        category="sports",
        verified_status="published",
        published_at=now,
    )
    db.add_all([card_tech, card_business, card_sports])
    db.commit()
    return [card_tech, card_business, card_sports]


def test_different_device_ids_receive_differently_ordered_feeds(
    db: Session, ranking_cards: list[Card]
):
    # Device A prefers technology > business > sports
    client.put("/user/dev-A/preferences", json={"category_order": ["technology", "business", "sports"]})

    # Device B prefers sports > business > technology
    client.put("/user/dev-B/preferences", json={"category_order": ["sports", "business", "technology"]})

    target_ids = {c.id for c in ranking_cards}

    res_a = client.get("/feed?device_id=dev-A")
    assert res_a.status_code == 200
    items_a = [item for item in res_a.json()["items"] if item["id"] in target_ids]
    categories_a = [item["category"].lower() for item in items_a]
    assert categories_a[0] in ("tech", "technology")
    assert categories_a[1] == "business"
    assert categories_a[2] == "sports"

    res_b = client.get("/feed?device_id=dev-B")
    assert res_b.status_code == 200
    items_b = [item for item in res_b.json()["items"] if item["id"] in target_ids]
    categories_b = [item["category"].lower() for item in items_b]
    assert categories_b[0] == "sports"
    assert categories_b[1] == "business"
    assert categories_b[2] in ("tech", "technology")

    assert categories_a != categories_b, "Different device IDs must receive differently ordered feeds!"


def test_unranked_device_receives_equal_weight_feed(db: Session):
    # Before ranking is set, all categories must be equal weight
    # Seed 2 cards with different objective scores
    cluster = StoryCluster(id=new_id(), title_hint="Unranked test cluster", eligible=True)
    db.add(cluster)
    db.flush()

    card_low_obj = Card(
        id="card-low",
        cluster_id=new_id(),
        headline="Routine Civic Update: Road maintenance scheduled",
        summary="Road maintenance scheduled next week.",
        category="national",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    card_high_obj = Card(
        id="card-high",
        cluster_id=new_id(),
        headline="Major Earthquake Strikes: Thousands Affected in Natural Disaster",
        summary="Government declares state of emergency as search and rescue teams deploy.",
        category="national",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([card_low_obj, card_high_obj])
    db.commit()

    # Query with completely unranked device
    res = client.get("/feed?device_id=brand-new-device-id")
    assert res.status_code == 200
    items = res.json()["items"]
    # The higher objective score card must come first, since category weights are equal (0.0)
    card_ids = [item["id"] for item in items]
    assert card_ids.index("card-high") < card_ids.index("card-low")


def test_updating_category_order_immediately_affects_next_fetch(
    db: Session, ranking_cards: list[Card]
):
    device_id = "test-device-dynamic"

    target_ids = {c.id for c in ranking_cards}

    # 1. Initial order: sports first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["sports", "technology", "business"]})
    res1 = client.get(f"/feed?device_id={device_id}")
    assert res1.status_code == 200
    items1 = [item for item in res1.json()["items"] if item["id"] in target_ids]
    assert items1[0]["category"].lower() == "sports"

    # 2. Update order: technology first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["technology", "sports", "business"]})
    res2 = client.get(f"/feed?device_id={device_id}")
    assert res2.status_code == 200
    items2 = [item for item in res2.json()["items"] if item["id"] in target_ids]
    assert items2[0]["category"].lower() in ("tech", "technology")

    # 3. Update order: business first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["business", "technology", "sports"]})
    res3 = client.get(f"/feed?device_id={device_id}")
    assert res3.status_code == 200
    items3 = [item for item in res3.json()["items"] if item["id"] in target_ids]
    assert items3[0]["category"].lower() == "business"


def test_objective_score_calculation():
    """Verify objective scoring: impact keywords, source count, recency decay."""
    text_with_impact = "Chief Minister resigns following emergency cabinet meeting after election."
    assert count_impact_keywords(text_with_impact) == 3  # resigns, emergency, election

    text_no_impact = "Local football team prepares for summer tournament."
    assert count_impact_keywords(text_no_impact) == 0

    # Score calculation
    now = datetime.now(timezone.utc)
    score, hits = calculate_objective_score(
        articles=[],
        headline="Minister resigns",
        summary="A sudden emergency declaration was issued.",
        published_at=now,
    )
    assert hits == 2  # resigns, emergency
    assert score >= 4.0  # 2 * 2.0 = 4.0 minimum
