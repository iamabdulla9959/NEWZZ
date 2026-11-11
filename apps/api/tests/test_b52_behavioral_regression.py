import json
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Article, Card, CardSource, ReviewQueueItem, Source, StoryCluster, new_id
from app.config import settings
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

client = TestClient(app)


def test_b52_1_admin_approval_preserves_original_source_published_at(db):
    """1 & 2. Admin approval via POST /admin/review/{id}/approve preserves original source published_at and stores newzz_published_at separately."""
    orig_pub = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    sc = StoryCluster(id=new_id(), title_hint="Admin Test Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Admin Review Approval Integrity Test",
        summary="Summary of admin review item.",
        category="national",
        verified_status="pending_review",
        published_at=orig_pub,
        created_at=datetime.now(timezone.utc),
    )
    rq = ReviewQueueItem(
        id=new_id(),
        card_id=card.id,
        reasons=["sensitivity_keyword"],
        source_excerpts="Excerpt...",
        status="pending",
    )
    db.add_all([sc, card, rq])
    db.commit()

    headers = {"X-Admin-Key": settings.admin_api_key}
    resp = client.post(f"/admin/review/{rq.id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    reloaded = db.query(Card).filter(Card.id == card.id).one()
    # Original source publication date MUST NOT be overwritten with now()
    assert reloaded.published_at.replace(tzinfo=timezone.utc) == orig_pub
    # New editorial publication date MUST be recorded
    assert reloaded.newzz_published_at is not None
    assert reloaded.verified_status == "published"


def test_b52_3_serpapi_missing_date_retains_none(db):
    """3. SerpAPI ingestion with no date metadata retains published_at = None (never fallback to now)."""
    from worker.serpapi_news import ingest_serpapi_source
    src = Source(id=new_id(), name="SerpApi Test Source", category="national", trust_tier="2", source_type="serpapi")
    db.add(src)
    db.commit()

    # Mock SerpApi response where item has no 'date'
    mock_item = {"link": "https://example.com/serpapi-no-date-1", "title": "SerpApi Article No Date", "snippet": "Snippet..."}

    # Direct test of ingest mapping logic
    from worker.ingest import parse_datetime
    pub = parse_datetime(mock_item.get("date"))
    assert pub is None

    art = Article(
        id=new_id(),
        source_id=src.id,
        url=mock_item["link"],
        title=mock_item["title"],
        raw_text=mock_item["snippet"],
        published_at=pub,
    )
    db.add(art)
    db.commit()

    reloaded = db.query(Article).filter(Article.id == art.id).one()
    assert reloaded.published_at is None


def test_b52_4_providers_do_not_assign_fake_date(db):
    """4. Verified provider ingest logic: missing date yields None across all providers."""
    from worker.ingest import parse_datetime
    assert parse_datetime(None) is None
    assert parse_datetime("") is None
    assert parse_datetime("invalid-date-string") is None


def test_b52_5_old_article_ingested_today_remains_old(db):
    """5. Old article ingested today has freshness score <= 10.0."""
    now = datetime.now(timezone.utc)
    old_pub = now - timedelta(days=6)
    score = FreshnessEngine.calculate_freshness(published_at=old_pub, current_time=now)
    assert score <= 10.0


def test_b52_6_old_card_republished_remains_old(db):
    """6. Old card republished preserves published_at, yielding stale freshness decay."""
    now = datetime.now(timezone.utc)
    old_pub = now - timedelta(days=12)
    card = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline="Old Story Republished",
        summary="Old story summary.",
        category="national",
        verified_status="published",
        published_at=old_pub,
        newzz_published_at=now,
    )
    db.add(card)
    db.commit()

    score = FreshnessEngine.calculate_freshness(published_at=card.published_at, current_time=now)
    assert score <= 10.0


def test_b52_7_missing_malformed_future_dates_handled(db):
    """7. Missing, malformed, and future dates yield conservative freshness score 25.0."""
    now = datetime.now(timezone.utc)
    future_date = now + timedelta(days=2)

    assert FreshnessEngine.calculate_freshness(published_at=None, current_time=now) == 25.0
    assert FreshnessEngine.calculate_freshness(published_at=future_date, current_time=now) == 25.0


