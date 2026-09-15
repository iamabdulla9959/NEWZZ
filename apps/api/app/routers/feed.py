import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

# Ensure repo root is available
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.db import get_db
from app.models import Card, UserPreferences, new_id
from app.schemas import (
    CardOut,
    CardSourceOut,
    FeedOut,
    UserPreferencesIn,
    UserPreferencesOut,
)

router = APIRouter()


@router.get("/feed", response_model=FeedOut)
def get_feed(
    db: Session = Depends(get_db),
    categories: str | None = Query(default=None),
    category: str | None = Query(default=None),
    district: str | None = Query(default=None),
    state: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> FeedOut:
    if not categories and category:
        categories = category

    # Canonical category and synonyms mapping to guarantee matching across all DB conventions
    _CAT_SYNONYMS = {
        "tech": ["tech", "technology"],
        "technology": ["tech", "technology"],
        "international": ["international", "world", "global"],
        "world": ["world", "international", "global"],
        "global": ["world", "international", "global"],
        "national": ["national", "india"],
        "politics": ["politics", "political"],
        "business": ["business", "economy", "finance"],
        "science": ["science", "space"],
        "health": ["health", "medical"],
        "sports": ["sports", "sport"],
        "entertainment": ["entertainment", "cinema", "movies", "culture"],
        "environment": ["environment", "climate", "nature"],
        "state": ["state", "regional"],
        "education": ["education"],
    }

    def _canonicalize(cat: str) -> str:
        """Returns canonical category for any case-variant."""
        syns = _CAT_SYNONYMS.get(cat.strip().lower())
        if syns:
            return syns[0].capitalize()
        return cat.strip().capitalize()

    def _build_query(wanted_cats: list[str]):
        q = (
            db.query(Card)
            .options(selectinload(Card.sources))
            .filter(
                Card.verified_status == "published",
                sa.or_(Card.created_by.is_(None), Card.created_by != "dev_testing"),
                Card.content_type == "NEWS",
            )
        )
        if wanted_cats:
            # Robust case-insensitive match: expand every category with all synonyms
            lower_wanted = set()
            for c in wanted_cats:
                c_low = c.strip().lower()
                lower_wanted.add(c_low)
                for syn in _CAT_SYNONYMS.get(c_low, []):
                    lower_wanted.add(syn.lower())
            q = q.filter(sa.func.lower(Card.category).in_(list(lower_wanted)))

        # Location Filtering:
        # If user selects 'state' category tab, show news for their state (or state-neutral).
        is_strictly_state_cat = len(wanted_cats) == 1 and wanted_cats[0].lower() == "state"
        if state and is_strictly_state_cat:
            q = q.filter(
                sa.or_(
                    sa.func.lower(Card.state) == state.strip().lower(),
                    Card.state.is_(None)
                )
            )
        return q

    wanted = []
    if categories:
        raw_cats = [c.strip() for c in categories.split(",") if c.strip() and c.strip().lower() not in ("all",)]
        # Canonicalize each wanted category so filtering works against stored canonical values
        wanted = [_canonicalize(c) for c in raw_cats]
    
    is_strictly_state_cat = len(wanted) == 1 and wanted[0].lower() == "state"
    query = _build_query(wanted)
    fallback_used = False
    fallback_level = None

    # A selected category is an explicit user filter. Do not silently replace
    # an empty district feed with state or national stories; that makes the
    # category controls appear broken and mislabels the news being shown.

    # Retrieve user category preferences if device_id provided
    category_order: list[str] = []
    if device_id:
        pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
        if pref and pref.category_order:
            category_order = [str(c) for c in pref.category_order if c]

    # Fetch candidate cards matching baseline category and location constraints
    candidates = query.all()

    now = datetime.now(timezone.utc)
    from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
    from packages.ranking_engine.freshness_engine import FreshnessEngine
    from packages.ranking_engine.importance_engine import ImportanceEngine
    from packages.ranking_engine.relevance_engine import RelevanceEngine
    from packages.ranking_engine.urgency_engine import UrgencyEngine
    from packages.ranking_engine.verification_engine import VerificationEngine

    scored_cards: list[Card] = []
    seen_cluster_keys: dict[tuple[str, str], Card] = {}

    for card in candidates:
        # 1. Importance (0..100) - Dynamic contextual multi-dimensional evaluation
        dims, imp = ImportanceEngine.analyze_event_text(card.headline, card.summary, card.category)

        combined_text = f"{card.headline} {card.summary}".lower()
        # Lifestyle / culture / celebrity stories must never receive disaster-level importance
        if re.search(r"\b(museum|painting|exhibition|art gallery|celebrity|actor spotted|fashion show|red carpet)\b", combined_text):
            imp = min(imp, 30.0)

        # 2. Urgency (0..100) - Contextual real-world urgency
        urg, urg_reason = UrgencyEngine.calculate_urgency(card.headline, card.summary)
        
        # 3. Freshness (0..100) - Dynamic decay relative to request time
        pub_dt = card.published_at or card.created_at
        frsh = FreshnessEngine.calculate_freshness(published_at=pub_dt, current_time=now)
        
        # 4. Verification (0..100)
        ver = float(getattr(card, "verification_score", 0.0) or 0.0)
        sources_list = card.sources or []
        tier1_count = 0
        if ver <= 0.0:
            src_dicts = []
            for s in sources_list:
                is_t1 = s.trust_tier in ("1", "Tier 1")
                if is_t1:
                    tier1_count += 1
                src_dicts.append({"name": s.name, "tier": s.trust_tier})
            ver, _ = VerificationEngine.calculate_verification(src_dicts)
        else:
            tier1_count = sum(1 for s in sources_list if s.trust_tier in ("1", "Tier 1"))

        # 5. Personal Relevance (0..100) - Tailored to requesting user
        rel = RelevanceEngine.calculate_relevance(
            story_category=card.category,
            story_district=card.district,
            story_state=card.state,
            user_district=district,
            user_state=state,
            user_category_order=category_order,
        )

        # 6. Final Deterministic Multi-Dimensional Feed Score (0..100)
        scoring_out = FeedRankingEngine.compute_final_score(
            objective_importance=imp,
            urgency=urg,
            freshness=frsh,
            personal_relevance=rel,
            verification_confidence=ver,
            dimensions=dims,
            urgency_reason=urg_reason,
            source_count=len(sources_list),
            tier1_count=tier1_count,
        )

        # Attach computed dynamic attributes for serialization
        card.importance_score = scoring_out.objective_importance
        card.urgency_score = scoring_out.urgency
        card.freshness_score = scoring_out.freshness
        card.verification_score = scoring_out.verification_confidence
        card.personal_relevance_score = scoring_out.personal_relevance
        card.final_feed_score = scoring_out.final_feed_score
        card.priority_reason = scoring_out.priority_reason

        # Deduplicate per cluster and headline, keeping highest scoring representation
        cluster_key = (card.cluster_id, " ".join(card.headline.lower().split()))
        if cluster_key in seen_cluster_keys:
            if card.final_feed_score > seen_cluster_keys[cluster_key].final_feed_score:
                seen_cluster_keys[cluster_key] = card
        else:
            seen_cluster_keys[cluster_key] = card

    # Authoritative Final Ranking Order: user-state priority (if looking at state news), then final_feed_score DESC, published_at DESC, created_at DESC
    def _state_priority(c: Card) -> int:
        if state and c.state and c.state.strip().lower() == state.strip().lower():
            return 2  # exact state match
        if state and state.strip().lower() in ((c.headline or "") + " " + (c.district or "")).lower():
            return 1  # mentioned in headline or district
        return 0

    unique_rows = sorted(
        seen_cluster_keys.values(),
        key=lambda c: (
            _state_priority(c) if (is_strictly_state_cat or not wanted) else 0,
            c.final_feed_score,
            c.published_at.timestamp() if c.published_at else 0.0,
            c.created_at.timestamp() if c.created_at else 0.0,
        ),
        reverse=True,
    )

    total = len(unique_rows)
    rows = unique_rows[offset : offset + limit]
    empty_reason = "no_eligible_stories" if not rows and total == 0 else None
    return FeedOut(
        items=[_to_out(c) for c in rows], 
        offset=offset, 
        limit=limit, 
        total=total,
        fallback_used=fallback_used,
        fallback_level=fallback_level,
        empty_reason=empty_reason,
    )


@router.get("/user/{device_id}/preferences", response_model=UserPreferencesOut)
def get_user_preferences(device_id: str, db: Session = Depends(get_db)) -> UserPreferencesOut:
    pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
    if pref is None:
        return UserPreferencesOut(device_id=device_id, category_order=[])
    return UserPreferencesOut(
        device_id=pref.device_id,
        category_order=pref.category_order or [],
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


@router.put("/user/{device_id}/preferences", response_model=UserPreferencesOut)
def update_user_preferences(
    device_id: str,
    payload: UserPreferencesIn,
    db: Session = Depends(get_db),
) -> UserPreferencesOut:
    pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
    if pref is None:
        pref = UserPreferences(
            id=new_id(),
            device_id=device_id,
            category_order=payload.category_order,
        )
        db.add(pref)
    else:
        pref.category_order = payload.category_order
    db.commit()
    db.refresh(pref)
    return UserPreferencesOut(
        device_id=pref.device_id,
        category_order=pref.category_order or [],
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


@router.get("/card/{card_id}/sources", response_model=list[CardSourceOut])
def get_card_sources(card_id: str, db: Session = Depends(get_db)) -> list[CardSourceOut]:
    card = (
        db.query(Card)
        .options(selectinload(Card.sources))
        .filter(Card.id == card_id, Card.verified_status == "published")
        .one_or_none()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return [
        CardSourceOut(
            source_id=s.source_id,
            name=s.name,
            url=s.url,
            trust_tier=s.trust_tier,
        )
        for s in card.sources
    ]


def _to_out(card: Card) -> CardOut:
    return CardOut(
        id=card.id,
        headline=card.headline,
        summary=card.summary,
        category=card.category,
        verified_status=card.verified_status,
        verification_type=card.verification_type,
        created_at=card.created_at,
        published_at=card.published_at,
        district=card.district,
        state=card.state,
        objective_score=getattr(card, "objective_score", 0.0) or 0.0,
        priority_score=getattr(card, "priority_score", 5) or 5,
        importance_score=getattr(card, "importance_score", 0.0) or 0.0,
        urgency_score=getattr(card, "urgency_score", 0.0) or 0.0,
        freshness_score=getattr(card, "freshness_score", 0.0) or 0.0,
        verification_score=getattr(card, "verification_score", 0.0) or 0.0,
        personal_relevance_score=getattr(card, "personal_relevance_score", 0.0) or 0.0,
        final_feed_score=getattr(card, "final_feed_score", 0.0) or 0.0,
        priority_reason=getattr(card, "priority_reason", "") or "",
        impact_evidence=getattr(card, "impact_evidence", None),
        image_url=card.image_url,
        image_author=card.image_author,
        image_author_url=card.image_author_url,
        sources=[
            CardSourceOut(
                source_id=s.source_id,
                name=s.name,
                url=s.url,
                trust_tier=s.trust_tier,
            )
            for s in (card.sources or [])
        ],
    )
