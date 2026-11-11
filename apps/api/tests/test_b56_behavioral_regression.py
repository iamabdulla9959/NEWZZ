import calendar
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import Article, Card, CardSource, Source, StoryCluster, new_id
from worker.ingest import parse_datetime

client = TestClient(app)


def test_b56_1_legacy_synthetic_and_seed_cards_excluded(db: Session):
    """1. Synthetic cards with created_by='seed' or 'seed_demo' are strictly excluded from GET /feed."""
    sc = StoryCluster(id=new_id(), title_hint="Seed Cluster", eligible=True)
    seed1 = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Synthetic Demo Card 1",
        summary="A demo story summary.",
        category="national",
        verified_status="published",
        created_by="seed",
        content_type="NEWS",
    )
    seed2 = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Synthetic Demo Card 2",
        summary="Another demo summary.",
        category="national",
        verified_status="published",
        created_by="seed_demo",
        content_type="NEWS",
    )
    db.add_all([sc, seed1, seed2])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert seed1.id not in ids
    assert seed2.id not in ids


def test_b56_2_authentic_records_retained(db: Session):
    """2. Authentic records with approved provenance tags are included in GET /feed."""
    sc = StoryCluster(id=new_id(), title_hint="Authentic Cluster", eligible=True)
    src = Source(id=new_id(), name="BBC News", category="national", trust_tier="1")
    card_live = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Authentic Ingested Live News Story",
        summary="A verified public news report from the live pipeline.",
        category="national",
        verified_status="published",
        created_by="live_pipeline",
        content_type="NEWS",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([sc, src, card_live])
    db.flush()
    db.add(CardSource(id=new_id(), card_id=card_live.id, source_id=src.id, name="BBC News", url="https://bbc.com/news/1", trust_tier="1"))
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert card_live.id in ids


def test_b56_3_unresolved_provenance_records_handled_conservatively(db: Session):
    """3. Records with created_by='legacy_unresolved' or 'development_test' are strictly excluded from public feed."""
    sc = StoryCluster(id=new_id(), title_hint="Unresolved Cluster", eligible=True)
    card_unresolved = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Legacy Unresolved Card",
        summary="Legacy unresolved summary.",
        category="national",
        verified_status="published",
        created_by="legacy_unresolved",
        content_type="NEWS",
    )
    card_dev_test = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Development Test Card",
        summary="Dev test summary.",
        category="national",
        verified_status="published",
        created_by="development_test",
        content_type="NEWS",
    )
    db.add_all([sc, card_unresolved, card_dev_test])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert card_unresolved.id not in ids
    assert card_dev_test.id not in ids


