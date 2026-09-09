from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import Article, Card, Source, StoryCluster, new_id
from worker.scoring import (
    calculate_objective_score,
    count_impact_keywords,
    recalculate_recent_cards_decay,
)


def test_impact_keywords_uses_translated_text_not_original_text():
    """Confirms impact-keyword matching in scoring.py runs against translated_text,
    not original_text, for non-English sources.
    """
    # 1. Non-English article where original_text is Hindi and translated_text is English
    art_hindi = MagicMock(spec=Article)
    art_hindi.title = "ब्रेकिंग न्यूज"
    art_hindi.original_language = "hi"
    art_hindi.original_text = "मुख्यमंत्री ने दिया इस्तीफा और नई सरकार बनेगी।"  # Hindi for resigns
    art_hindi.translated_text = "Chief Minister resigns and new government will be formed."  # English translated
    art_hindi.raw_text = art_hindi.translated_text
    art_hindi.source = MagicMock(spec=Source, id="src-1", trust_tier="2")
    art_hindi.source_id = "src-1"

    score, hits = calculate_objective_score(
        articles=[art_hindi],
        headline="Cabinet Update",
        summary="Political developments continue.",
    )
    # 'resigns' keyword from translated_text MUST be matched
    assert hits == 1
    assert score >= 3.0  # 1.0 (source) + 2.0 (resigns impact hit)

    # 2. Article where original_text contains an impact keyword ('emergency') but translated_text does NOT
    # Demonstrates strictly that original_text is NEVER inspected
    art_no_match = MagicMock(spec=Article)
    art_no_match.title = "Local Administration Notice"
    art_no_match.original_language = "hi"
    art_no_match.original_text = "state of emergency mentioned in older quote"
    art_no_match.translated_text = "municipal guidelines issued for local festival"
    art_no_match.raw_text = art_no_match.translated_text
    art_no_match.source = MagicMock(spec=Source, id="src-2", trust_tier="2")
    art_no_match.source_id = "src-2"

    score2, hits2 = calculate_objective_score(
        articles=[art_no_match],
        headline="Festival Guidelines",
        summary="District issues standard advisory.",
    )
    # 'emergency' from original_text must NOT be counted
    assert hits2 == 0

    # 3. English source article with no translated_text (translated_text=None, raw_text has content)
    art_en = MagicMock(spec=Article)
    art_en.title = "Economic Report"
    art_en.original_language = "en"
    art_en.original_text = None
    art_en.translated_text = None
    art_en.raw_text = "Market crash triggers financial emergency declaration."
    art_en.source = MagicMock(spec=Source, id="src-3", trust_tier="2")
    art_en.source_id = "src-3"

    score3, hits3 = calculate_objective_score(
        articles=[art_en],
        headline="Markets Slide",
        summary="Stocks drop across exchanges.",
    )
    # 'market crash' and 'emergency' in raw_text must be matched
    assert hits3 == 2


def test_recalculate_recent_cards_decay(db: Session):
    """Verifies that objective_score recency decay is recalculated for published cards
    from the last 48 hours, while older/archived cards (>48h) or draft cards are untouched.
    """
    now = datetime.now(timezone.utc)
    cluster = StoryCluster(id=new_id(), title_hint="Recency Decay Cluster", eligible=True)
    source = Source(id=new_id(), name="National Herald", category="national", trust_tier="2")
    db.add_all([cluster, source])
    db.flush()

    art = Article(
        id=new_id(),
        source_id=source.id,
        url="https://example.com/decay-article",
        title="Major Political Update",
        raw_text="The prime minister resigns ahead of national election.",
        cluster_id=cluster.id,
    )
    db.add(art)
    db.flush()

    # Initial publish 12 hours ago (within 48h window)
    pub_12h = now - timedelta(hours=12)
    card_recent = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Prime Minister Resigns",
        summary="A resignation has been tendered before the upcoming election.",
        category="national",
        verified_status="published",
        published_at=pub_12h,
        objective_score=10.0,  # Initially frozen at publish time
        impact_keywords_count=2,
    )

    # Published 50 hours ago (beyond 48h cap)
    pub_50h = now - timedelta(hours=50)
    card_archived = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Archived Event",
        summary="Old summary from 50 hours ago.",
        category="national",
        verified_status="published",
        published_at=pub_50h,
        objective_score=9.99,  # Frozen score from past
        impact_keywords_count=1,
    )

    # Draft card (not published)
    card_draft = Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline="Draft Item",
        summary="Not yet published.",
        category="national",
        verified_status="draft",
        published_at=None,
        objective_score=0.0,
    )

    db.add_all([card_recent, card_archived, card_draft])
    db.commit()

    # Run recalculation
    updated = recalculate_recent_cards_decay(db, max_age_hours=48, current_time=now)
    assert updated >= 1  # Updates recent published cards including card_recent

    db.refresh(card_recent)
    db.refresh(card_archived)
    db.refresh(card_draft)

    # base_score = 1.0 (source) + 2*2.0 (resigns, election) + (5**2 * 2.0) = 55.0
    # decay = exp(-0.028 * 12) = ~0.7146
    # expected score = round(55.0 * 0.7146, 3) = ~39.304
    assert card_recent.objective_score < 55.0
    assert card_recent.objective_score == pytest.approx(39.304, abs=0.05)

    # card_archived must NOT have been modified
    assert card_archived.objective_score == 9.99

    # card_draft must NOT have been modified
    assert card_draft.objective_score == 0.0
