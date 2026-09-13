"""
Sync and score all stories in summarized_news.json into the primary News Reels database (newsreels.db).
Ensures all categories are mapped cleanly and scored with the new Multi-Dimensional Ranking Engine.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
api_root = repo_root / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from app.db import SessionLocal
from app.models import Card, CardSource, StoryCluster
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

JSON_PATH = repo_root / "website_scraping" / "summarized_news.json"

CATEGORY_MAP = {
    "Anthropic": "technology",
    "AI": "technology",
    "Currency": "business",
    "Economic": "business",
    "Floods": "disaster",
    "Flood": "disaster",
    "Court": "politics",
    "Modi": "politics",
    "BRICS": "national",
}

def determine_category(title: str, orig_cat: str) -> str:
    title_lower = title.lower()
    if any(k in title_lower for k in ["anthropic", "ai ", "tech", "cyber", "software"]):
        return "technology"
    if any(k in title_lower for k in ["currency", "market", "economy", "bank", "trade"]):
        return "business"
    if any(k in title_lower for k in ["court", "high court", "minister", "parliament", "brics", "modi"]):
        return "politics"
    if any(k in title_lower for k in ["flood", "accident", "killed", "collision", "deaths", "cyclone"]):
        return "national" if "nepal" in title_lower else "state"
    c = (orig_cat or "national").strip().lower()
    if c in ["national", "state", "business", "technology", "politics", "science", "health", "sports", "entertainment"]:
        return c
    return "national"

def run_sync():
    if not JSON_PATH.exists():
        print(f"File not found: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        stories = json.load(f)

    print(f"Loaded {len(stories)} stories from {JSON_PATH}")
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    synced_count = 0
    try:
        for idx, s in enumerate(stories):
            headline = s.get("headline", "").strip()
            if not headline:
                continue

            # Check if card already exists by headline similarity
            existing = db.query(Card).filter(Card.headline == headline).first()
            category = determine_category(headline, s.get("category"))
            state_name = s.get("state")
            summary = s.get("summary") or headline

            # Parse or generate published_at
            pub_str = s.get("published_at")
            pub_dt = now
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pub_dt = now

            # Multi-Dimensional Scoring
            obj_dims, imp_score = ImportanceEngine.analyze_event_text(headline, summary, category)
            urg_score, _ = UrgencyEngine.calculate_urgency(headline, summary)
            frs_score = FreshnessEngine.calculate_freshness(published_at=pub_dt, current_time=now)

            # Sources count & verification
            sources = s.get("sources", [])
            src_objs = [{"name": src.get("name", "News Source"), "url": src.get("url", "")} for src in sources]
            ver_score, ver_meta = VerificationEngine.calculate_verification(src_objs, conflict_detected=False)
            t1_count = ver_meta.get("tier1_source_count", 0)

            rel_score = RelevanceEngine.calculate_relevance(
                story_category=category,
                story_state=state_name,
                story_district=None,
                user_state=None,
                user_district=None,
                user_category_order=[]
            )

            scoring_out = FeedRankingEngine.compute_final_score(
                objective_importance=imp_score,
                urgency=urg_score,
                freshness=frs_score,
                personal_relevance=rel_score,
                verification_confidence=ver_score,
                dimensions=obj_dims,
                source_count=len(sources),
                tier1_count=t1_count
            )
            final_score = scoring_out.final_feed_score
            reason = scoring_out.priority_reason

            if existing:
                card = existing
                card.category = category
                card.state = state_name
                card.objective_score = scoring_out.objective_importance
                card.importance_score = scoring_out.objective_importance
                card.urgency_score = scoring_out.urgency
                card.freshness_score = scoring_out.freshness
                card.verification_score = scoring_out.verification_confidence
                card.personal_relevance_score = scoring_out.personal_relevance
                card.final_feed_score = final_score
                card.priority_reason = reason
                card.impact_evidence = obj_dims.model_dump()
                card.verified_status = "published"
                card.content_type = "NEWS"
            else:
                sc = StoryCluster(
                    id=str(uuid.uuid4()),
                    title_hint=headline,
                    eligible=True,
                )
                db.add(sc)
                db.flush()

                card = Card(
                    id=str(uuid.uuid4()),
                    cluster_id=sc.id,
                    headline=headline,
                    summary=summary,
                    category=category,
                    state=state_name,
                    district=None,
                    created_at=now,
                    published_at=pub_dt,
                    verified_status="published",
                    content_type="NEWS",
                    objective_score=scoring_out.objective_importance,
                    importance_score=scoring_out.objective_importance,
                    urgency_score=scoring_out.urgency,
                    freshness_score=scoring_out.freshness,
                    verification_score=scoring_out.verification_confidence,
                    personal_relevance_score=scoring_out.personal_relevance,
                    final_feed_score=final_score,
                    priority_reason=reason,
                    impact_evidence=obj_dims.model_dump(),
                    created_by="ranking_sync"
                )
                db.add(card)
                db.flush()

                for src in sources:
                    cs = CardSource(
                        id=str(uuid.uuid4()),
                        card_id=card.id,
                        source_id=sc.id,
                        name=src.get("name", "Wire"),
                        url=src.get("url", "https://news.google.com"),
                        trust_tier="1" if any(t in str(src.get("name", "")).lower() for t in ["the hindu", "ndtv", "reuters", "pti", "ani"]) else "2",
                    )
                    db.add(cs)

            synced_count += 1

        # Step 2: Recalculate ALL published cards in newsreels.db using authoritative engine
        all_cards = db.query(Card).filter(Card.verified_status == "published").all()
        for c in all_cards:
            obj_dims, imp_score = ImportanceEngine.analyze_event_text(c.headline, c.summary, c.category)
            urg_score, _ = UrgencyEngine.calculate_urgency(c.headline, c.summary)
            pub_dt = c.published_at or c.created_at or now
            frs_score = FreshnessEngine.calculate_freshness(published_at=pub_dt, current_time=now)
            sources = c.sources or []
            src_objs = [{"name": s.name, "url": s.url, "tier": s.trust_tier} for s in sources]
            ver_score, ver_meta = VerificationEngine.calculate_verification(src_objs, conflict_detected=False)
            t1_count = ver_meta.get("tier1_source_count", 0)

            rel_score = RelevanceEngine.calculate_relevance(
                story_category=c.category,
                story_state=c.state,
                story_district=c.district,
                user_state=None,
                user_district=None,
                user_category_order=[]
            )

            scoring_out = FeedRankingEngine.compute_final_score(
                objective_importance=imp_score,
                urgency=urg_score,
                freshness=frs_score,
                personal_relevance=rel_score,
                verification_confidence=ver_score,
                dimensions=obj_dims,
                source_count=len(sources),
                tier1_count=t1_count
            )

            c.objective_score = scoring_out.objective_importance
            c.importance_score = scoring_out.objective_importance
            c.urgency_score = scoring_out.urgency
            c.freshness_score = scoring_out.freshness
            c.verification_score = scoring_out.verification_confidence
            c.personal_relevance_score = scoring_out.personal_relevance
            c.final_feed_score = scoring_out.final_feed_score
            c.priority_reason = scoring_out.priority_reason
            c.impact_evidence = obj_dims.model_dump()

        db.commit()
        print(f"Successfully synced & ranked {len(all_cards)} total published cards in newsreels.db.")
    finally:
        db.close()

if __name__ == "__main__":
    run_sync()
