from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import Card, ReviewQueueItem

router = APIRouter(prefix="/admin")


def require_admin(
    x_admin_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    key: str | None = Query(default=None),
) -> str:
    import secrets
    admin_key = (settings.admin_api_key or "").strip()
    is_prod = (settings.app_env or "").lower() == "production"

    if is_prod and (not admin_key or admin_key == "change-me-local-only"):
        raise HTTPException(
            status_code=403,
            detail="Admin access disabled: secure admin key not configured",
        )

    if not admin_key:
        raise HTTPException(
            status_code=403,
            detail="Admin access disabled: secure admin key not configured",
        )

    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
        else:
            token = authorization.strip()
    elif x_admin_key:
        token = x_admin_key.strip()
    elif key and not is_prod:
        token = key.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Admin credentials required")
    if not secrets.compare_digest(token, admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    return token


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
        reasons = escape(", ".join(str(r) for r in (item.reasons or [])))
        sources = "".join(
            f"<li><a href='{escape(s.url, quote=True)}'>{escape(s.name)}</a></li>"
            for s in card.sources
        )
        rows.append(
            f"""
            <article style="border:1px solid #333;padding:16px;margin:12px 0;background:#111;color:#eee">
              <h2>{escape(card.headline)}</h2>
              <p><strong>Reasons:</strong> {reasons}</p>
              <p>{escape(card.summary)}</p>
              <ul>{sources}</ul>
              <pre style="white-space:pre-wrap;background:#000;padding:8px">{escape(item.source_excerpts)}</pre>
              <form method="post" action="/admin/review/{escape(item.id, quote=True)}/approve?key={escape(admin_key, quote=True)}">
                <button type="submit">Approve</button>
              </form>
              <form method="post" action="/admin/review/{escape(item.id, quote=True)}/reject?key={escape(admin_key, quote=True)}">
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
    item.card.newzz_published_at = datetime.now(timezone.utc)
    # Preserve original source published_at date; do not overwrite with now()
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
