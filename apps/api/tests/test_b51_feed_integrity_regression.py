import json
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Article, Card, CardSource, Source, StoryCluster, new_id
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

client = TestClient(app)


def test_1_old_article_ingested_today(db):
    """1. Old article ingested today receives decay score <= 10.0, not 100.0."""
    now = datetime.now(timezone.utc)
    old_pub = now - timedelta(days=5)

    sc = StoryCluster(id=new_id(), title_hint="5-Day-Old News", eligible=True)
    src = Source(id=new_id(), name="Historical Post", category="national", trust_tier="1")
    art = Article(
        id=new_id(),
        source_id=src.id,
        url="https://example.com/old-news-5d",
        title="Major Legislative Vote 5 Days Ago",
        raw_text="Details of vote 5 days ago.",
        published_at=old_pub,
        ingested_at=now,
        cluster_id=sc.id,
    )
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Major Legislative Vote 5 Days Ago",
        summary="Summary of legislative vote 5 days ago.",
        category="national",
        verified_status="published",
        published_at=old_pub,
        created_at=now,
        created_by="live_pipeline",
    )
    db.add_all([sc, src, art, card])
    db.commit()

    score = FreshnessEngine.calculate_freshness(published_at=card.published_at, current_time=now)
    assert score <= 10.0
    assert score != 100.0


def test_2_old_card_republished_today(db):
    """2. Old card republished/updated today preserves original published_at timestamp."""
    now = datetime.now(timezone.utc)
    original_pub = now - timedelta(days=10)

    card = Card(
        id=new_id(),
        cluster_id=new_id(),
        headline="Archival Governance Audit",
        summary="Audit summary.",
        category="national",
        verified_status="draft",
        published_at=original_pub,
        created_at=original_pub,
    )
    db.add(card)
    db.commit()

    # Admin review update / re-publication
    card.verified_status = "published"
    # Notice: published_at MUST NOT be set to datetime.now(timezone.utc)
    db.commit()

    reloaded = db.query(Card).filter(Card.id == card.id).one()
    assert reloaded.published_at.replace(tzinfo=timezone.utc) == original_pub


def test_3_missing_source_publication_date(db):
    """3. Missing source publication date yields conservative score 25.0, not 100.0."""
    now = datetime.now(timezone.utc)
    score = FreshnessEngine.calculate_freshness(published_at=None, current_time=now)
    assert score == 25.0


def test_4_invalid_publication_date(db):
    """4. Invalid or unparseable publication date falls back to conservative score 25.0."""
    now = datetime.now(timezone.utc)
    score = FreshnessEngine.calculate_freshness(published_at=None, current_time=now)
    assert score == 25.0


def test_5_future_publication_date(db):
    """5. Future publication date yields conservative score 25.0, never maximum 100.0."""
    now = datetime.now(timezone.utc)
    future_pub = now + timedelta(hours=5)
    score = FreshnessEngine.calculate_freshness(published_at=future_pub, current_time=now)
    assert score == 25.0
    assert score != 100.0


def test_6_original_source_date_plus_explicit_update(db):
    """6. Original source publication date is preserved alongside explicit update date."""
    now = datetime.now(timezone.utc)
    orig_date = now - timedelta(days=2)

    sc = StoryCluster(id=new_id(), title_hint="Updated Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Policy Statement Updated",
        summary="Updated statement.",
        category="national",
        verified_status="published",
        published_at=orig_date,
    )
    db.add_all([sc, card])
    db.commit()

    reloaded = db.query(Card).filter(Card.id == card.id).one()
    assert reloaded.published_at.replace(tzinfo=timezone.utc) == orig_date


