from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Card
from app.schemas import CardOut, CardSourceOut, FeedOut

router = APIRouter()


@router.get("/feed", response_model=FeedOut)
def get_feed(
    db: Session = Depends(get_db),
    categories: str | None = Query(default=None),
    district: str | None = Query(default=None),
    state: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
) -> FeedOut:
    query = db.query(Card).options(selectinload(Card.sources)).filter(Card.verified_status == "published")
    if categories:
        wanted = [c.strip() for c in categories.split(",") if c.strip()]
        if wanted:
            query = query.filter(Card.category.in_(wanted))
    if district:
        query = query.filter(Card.district == district)
    if state:
        query = query.filter(Card.state == state)
    total = query.count()
    rows = (
        query.order_by(Card.published_at.desc(), Card.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return FeedOut(items=[_to_out(c) for c in rows], offset=offset, limit=limit, total=total)


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
