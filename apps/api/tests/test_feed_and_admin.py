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



def test_etl_excludes_seed_cards_and_preserves_authentic_cards(tmp_path):
    import sqlite3
    from apps.api.scripts.etl_migrate_sqlite_to_pg import run_etl
    from alembic import command
    from alembic.config import Config
    from app.models import Card, Source, StoryCluster
    from sqlalchemy.orm import Session
    from app.db import create_db_engine

    src_file = tmp_path / "mock_src.db"
    dst_file = tmp_path / "mock_dst.db"
    
    # Setup source sqlite
    sconn = sqlite3.connect(src_file)
    sconn.execute("CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT, category TEXT, region TEXT, district TEXT, rss_url TEXT, trust_tier INTEGER, is_active INTEGER, source_type TEXT, verified_local_source INTEGER)")
    sconn.execute("CREATE TABLE story_clusters (id TEXT PRIMARY KEY, title_hint TEXT, eligible INTEGER, flagged_conflict INTEGER)")
    sconn.execute("CREATE TABLE articles (id TEXT PRIMARY KEY, source_id TEXT, url TEXT, title TEXT, raw_text TEXT, published_at TEXT, cluster_id TEXT, original_text TEXT, translated_text TEXT, original_language TEXT, translation_confidence REAL, wire_attribution TEXT, category TEXT, state TEXT, district TEXT)")
    sconn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, cluster_id TEXT, headline TEXT, summary TEXT, category TEXT, verified_status TEXT, district TEXT, state TEXT, created_by TEXT, published_at TEXT, verification_type TEXT, objective_score REAL, impact_keywords_count INTEGER, image_url TEXT, image_author TEXT, image_author_url TEXT, priority_score INTEGER, is_corrected INTEGER, correction_note TEXT, content_type TEXT, importance_score REAL, urgency_score REAL, freshness_score REAL, verification_score REAL, personal_relevance_score REAL, final_feed_score REAL, priority_reason TEXT)")
    sconn.execute("CREATE TABLE card_sources (id TEXT PRIMARY KEY, card_id TEXT, source_id TEXT, article_id TEXT, name TEXT, url TEXT, trust_tier INTEGER)")
    sconn.execute("CREATE TABLE user_preferences (id TEXT PRIMARY KEY, device_id TEXT, category_order TEXT)")
    sconn.execute("CREATE TABLE worker_runs (id TEXT PRIMARY KEY, provider TEXT, timestamp TEXT, sources_polled INTEGER, articles_ingested INTEGER, credits_used INTEGER, errors TEXT, duration_seconds REAL)")

    sconn.execute("INSERT INTO sources VALUES ('src-1', 'Wire Wire', 'national', NULL, NULL, 'http://rss', 2, 1, 'rss', 0)")
    sconn.execute("INSERT INTO story_clusters VALUES ('clust-1', 'Title', 1, 0)")
    sconn.execute("INSERT INTO articles VALUES ('art-1', 'src-1', 'http://a1', 'Head', 'Body', '2026-09-01T00:00:00', 'clust-1', NULL, NULL, 'en', 1.0, NULL, 'national', NULL, NULL)")
    sconn.execute("INSERT INTO cards VALUES ('card-real', 'clust-1', 'Real News', 'Real Summary', 'national', 'published', NULL, NULL, 'website_scraping_bot', '2026-09-01T00:00:00', 'cross_verified', 80.0, 0, NULL, NULL, NULL, 5, 0, NULL, 'NEWS', 60.0, 40.0, 50.0, 90.0, 0.0, 65.0, '')")
    sconn.execute("INSERT INTO cards VALUES ('card-seed', 'clust-1', 'Demo News', 'Demo Summary', 'national', 'published', NULL, NULL, 'seed', '2026-09-01T00:00:00', 'cross_verified', 80.0, 0, NULL, NULL, NULL, 5, 0, NULL, 'NEWS', 60.0, 40.0, 50.0, 90.0, 0.0, 65.0, '')")
    sconn.execute("INSERT INTO card_sources VALUES ('cs-1', 'card-real', 'src-1', 'art-1', 'Wire Wire', 'http://a1', 2)")
    sconn.commit()
    sconn.close()

    # Migrate destination
    dst_url = f"sqlite:///{dst_file.as_posix()}"
    cfg = Config("apps/api/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", dst_url)
    command.upgrade(cfg, "head")

    # Run ETL pass 1
    stats1 = run_etl(str(src_file), target_db_url=dst_url)
    assert stats1["cards"] == 1
    assert stats1["skipped_seed_cards"] == 1

    d_eng = create_db_engine(dst_url)
    d_sess = Session(bind=d_eng)
    cards = d_sess.query(Card).all()
    assert len(cards) == 1
    assert cards[0].id == "card-real"

    # Run ETL pass 2 (Idempotency)
    stats2 = run_etl(str(src_file), target_db_url=dst_url)
    assert stats2["cards"] == 0
    d_sess.close()
    d_eng.dispose()


