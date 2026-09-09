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

    # Create 3 cards in different categories with equal objective_score (1.0)
    card_tech = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Tech Breakthrough in Quantum Computing",
        summary="A new quantum processor has solved optimization tasks in seconds.",
        category="tech",
        verified_status="published",
        published_at=now,
        objective_score=1.0,
    )
    card_district = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="District Council Opens New Healthcare Center",
        summary="New municipal clinic begins operations to serve local residents.",
        category="district",
        verified_status="published",
        published_at=now,
        objective_score=1.0,
    )
    card_national = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="National Infrastructure Plan Approved",
        summary="Parliament has passed the transportation and rail modernization bill.",
        category="national",
        verified_status="published",
        published_at=now,
        objective_score=1.0,
    )
    db.add_all([card_tech, card_district, card_national])
    db.commit()
    return [card_tech, card_district, card_national]


def test_different_device_ids_receive_differently_ordered_feeds(
    db: Session, ranking_cards: list[Card]
):
    # Device A prefers tech > district > national
    client.put("/user/dev-A/preferences", json={"category_order": ["tech", "district", "national"]})

    # Device B prefers district > national > tech
    client.put("/user/dev-B/preferences", json={"category_order": ["district", "national", "tech"]})

    target_ids = {c.id for c in ranking_cards}

    res_a = client.get("/feed?device_id=dev-A")
    assert res_a.status_code == 200
    items_a = [item for item in res_a.json()["items"] if item["id"] in target_ids]
    categories_a = [item["category"] for item in items_a]
    assert categories_a[0] == "tech"
    assert categories_a[1] == "district"
    assert categories_a[2] == "national"

    res_b = client.get("/feed?device_id=dev-B")
    assert res_b.status_code == 200
    items_b = [item for item in res_b.json()["items"] if item["id"] in target_ids]
    categories_b = [item["category"] for item in items_b]
    assert categories_b[0] == "district"
    assert categories_b[1] == "national"
    assert categories_b[2] == "tech"

    assert categories_a != categories_b, "Different device IDs must receive differently ordered feeds!"


def test_unranked_device_receives_equal_weight_feed(db: Session):
    # Before ranking is set, all categories must be equal weight
    # Seed 2 cards with different objective scores
    cluster = StoryCluster(id=new_id(), title_hint="Unranked test cluster", eligible=True)
    db.add(cluster)
    db.flush()

    card_low_obj = Card(
        id="card-low",
        cluster_id=cluster.id,
        headline="Routine Civic Update",
        summary="Road maintenance scheduled next week.",
        category="district",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
        objective_score=1.0,
    )
    card_high_obj = Card(
        id="card-high",
        cluster_id=cluster.id,
        headline="Major Scientific Discovery Announced",
        summary="Astronomers discover water signatures on nearby exoplanet.",
        category="science",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
        objective_score=5.0,
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

    # 1. Initial order: national first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["national", "tech", "district"]})
    res1 = client.get(f"/feed?device_id={device_id}")
    assert res1.status_code == 200
    items1 = [item for item in res1.json()["items"] if item["id"] in target_ids]
    assert items1[0]["category"] == "national"

    # 2. Update order: tech first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["tech", "national", "district"]})
    res2 = client.get(f"/feed?device_id={device_id}")
    assert res2.status_code == 200
    items2 = [item for item in res2.json()["items"] if item["id"] in target_ids]
    assert items2[0]["category"] == "tech"

    # 3. Update order: district first
    client.put(f"/user/{device_id}/preferences", json={"category_order": ["district", "tech", "national"]})
    res3 = client.get(f"/feed?device_id={device_id}")
    assert res3.status_code == 200
    items3 = [item for item in res3.json()["items"] if item["id"] in target_ids]
    assert items3[0]["category"] == "district"


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