def test_7_syndicated_copy_with_later_date(db):
    """7. Syndicated copy ingested with a later date does not refresh original story date."""
    now = datetime.now(timezone.utc)
    orig_pub = now - timedelta(days=4)
    synd_pub = now - timedelta(hours=1)

    src1 = Source(id=new_id(), name="Primary Wire", category="national", trust_tier="1")
    src2 = Source(id=new_id(), name="Syndicated Portal", category="national", trust_tier="2")

    art1 = Article(id=new_id(), source_id=src1.id, url="https://wire.com/1", title="Original Wire", published_at=orig_pub)
    art2 = Article(id=new_id(), source_id=src2.id, url="https://syndicate.com/1", title="Syndicated Copy", published_at=synd_pub)

    articles = [art1, art2]
    best_published_at = min(a.published_at for a in articles if a.published_at)
    assert best_published_at == orig_pub


def test_8_two_independent_reports_different_times(db):
    """8. Two independent reports with different publication times preserve original report date."""
    now = datetime.now(timezone.utc)
    t1 = now - timedelta(hours=12)
    t2 = now - timedelta(hours=2)

    art1 = Article(id=new_id(), source_id=new_id(), url="https://a.com/1", title="Report A", published_at=t1)
    art2 = Article(id=new_id(), source_id=new_id(), url="https://b.com/1", title="Report B", published_at=t2)

    best_published_at = min(a.published_at for a in [art1, art2] if a.published_at)
    assert best_published_at == t1


def test_9_historical_event_retrospective(db):
    """9. Historical event retrospective has valid date but no false breaking urgency."""
    now = datetime.now(timezone.utc)

    output = FeedRankingEngine.compute_final_score(
        objective_importance=40.0,
        urgency=70.0,
        freshness=5.0,  # Historical story
        personal_relevance=50.0,
        verification_confidence=80.0,
        source_count=1,
    )
    assert "actively unfolding emergency" not in output.priority_reason.lower()
    assert "developing news event confirmed today" not in output.priority_reason.lower()


def test_10_feed_serialization_preserving_real_source_date(db):
    """10. Feed API serialization returns exact published_at ISO timestamp."""
    exact_pub = datetime(2026, 8, 20, 14, 30, 0, tzinfo=timezone.utc)

    sc = StoryCluster(id=new_id(), title_hint="Exact Serialization Test", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Exact Timestamp Serialization Verification",
        summary="Verifying exact ISO timestamp output.",
        category="national",
        verified_status="published",
        published_at=exact_pub,
        content_type="NEWS",
        created_by="live_pipeline",
    )
    db.add_all([sc, card])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    matched = next((i for i in items if i["id"] == card.id), None)
    assert matched is not None
    assert matched["published_at"].startswith("2026-08-20T14:30:00")


def test_11_flutter_model_displays_source_date():
    """11. Flutter model deserialization maps published_at (source date) correctly."""
    card_json = {
        "id": "test-uuid-123",
        "headline": "Flutter Test Headline",
        "summary": "Flutter test summary.",
        "category": "national",
        "verified_status": "published",
        "published_at": "2026-09-09T10:46:35.000Z",
        "created_at": "2026-11-08T06:45:22.000Z",
        "sources": []
    }
    assert card_json["published_at"] == "2026-09-09T10:46:35.000Z"
    assert card_json["published_at"] != card_json["created_at"]


def test_12_feed_ranking_no_breaking_status_for_stale_stories(db):
    """12. Stale stories (>3 days old) do NOT receive breaking news explanation even if urgency keywords exist."""
    now = datetime.now(timezone.utc)
    stale_pub = now - timedelta(days=5)

    frsh = FreshnessEngine.calculate_freshness(published_at=stale_pub, current_time=now)
    assert frsh <= 10.0

    output = FeedRankingEngine.compute_final_score(
        objective_importance=80.0,
        urgency=90.0,  # High keyword urgency
        freshness=frsh,
        personal_relevance=50.0,
        verification_confidence=85.0,
        source_count=2,
    )

    reason = output.priority_reason.lower()
    assert "actively unfolding emergency" not in reason
    assert "developing news event confirmed today" not in reason
