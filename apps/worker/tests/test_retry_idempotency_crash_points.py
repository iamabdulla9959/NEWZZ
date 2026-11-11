from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models import Article, Card, CardSource, IngestionLease, IngestionRequest, ReviewQueueItem, Source, StoryCluster, WorkerRun, new_id
from worker.coordination import (
    atomic_claim_request_with_lease,
    finish_request,
    recover_abandoned_requests,
    utc_now,
)
from worker.pipeline import process_eligible_clusters, cluster_unassigned_articles, evaluate_cluster


class MockDeterministicLLM:
    def complete_json(self, *args, **kwargs):
        return {
            "headline": "Idempotent Mission Success Confirmed",
            "summary": "Full verified summary of the mission milestone event.",
            "category": "national",
            "priority_score": 8,
            "content_type": "NEWS",
            "conflicts": [],
            "key_facts": ["Event confirmed", "Telemetric proof valid"],
        }
    def complete_text(self, *args, **kwargs):
        return '{"consistent": true}'


def _setup_two_independent_sources(db: Session) -> tuple[Source, Source]:
    s1 = Source(id=new_id(), name="The Hindu", category="national", trust_tier="1", is_active=True)
    s2 = Source(id=new_id(), name="BBC News", category="national", trust_tier="1", is_active=True)
    db.add(s1)
    db.add(s2)
    db.flush()
    return s1, s2


def test_crash_point_1_after_article_insertion(db: Session):
    """Crash Point 1: Worker crashes immediately after inserting Articles.
    Retry must not duplicate Articles (handled by uq_articles_url and conflict savepoints).
    """
    s1, s2 = _setup_two_independent_sources(db)
    u1, u2 = "https://example.com/crash-pt-1-a", "https://example.com/crash-pt-1-b"
    a1 = Article(
        id=new_id(),
        source_id=s1.id,
        url=u1,
        title="ISRO Launches Navigation Satellite Milestone",
        raw_text="ISRO space agency launched navigation satellite mission from Sriharikota spaceport successfully.",
        category="national",
    )
    a2 = Article(
        id=new_id(),
        source_id=s2.id,
        url=u2,
        title="ISRO Puts Navigation Satellite Into Orbit",
        raw_text="ISRO rocket mission carried navigation satellite into space successfully according to officials.",
        category="national",
    )
    db.add(a1)
    db.add(a2)
    
    # Request left stranded in 'running'
    past = utc_now() - timedelta(seconds=400)
    req = IngestionRequest(id=new_id(), status="running", trigger_origin="manual_api", attempt_count=1, started_at=past, last_heartbeat_at=past)
    db.add(req)
    db.commit()

    # Recovery
    recover_abandoned_requests(db, max_age_seconds=300)
    db.refresh(req)
    assert req.status == "pending"

    # New worker claims and executes
    worker2 = "worker-recovery-pt1"
    claimed, gen = atomic_claim_request_with_lease(db, worker_id=worker2)
    assert claimed is not None

    # Clustering and card publication
    cluster_unassigned_articles(db)
    for c in db.query(StoryCluster).all():
        evaluate_cluster(db, c)
    published = process_eligible_clusters(db, MockDeterministicLLM(), expected_lease_holder=worker2, expected_lease_generation=gen)
    assert len(published) >= 1

    finish_request(db, req.id, worker_id=worker2, status="succeeded", expected_generation=gen)

    # Invariants
    assert len(db.query(Article).filter(Article.url == u1).all()) == 1
    assert len(db.query(Article).filter(Article.url == u2).all()) == 1
    assert len(db.query(StoryCluster).all()) == 1
    assert len(db.query(Card).all()) == 1


def test_crash_point_2_after_story_cluster_creation(db: Session):
    """Crash Point 2: Worker crashes after creating StoryCluster and linking Articles.
    Retry must reuse existing StoryCluster rather than generating a duplicate.
    """
    s1, s2 = _setup_two_independent_sources(db)
    cluster = StoryCluster(id=new_id(), title_hint="Existing Cluster Milestone", eligible=True)
    db.add(cluster)
    a1 = Article(id=new_id(), source_id=s1.id, cluster_id=cluster.id, url="https://example.com/crash-pt-2-a", title="Milestone Hindu", raw_text="Telemetry.", category="national")
    a2 = Article(id=new_id(), source_id=s2.id, cluster_id=cluster.id, url="https://example.com/crash-pt-2-b", title="Milestone BBC", raw_text="Telemetry.", category="national")
    db.add(a1)
    db.add(a2)
    db.commit()

    # Second worker takes over
    worker2 = "worker-recovery-pt2"
    claimed, gen = atomic_claim_request_with_lease(db, worker_id=worker2)

    # Re-run clustering: articles are already clustered (cluster_id is not None)
    assigned = cluster_unassigned_articles(db)
    assert assigned == 0

    for c in db.query(StoryCluster).all():
        evaluate_cluster(db, c)
    published = process_eligible_clusters(db, MockDeterministicLLM(), expected_lease_holder=worker2, expected_lease_generation=gen)
    assert len(published) == 1

    assert len(db.query(StoryCluster).all()) == 1
    assert len(db.query(Card).all()) == 1


