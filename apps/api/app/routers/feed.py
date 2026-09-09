from fastapi import APIRouter, Depends, HTTPException, Query
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

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
    district: str | None = Query(default=None),
    state: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=250),
) -> FeedOut:
    # Dev-testing cards (e.g. NewsAPI) must never appear in the production feed API by default
    query = (
        db.query(Card)
        .options(selectinload(Card.sources))
        .filter(
            Card.verified_status == "published",
            sa.or_(Card.created_by.is_(None), Card.created_by != "dev_testing"),
        )
    )
    if categories:
        wanted = [c.strip() for c in categories.split(",") if c.strip() and c.strip().lower() not in ("all", "global")]
        if wanted:
            query = query.filter(Card.category.in_(wanted))
    if district:
        query = query.filter(
            sa.or_(
                Card.district == district,
                Card.district.is_(None),
            )
        )
    if state:
        query = query.filter(
            sa.or_(
                Card.state == state,
                Card.state.is_(None),
            )
        )
    total = query.count()

    # Per-user priority ranking:
    # If device_id provided and has category_order, boost matching categories
    # Before any ranking is set (or if unranked), all selected categories have equal weight
    category_order: list[str] = []
    if device_id:
        pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
        if pref and pref.category_order:
            category_order = [str(c) for c in pref.category_order if c]

    location_boost_expr = 0.0
    if district:
        location_boost_expr += sa.case({district: 50.0}, value=Card.district, else_=0.0)
    if state:
        location_boost_expr += sa.case({state: 20.0}, value=Card.state, else_=0.0)

    if category_order:
        # Category weight boost: rank 0 gets highest boost, decreasing linearly
        whens = {
            cat: float(len(category_order) - idx) * 2.0
            for idx, cat in enumerate(category_order)
        }
        subj_boost_expr = sa.case(whens, value=Card.category, else_=0.0)
        final_score_expr = Card.objective_score + subj_boost_expr + location_boost_expr
        query = query.order_by(
            final_score_expr.desc(),
            Card.published_at.desc(),
            Card.created_at.desc(),
        )
    else:
        # Equal weight: ordered purely by priority, objective_score and location relevance
        final_score_expr = Card.objective_score + location_boost_expr
        query = query.order_by(
            final_score_expr.desc(),
            Card.published_at.desc(),
            Card.created_at.desc(),
        )

    rows = query.offset(offset).limit(limit).all()
    return FeedOut(items=[_to_out(c) for c in rows], offset=offset, limit=limit, total=total)


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
        objective_score=card.objective_score or 0.0,
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
            for s in card.sources
        ],
    )