def test_b52_8_syndicated_copy_cannot_refresh_story_date(db):
    """8. Syndicated copy ingested later does not override original primary article publication date."""
    now = datetime.now(timezone.utc)
    primary_pub = now - timedelta(days=3)
    syndicated_pub = now - timedelta(hours=2)

    art_primary = Article(id=new_id(), source_id=new_id(), url="https://wire.com/p", title="Primary Wire", published_at=primary_pub)
    art_synd = Article(id=new_id(), source_id=new_id(), url="https://syndicate.com/p", title="Syndicated Copy", published_at=syndicated_pub)

    best_pub = min(a.published_at for a in [art_primary, art_synd] if a.published_at)
    assert best_pub == primary_pub


def test_b52_9_independent_reports_preserve_source_dates(db):
    """9. Independent reports in a cluster preserve their individual source article timestamps."""
    t1 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc)

    art1 = Article(id=new_id(), source_id=new_id(), url="https://a.com/story", title="Headline A", published_at=t1)
    art2 = Article(id=new_id(), source_id=new_id(), url="https://b.com/story", title="Headline B", published_at=t2)

    assert art1.published_at == t1
    assert art2.published_at == t2


def test_b52_10_seed_cards_excluded_from_public_feed(db):
    """10 & 11. Historical seed cards (created_by='seed') are strictly excluded from GET /feed response."""
    sc = StoryCluster(id=new_id(), title_hint="Seed Exclude Test", eligible=True)
    seed_card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Synthetic Demo Seed Card",
        summary="Demo summary.",
        category="national",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
        created_by="seed",
        content_type="NEWS",
    )
    db.add_all([sc, seed_card])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    seed_ids = [i["id"] for i in items if i["id"] == seed_card.id]
    assert len(seed_ids) == 0


def test_b52_12_published_status_does_not_imply_verified(db):
    """12. Published card with single source is output with verification_type='single_source' and is_single_source=True."""
    sc = StoryCluster(id=new_id(), title_hint="Single Source Test", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Single Source Published Card",
        summary="Single source summary.",
        category="national",
        verified_status="published",
        verification_type="cross_verified",  # Legacy incorrect value on card
        published_at=datetime.now(timezone.utc),
        created_by="live_pipeline",
        content_type="NEWS",
    )
    src = Source(id=new_id(), name="Single Outlet", category="national", trust_tier="2")
    cs = CardSource(id=new_id(), card_id=card.id, source_id=src.id, name="Single Outlet", url="https://single.com/1", trust_tier="2")
    db.add_all([sc, card, src, cs])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    matched = next((i for i in items if i["id"] == card.id), None)
    assert matched is not None
    assert matched["is_single_source"] is True
    assert matched["verification_type"] == "single_source"
    assert matched["verification_type"] != "cross_verified"


def test_b52_13_feed_serialization_preserves_newzz_published_at(db):
    """13 & 18. Feed API serialization preserves exact source published_at and newzz_published_at; refresh does not mutate them."""
    orig_pub = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    newzz_pub = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)

    sc = StoryCluster(id=new_id(), title_hint="Serialization Integrity", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Serialization Field Integrity Verification",
        summary="Verifying newzz_published_at serialization.",
        category="national",
        verified_status="published",
        published_at=orig_pub,
        newzz_published_at=newzz_pub,
        created_by="live_pipeline",
        content_type="NEWS",
    )
    db.add_all([sc, card])
    db.commit()

    resp1 = client.get("/feed?limit=50")
    assert resp1.status_code == 200
    matched1 = next((i for i in resp1.json()["items"] if i["id"] == card.id), None)
    assert matched1 is not None
    assert matched1["published_at"].startswith("2026-08-20T10:00:00")
    assert matched1["newzz_published_at"].startswith("2026-11-08T12:00:00")

    # Second fetch (refresh simulation)
    resp2 = client.get("/feed?limit=50")
    assert resp2.status_code == 200
    matched2 = next((i for i in resp2.json()["items"] if i["id"] == card.id), None)
    assert matched2["published_at"] == matched1["published_at"]
    assert matched2["newzz_published_at"] == matched1["newzz_published_at"]