def test_feed_serialization_and_verification_with_sentinel_source(db):
    from packages.ranking_engine.verification_engine import VerificationEngine

    # Sentinel source
    sentinel = Source(
        id="00000000-0000-0000-0000-000000000000",
        name="Legacy Unresolved Provenance",
        category="unresolved",
        trust_tier="3",
        is_active=False,
    )
    t1_source = Source(
        id=new_id(),
        name="The Hindu",
        category="national",
        trust_tier="1",
        is_active=True,
    )
    t2_source = Source(
        id=new_id(),
        name="India Today",
        category="national",
        trust_tier="2",
        is_active=True,
    )
    clust1 = StoryCluster(id=new_id(), title_hint="T1 Story", eligible=True)
    clust2 = StoryCluster(id=new_id(), title_hint="T2 Story", eligible=True)
    clust3 = StoryCluster(id=new_id(), title_hint="Unresolved Story", eligible=True)

    # Card 1: Verified Tier 1
    c1 = Card(
        id=new_id(),
        cluster_id=clust1.id,
        headline="Tier 1 Major Diplomatic Update",
        summary="Major verified diplomatic breakthrough occurs.",
        category="National",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    # Card 2: Tier 2
    c2 = Card(
        id=new_id(),
        cluster_id=clust2.id,
        headline="Tier 2 Regional Economic Development",
        summary="Regional policy review commences.",
        category="National",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    # Card 3: Linked to Sentinel (e.g. scraped from web as livemint.com)
    c3 = Card(
        id=new_id(),
        cluster_id=clust3.id,
        headline="Unresolved Source Market Analysis",
        summary="Market analysis report published online.",
        category="National",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([sentinel, t1_source, t2_source, clust1, clust2, clust3, c1, c2, c3])
    db.flush()

    cs1 = CardSource(
        id=new_id(),
        card_id=c1.id,
        source_id=t1_source.id,
        name="The Hindu",
        url="https://thehindu.example/story",
        trust_tier="1",
    )
    cs2 = CardSource(
        id=new_id(),
        card_id=c2.id,
        source_id=t2_source.id,
        name="India Today",
        url="https://indiatoday.example/story",
        trust_tier="2",
    )
    # Unresolved card source: source_id is sentinel, original name is livemint.com, trust_tier is 3
    cs3 = CardSource(
        id=new_id(),
        card_id=c3.id,
        source_id="00000000-0000-0000-0000-000000000000",
        name="livemint.com",
        url="https://livemint.example/market",
        trust_tier="3",
    )
    db.add_all([cs1, cs2, cs3])
    db.commit()

    # Query Feed API
    response = client.get("/feed")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}

    # Verify Card 1 (Tier 1)
    item1 = items[c1.id]
    assert len(item1["sources"]) == 1
    assert item1["sources"][0]["name"] == "The Hindu"
    assert item1["sources"][0]["trust_tier"] == "1"
    assert item1["verification_score"] >= 88.0

    # Verify Card 2 (Tier 2)
    item2 = items[c2.id]
    assert len(item2["sources"]) == 1
    assert item2["sources"][0]["name"] == "India Today"
    assert item2["sources"][0]["trust_tier"] == "2"
    assert item2["verification_score"] == 70.0

    # Verify Card 3 (Unresolved Sentinel)
    item3 = items[c3.id]
    assert len(item3["sources"]) == 1
    assert item3["sources"][0]["source_id"] == "00000000-0000-0000-0000-000000000000"
    # Original publisher name is preserved, NOT overwritten with sentinel label
    assert item3["sources"][0]["name"] == "livemint.com"
    assert item3["sources"][0]["url"] == "https://livemint.example/market"
    assert item3["sources"][0]["trust_tier"] == "3"
    # Receives no credibility boost: score is baseline unconfirmed
    assert item3["verification_score"] <= 55.0