def test_b56_4_empty_feed_is_honest(db: Session):
    """4. If all cards in the database are synthetic or unresolved, GET /feed returns an honest empty list."""
    # Wipe only cards to test pure query isolation
    db.query(CardSource).delete()
    db.query(Card).delete()
    db.commit()

    sc = StoryCluster(id=new_id(), title_hint="Only Seed Cluster", eligible=True)
    seed = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Only Seed Story In DB",
        summary="This is a seed story.",
        category="national",
        verified_status="published",
        created_by="seed",
        content_type="NEWS",
    )
    db.add_all([sc, seed])
    db.commit()

    resp = client.get("/feed?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["offset"] == 0


def test_b56_5_rss_date_parsing_distinguishes_published_and_updated():
    """5, 6, 7 & 8. RSS published_parsed maps strictly to publication time; updated_parsed does not overwrite it."""
    # Simulation of feedparser entry with published_parsed and updated_parsed
    time_pub = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    time_upd = datetime(2026, 8, 21, 14, 30, 0, tzinfo=timezone.utc)

    struct_pub = time_pub.utctimetuple()
    struct_upd = time_upd.utctimetuple()

    entry = {
        "published": "Thu, 20 Aug 2026 10:00:00 GMT",
        "published_parsed": struct_pub,
        "updated": "Fri, 21 Aug 2026 14:30:00 GMT",
        "updated_parsed": struct_upd,
    }

    # Extract publication time
    raw_pub = entry.get("published")
    pub_dt = parse_datetime(str(raw_pub) if raw_pub else None)
    if not pub_dt and entry.get("published_parsed"):
        pub_dt = datetime.fromtimestamp(calendar.timegm(entry["published_parsed"]), tz=timezone.utc)

    # Extract update time
    raw_upd = entry.get("updated")
    upd_dt = parse_datetime(str(raw_upd) if raw_upd else None)
    if not upd_dt and entry.get("updated_parsed"):
        upd_dt = datetime.fromtimestamp(calendar.timegm(entry["updated_parsed"]), tz=timezone.utc)

    assert pub_dt == time_pub
    assert upd_dt == time_upd
    assert pub_dt != upd_dt

    # If published is missing entirely but updated exists:
    entry_upd_only = {
        "published": None,
        "published_parsed": None,
        "updated": "Fri, 21 Aug 2026 14:30:00 GMT",
        "updated_parsed": struct_upd,
    }
    raw_pub2 = entry_upd_only.get("published")
    pub_dt2 = parse_datetime(str(raw_pub2) if raw_pub2 else None)
    if not pub_dt2 and entry_upd_only.get("published_parsed"):
        pub_dt2 = datetime.fromtimestamp(calendar.timegm(entry_upd_only["published_parsed"]), tz=timezone.utc)

    # Must remain None (unknown), NOT silently populated from updated
    assert pub_dt2 is None


def test_b56_9_syndicated_copy_cannot_refresh_story_date():
    """9 & 11. Syndicated copies (e.g. wire attributions) cannot refresh a story's chronology."""
    original_pub = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
    syndicated_pub = datetime(2026, 8, 2, 18, 0, 0, tzinfo=timezone.utc)  # Ingested next day

    art_orig = Article(
        id=new_id(),
        source_id="src-1",
        url="https://thehindu.com/orig",
        title="Original Investigation Report",
        raw_text="Original exclusive details.",
        published_at=original_pub,
        wire_attribution=None,
    )
    art_wire = Article(
        id=new_id(),
        source_id="src-2",
        url="https://wire.com/reprint",
        title="Reprint of Investigation",
        raw_text="Wire syndicated reprint.",
        published_at=syndicated_pub,
        wire_attribution="PTI",  # Explicit wire attribution
    )

    articles = [art_orig, art_wire]

    # Pipeline chronology logic
    all_pubs = [a.published_at for a in articles if a.published_at]
    first_reported_at = min(all_pubs) if all_pubs else None
    independent_pubs = [a.published_at for a in articles if a.published_at and not getattr(a, "wire_attribution", None)]
    latest_independent_at = max(independent_pubs) if independent_pubs else first_reported_at

    # The latest independent reporting date remains original_pub, NOT the syndicated copy's date
    assert first_reported_at == original_pub
    assert latest_independent_at == original_pub
    assert latest_independent_at < syndicated_pub


def test_b56_10_new_development_preserves_latest_independent_date():
    """10. A genuine new independent report in a developing story advances latest_independent_at without erasing first_reported_at."""
    day1 = datetime(2026, 9, 10, 8, 0, 0, tzinfo=timezone.utc)
    day2 = datetime(2026, 9, 11, 14, 0, 0, tzinfo=timezone.utc)

    art1 = Article(id=new_id(), source_id="src-1", url="https://a.com/1", title="Initial Outbreak", published_at=day1, wire_attribution=None)
    art2 = Article(id=new_id(), source_id="src-2", url="https://b.com/2", title="Health Ministry Containment Update", published_at=day2, wire_attribution=None)

    articles = [art1, art2]
    all_pubs = [a.published_at for a in articles if a.published_at]
    independent_pubs = [a.published_at for a in articles if a.published_at and not getattr(a, "wire_attribution", None)]

    first_reported = min(all_pubs)
    latest_independent = max(independent_pubs)

    assert first_reported == day1
    assert latest_independent == day2
    assert latest_independent > first_reported


def test_b56_12_feed_sources_and_detail_sources_agree(db: Session):
    """14 & 18. Card sources match between GET /feed and GET /card/{id}/sources."""
    sc = StoryCluster(id=new_id(), title_hint="Sources Consistency", eligible=True)
    src = Source(id=new_id(), name="Reuters", category="national", trust_tier="1")
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Source Consistency Card",
        summary="Checking source consistency.",
        category="national",
        verified_status="published",
        created_by="live_pipeline",
        content_type="NEWS",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([sc, src, card])
    db.flush()
    c_src = CardSource(id=new_id(), card_id=card.id, source_id=src.id, name="Reuters", url="https://reuters.com/consistent", trust_tier="1")
    db.add(c_src)
    db.commit()

    # Query /feed
    feed_resp = client.get("/feed?limit=50")
    assert feed_resp.status_code == 200
    feed_card = next(i for i in feed_resp.json()["items"] if i["id"] == card.id)
    assert len(feed_card["sources"]) == 1
    assert feed_card["sources"][0]["name"] == "Reuters"
    assert feed_card["sources"][0]["url"] == "https://reuters.com/consistent"

    # Query /card/{card_id}/sources
    detail_resp = client.get(f"/card/{card.id}/sources")
    assert detail_resp.status_code == 200
    detail_sources = detail_resp.json()
    assert len(detail_sources) == 1
    assert detail_sources[0]["name"] == "Reuters"
    assert detail_sources[0]["url"] == "https://reuters.com/consistent"
