from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Card, CardSource, Source, StoryCluster, new_id

client = TestClient(app)


def test_provenance_verified_identity_and_direct_url(db):
    """Verified identity: publisher name matches and direct URL domain confirms publisher."""
    sc = StoryCluster(id=new_id(), title_hint="BBC Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="BBC Verified World Report",
        summary="Detailed world reporting from the BBC.",
        category="World",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    src = Source(
        id=new_id(),
        name="BBC World",
        category="World",
        rss_url="https://feeds.bbci.co.uk/news/world/rss.xml",
        trust_tier="1",
        is_active=True,
    )
    db.add_all([sc, card, src])
    db.flush()

    cs = CardSource(
        id=new_id(),
        card_id=card.id,
        source_id=src.id,
        name="BBC World",
        url="https://www.bbc.co.uk/news/articles/c3vgyn49y4l7o",
        trust_tier="1",
    )
    db.add(cs)
    db.commit()

    resp = client.get(f"/card/{card.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["url_type"] == "direct"
    assert data[0]["provenance_status"] == "verified_identity"
    assert data[0]["name"] == "BBC World"


def test_provenance_name_only_match_with_google_news_aggregator_url(db):
    """Name-only match: publisher name matches curated source, but URL is a Google News aggregator."""
    sc = StoryCluster(id=new_id(), title_hint="Reuters Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Reuters Global Market Summary",
        summary="Financial markets overview.",
        category="Business",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    src = Source(
        id=new_id(),
        name="Reuters",
        category="Business",
        rss_url="https://www.reutersagency.com/feed/",
        trust_tier="1",
        is_active=True,
    )
    db.add_all([sc, card, src])
    db.flush()

    cs = CardSource(
        id=new_id(),
        card_id=card.id,
        source_id=src.id,
        name="Reuters",
        url="https://news.google.com/rss/articles/CBMizwFBVV95cUxQaGZ1YUNPaWd4cjY0eGxDYmFJdWl",
        trust_tier="1",
    )
    db.add(cs)
    db.commit()

    resp = client.get(f"/card/{card.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    # Crucial: Aggregator URL must be classified as aggregator, never direct publisher link
    assert data[0]["url_type"] == "aggregator"
    # Cannot be upgraded to verified_identity without independent direct domain proof
    assert data[0]["provenance_status"] == "name_only_match"


def test_provenance_domain_conflict(db):
    """Domain conflict: direct URL domain directly contradicts the stated publisher name."""
    sc = StoryCluster(id=new_id(), title_hint="Conflicted Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Conflicted Source Report",
        summary="Summary of conflicted news.",
        category="National",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    src = Source(
        id=new_id(),
        name="Daily Pioneer",
        category="National",
        rss_url="https://www.dailypioneer.com/rss.xml",
        trust_tier="2",
        is_active=True,
    )
    db.add_all([sc, card, src])
    db.flush()

    # Direct URL points to BBC, but source name says Daily Pioneer
    cs = CardSource(
        id=new_id(),
        card_id=card.id,
        source_id=src.id,
        name="Daily Pioneer",
        url="https://www.bbc.co.uk/news/articles/conflict123",
        trust_tier="2",
    )
    db.add(cs)
    db.commit()

    resp = client.get(f"/card/{card.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["url_type"] == "direct"
    assert data[0]["provenance_status"] == "domain_conflict"


def test_provenance_unresolved_sentinel_publisher(db):
    """Unresolved sentinel: preserved with original name and cluster reference, flagged as unresolved."""
    sc = StoryCluster(id=new_id(), title_hint="Unresolved Scraped Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Scraped Tech Blog Headline",
        summary="Technical analysis of new hardware.",
        category="Technology",
        verified_status="published",
        published_at=datetime.now(timezone.utc),
    )
    db.add_all([sc, card])
    db.flush()

    cs = CardSource(
        id=new_id(),
        card_id=card.id,
        source_id="00000000-0000-0000-0000-000000000000",
        name="gadgets360.com",
        url="https://news.google.com",
        trust_tier="3",
    )
    db.add(cs)
    db.commit()

    # Check sources endpoint
    resp = client.get(f"/card/{card.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["provenance_status"] == "unresolved"
    assert data[0]["url_type"] == "aggregator"

    # Check feed endpoint
    feed_resp = client.get("/feed?categories=tech")
    assert feed_resp.status_code == 200
    feed_items = {i["id"]: i for i in feed_resp.json()["items"]}
    item = feed_items[card.id]
    assert item["sources"][0]["provenance_status"] == "unresolved"
    # Verification score must remain baseline without elevation
    assert item["verification_score"] <= 55.0


def test_editorial_trust_single_source_never_cross_verified(db):
    """Single-source story: even if database field previously held 'cross_verified', feed must report single_source."""
    sc = StoryCluster(id=new_id(), title_hint="Single Source Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Single Source National Report",
        summary="Reported by a single news agency.",
        category="National",
        verified_status="published",
        verification_type="cross_verified",  # Misleading DB value to be corrected
        published_at=datetime.now(timezone.utc),
    )
    src = Source(
        id=new_id(),
        name="The Hindu",
        category="National",
        rss_url="https://www.thehindu.com/news/national/feeder/default.rss",
        trust_tier="1",
        is_active=True,
    )
    db.add_all([sc, card, src])
    db.flush()

    cs = CardSource(
        id=new_id(),
        card_id=card.id,
        source_id=src.id,
        name="The Hindu",
        url="https://news.google.com/rss/articles/CBMi123",
        trust_tier="1",
    )
    db.add(cs)
    db.commit()

    resp = client.get("/feed?categories=national")
    assert resp.status_code == 200
    items = {i["id"]: i for i in resp.json()["items"]}
    item = items[card.id]
    assert item["is_single_source"] is True
    assert item["corroboration_count"] == 1
    assert item["verification_type"] == "single_source"


def test_editorial_trust_multi_source_distinct_corroboration(db):
    """Multi-source story: distinct authentic publishers corroborate the report."""
    sc = StoryCluster(id=new_id(), title_hint="Corroborated Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Summit Agreement Corroborated",
        summary="Two major outlets report the signed accord.",
        category="World",
        verified_status="published",
        verification_type="multi_source",
        published_at=datetime.now(timezone.utc),
    )
    s1 = Source(id=new_id(), name="The Hindu", category="World", trust_tier="1", is_active=True)
    s2 = Source(id=new_id(), name="BBC World", category="World", trust_tier="1", is_active=True)
    db.add_all([sc, card, s1, s2])
    db.flush()

    cs1 = CardSource(id=new_id(), card_id=card.id, source_id=s1.id, name="The Hindu", url="https://news.google.com/1", trust_tier="1")
    cs2 = CardSource(id=new_id(), card_id=card.id, source_id=s2.id, name="BBC World", url="https://news.google.com/2", trust_tier="1")
    db.add_all([cs1, cs2])
    db.commit()

    resp = client.get("/feed?categories=world")
    assert resp.status_code == 200
    items = {i["id"]: i for i in resp.json()["items"]}
    item = items[card.id]
    assert item["is_single_source"] is False
    assert item["corroboration_count"] == 2
    assert item["verification_type"] == "multi_source"


def test_editorial_trust_duplicate_source_names_do_not_inflate_corroboration(db):
    """Duplicate citations from same publisher (e.g. syndications) must not inflate corroboration count."""
    sc = StoryCluster(id=new_id(), title_hint="Syndicated Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Syndicated Economy Report",
        summary="Report syndicated across multiple feeds from one publisher.",
        category="Business",
        verified_status="published",
        verification_type="cross_verified",
        published_at=datetime.now(timezone.utc),
    )
    s = Source(id=new_id(), name="The Times of India", category="Business", trust_tier="2", is_active=True)
    db.add_all([sc, card, s])
    db.flush()

    cs1 = CardSource(id=new_id(), card_id=card.id, source_id=s.id, name="The Times of India", url="https://news.google.com/a", trust_tier="2")
    cs2 = CardSource(id=new_id(), card_id=card.id, source_id=s.id, name="The Times of India", url="https://news.google.com/b", trust_tier="2")
    db.add_all([cs1, cs2])
    db.commit()

    resp = client.get("/feed?categories=business")
    assert resp.status_code == 200
    items = {i["id"]: i for i in resp.json()["items"]}
    item = items[card.id]
    # Despite 2 CardSource rows, distinct publisher count is 1
    assert item["corroboration_count"] == 1
    assert item["is_single_source"] is True
    assert item["verification_type"] == "single_source"


def test_editorial_trust_unresolved_sentinel_does_not_corroborate(db):
    """An unresolved sentinel source cannot corroborate an authentic source to claim multi-source verification."""
    sc = StoryCluster(id=new_id(), title_hint="Mixed Provenance Story", eligible=True)
    card = Card(
        id=new_id(),
        cluster_id=sc.id,
        headline="Mixed Provenance Energy Report",
        summary="One authentic source and one unresolved blog.",
        category="National",
        verified_status="published",
        verification_type="cross_verified",
        published_at=datetime.now(timezone.utc),
    )
    s1 = Source(id=new_id(), name="The Hindu", category="National", trust_tier="1", is_active=True)
    db.add_all([sc, card, s1])
    db.flush()

    cs1 = CardSource(id=new_id(), card_id=card.id, source_id=s1.id, name="The Hindu", url="https://thehindu.example/energy", trust_tier="1")
    cs2 = CardSource(id=new_id(), card_id=card.id, source_id="00000000-0000-0000-0000-000000000000", name="randomblog.in", url="https://news.google.com", trust_tier="3")
    db.add_all([cs1, cs2])
    db.commit()

    resp = client.get("/feed?categories=national")
    assert resp.status_code == 200
    items = {i["id"]: i for i in resp.json()["items"]}
    item = items[card.id]
    # Unresolved sentinel is excluded from corroborating publishers
    assert item["corroboration_count"] == 1
    assert item["is_single_source"] is True
    assert item["verification_type"] == "single_source"

