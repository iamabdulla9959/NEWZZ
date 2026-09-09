from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import Card

if TYPE_CHECKING:
    from app.models import Article

IMPACT_KEYWORDS = [
    "dies",
    "resigns",
    "law passed",
    "election",
    "market crash",
    "emergency",
]


def count_impact_keywords(text: str) -> int:
    """Counts matches of high-impact news keywords in text."""
    lower = text.lower()
    count = 0
    for kw in IMPACT_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lower):
            count += 1
    return count


def calculate_objective_score(
    articles: list[Article],
    headline: str = "",
    summary: str = "",
    published_at: datetime | None = None,
    gdelt_tone: float | None = None,
    current_time: datetime | None = None,
    priority_score: int = 5,
) -> tuple[float, int]:
    """Calculates objective score cached on Card at publish time.
    Formula components:
    1. Weighted source_count: rewards multi-source verification.
    2. GDELT tone / Goldstein extremity: measures event scale/volatility.
    3. Impact-keyword hits: detects breaking/civic consequence.
    4. LLM Priority Score: (priority_score - 5) * 2.0 (boosts 6-10, penalizes 1-4).
    5. Recency decay: exponential decay based on article publication age.

    Returns: (objective_score, impact_keyword_count)
    """
    # 1. Source count with trust tier weighting
    source_score = 0.0
    seen_sources: set[str] = set()
    for art in articles:
        src = getattr(art, "source", None)
        src_id = getattr(art, "source_id", None) or (src.id if src else None)
        if src_id and src_id not in seen_sources:
            seen_sources.add(src_id)
            trust = getattr(src, "trust_tier", "2") if src else "2"
            if str(trust) == "1" or str(trust) == "official_local":
                source_score += 1.5
            else:
                source_score += 1.0
    # Minimum 1.0 if sources present
    if not source_score and articles:
        source_score = 1.0

    # 2. Impact keyword count across headline, summary, and articles
    # IMPORTANT: For non-English sources, impact-keyword matching MUST run against
    # translated_text (or raw_text fallback for English sources), NEVER original_text (vernacular).
    article_texts: list[str] = []
    for a in articles:
        title = getattr(a, "title", None)
        if title:
            article_texts.append(title)
        # Use translated_text for non-English sources; fallback to raw_text for English sources.
        # Explicitly avoid original_text to ensure English impact keywords match properly.
        body_text = getattr(a, "translated_text", None) or getattr(a, "raw_text", "")
        if body_text:
            article_texts.append(body_text)

    all_text = f"{headline} {summary} " + " ".join(article_texts)
    impact_count = count_impact_keywords(all_text)
    impact_score = impact_count * 2.0

    # 3. GDELT tone extremity
    gdelt_score = 0.0
    if gdelt_tone is not None:
        gdelt_score = min(abs(float(gdelt_tone)) * 0.2, 3.0)

    # 4. LLM Priority Score (Exponential Boost)
    # A score of 10 gives a huge boost (+200), ensuring it stays at the top of the feed for hours despite recency decay.
    # A score of <=2 (promotional/junk) heavily penalizes the base score.
    if priority_score <= 2:
        priority_boost = -100.0
    else:
        priority_boost = (priority_score ** 2) * 2.0

    base_score = max(0.0, source_score + impact_score + gdelt_score + priority_boost)

    # 5. Recency decay (half life ~ 24h, decay parameter 0.028)
    now = current_time or datetime.now(timezone.utc)
    pub = published_at or now
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    hours_old = max(0.0, (now - pub).total_seconds() / 3600.0)
    recency_decay = math.exp(-0.028 * hours_old)

    final_objective_score = round(base_score * recency_decay, 3)
    return final_objective_score, impact_count


def recalculate_recent_cards_decay(
    db: Session,
    max_age_hours: int = 48,
    current_time: datetime | None = None,
) -> int:
    """Recalculates objective_score recency decay for published cards from the last max_age_hours.
    Capped to recent cards only — does not recompute scores for old/archived content.
    """
    now = current_time or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    cards = (
        db.query(Card)
        .filter(
            Card.verified_status == "published",
            Card.published_at.isnot(None),
            Card.published_at >= cutoff,
        )
        .all()
    )

    updated_count = 0
    for card in cards:
        articles = card.cluster.articles if card.cluster else []
        new_score, hits = calculate_objective_score(
            articles=articles,
            headline=card.headline,
            summary=card.summary,
            published_at=card.published_at,
            current_time=now,
            priority_score=getattr(card, "priority_score", 5),
        )
        card.objective_score = new_score
        card.impact_keywords_count = hits
        updated_count += 1

    if updated_count > 0:
        db.commit()

    return updated_count

