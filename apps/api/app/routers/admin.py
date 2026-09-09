from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import Card, ReviewQueueItem

router = APIRouter(prefix="/admin")


def require_admin(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
) -> str:
    provided = x_admin_key or key
    if not provided or provided != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="admin key required")
    return provided


@router.get("/review", response_class=HTMLResponse)
def review_page(
    db: Session = Depends(get_db),
    admin_key: str = Depends(require_admin),
) -> str:
    items = (
        db.query(ReviewQueueItem)
        .options(selectinload(ReviewQueueItem.card).selectinload(Card.sources))
        .filter(ReviewQueueItem.status == "pending")
        .order_by(ReviewQueueItem.created_at.desc())
        .all()
    )
    rows = []
    for item in items:
        card = item.card
        reasons = ", ".join(str(r) for r in (item.reasons or []))
        sources = "".join(
            f"<li><a href='{s.url}'>{s.name}</a></li>" for s in card.sources
        )
        rows.append(
            f"""
            <article style="border:1px solid #333;padding:16px;margin:12px 0;background:#111;color:#eee">
              <h2>{card.headline}</h2>
              <p><strong>Reasons:</strong> {reasons}</p>
              <p>{card.summary}</p>
              <ul>{sources}</ul>
              <pre style="white-space:pre-wrap;background:#000;padding:8px">{item.source_excerpts}</pre>
              <form method="post" action="/admin/review/{item.id}/approve?key={admin_key}">
                <button type="submit">Approve</button>
              </form>
              <form method="post" action="/admin/review/{item.id}/reject?key={admin_key}">
                <button type="submit">Reject</button>
              </form>
            </article>
            """
        )
    body = "".join(rows) or "<p>Queue empty.</p>"
    return f"""<!doctype html>
    <html><head><title>News Reels review</title></head>
    <body style="font-family:sans-serif;background:#0b0f14;color:#eee;padding:24px">
      <h1>Review queue</h1>
      {body}
    </body></html>
    """


@router.post("/review/{item_id}/approve")
def approve(
    item_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict[str, str]:
    item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    item.status = "approved"
    item.resolved_at = datetime.now(timezone.utc)
    item.card.verified_status = "published"
    item.card.published_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "published", "card_id": item.card_id}


@router.post("/review/{item_id}/reject")
def reject(
    item_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict[str, str]:
    item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    item.status = "rejected"
    item.resolved_at = datetime.now(timezone.utc)
    item.card.verified_status = "rejected"
    item.card.published_at = None
    db.commit()
    return {"status": "rejected", "card_id": item.card_id}