def test_crash_point_5_and_6_after_card_creation_or_publication(db: Session):
    """Crash Point 5/6: Worker crashes after Card is created/published, but before request completion.
    Retry must recognize existing card for cluster and NOT generate a duplicate Card.
    """
    s1, s2 = _setup_two_independent_sources(db)
    cluster = StoryCluster(id=new_id(), title_hint="Pre-published Card Event", eligible=True)
    db.add(cluster)
    a1 = Article(id=new_id(), source_id=s1.id, cluster_id=cluster.id, url="https://example.com/crash-pt-5-a", title="Pre-published Event A", raw_text="...", category="national")
    a2 = Article(id=new_id(), source_id=s2.id, cluster_id=cluster.id, url="https://example.com/crash-pt-5-b", title="Pre-published Event B", raw_text="...", category="national")
    db.add(a1)
    db.add(a2)
    card = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Idempotent Mission Success Confirmed",
        summary="Existing summary",
        category="national",
        verified_status="published",
    )
    db.add(card)
    cs1 = CardSource(id=new_id(), card_id=card.id, source_id=s1.id, article_id=a1.id, name=s1.name, url=a1.url, trust_tier="1")
    cs2 = CardSource(id=new_id(), card_id=card.id, source_id=s2.id, article_id=a2.id, name=s2.name, url=a2.url, trust_tier="1")
    db.add(cs1)
    db.add(cs2)
    db.commit()

    # Second worker takes over and processes clusters
    worker2 = "worker-recovery-pt5"
    claimed, gen = atomic_claim_request_with_lease(db, worker_id=worker2)

    # process_eligible_clusters checks for existing card on cluster
    new_published = process_eligible_clusters(db, MockDeterministicLLM(), expected_lease_holder=worker2, expected_lease_generation=gen)
    assert len(new_published) == 0, "Should skip existing card and produce 0 new cards"

    # Invariants
    assert len(db.query(Card).filter(Card.cluster_id == cluster.id).all()) == 1
    assert len(db.query(CardSource).filter(CardSource.card_id == card.id).all()) == 2


def test_crash_point_7_before_request_completion_committed(db: Session):
    """Crash Point 7: Cards published, but worker died before finish_request committed.
    Recovered worker finishes request without duplicating cards or clusters.
    """
    s1, s2 = _setup_two_independent_sources(db)
    cluster = StoryCluster(id=new_id(), title_hint="Crash At Finish Event", eligible=True)
    db.add(cluster)
    a1 = Article(id=new_id(), source_id=s1.id, cluster_id=cluster.id, url="https://example.com/crash-pt-7-a", title="Event A", raw_text="...", category="national")
    a2 = Article(id=new_id(), source_id=s2.id, cluster_id=cluster.id, url="https://example.com/crash-pt-7-b", title="Event B", raw_text="...", category="national")
    db.add(a1)
    db.add(a2)
    card = Card(id=new_id(), cluster_id=cluster.id, headline="Headline", summary="...", category="national", verified_status="published")
    db.add(card)

    past = utc_now() - timedelta(seconds=400)
    req = IngestionRequest(id=new_id(), status="running", trigger_origin="manual_api", attempt_count=1, started_at=past, last_heartbeat_at=past)
    db.add(req)
    db.commit()

    # Recovery
    recover_abandoned_requests(db, max_age_seconds=300)
    db.refresh(req)
    assert req.status == "pending"

    w2 = "worker-finisher"
    claimed, gen = atomic_claim_request_with_lease(db, worker_id=w2)
    assert claimed.id == req.id

    # Pipeline runs: sees card already published, does not duplicate
    process_eligible_clusters(db, MockDeterministicLLM(), expected_lease_holder=w2, expected_lease_generation=gen)

    # Finishes request cleanly
    res = finish_request(db, request_id=req.id, worker_id=w2, status="succeeded", expected_generation=gen)
    assert res is True

    db.refresh(req)
    assert req.status == "succeeded"
    assert len(db.query(Card).all()) == 1
    assert len(db.query(StoryCluster).all()) == 1
