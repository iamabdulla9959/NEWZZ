import sys
sys.path.insert(0, "d:/News/apps/api")
sys.path.insert(0, "d:/News/apps/worker")
from dotenv import load_dotenv
load_dotenv("d:/News/.env")
from app.db import SessionLocal
from app.models import Card, ReviewQueueItem, StoryCluster
from sqlalchemy import func

session = SessionLocal()

print("=== 1. PUBLISHED CARDS BY CATEGORY ===")
published_by_cat = session.query(Card.category, func.count(Card.id)).filter(Card.verified_status == "published").group_by(Card.category).all()
for cat, cnt in published_by_cat:
    print(f"  {cat}: {cnt}")

print("\n=== 2. DETAILS OF NATIONAL & TECH CARDS ===")
cards = session.query(Card).filter(Card.category.in_(["national", "tech"])).all()
for c in cards:
    print(f"  - [{c.category.upper()}] Status: {c.verified_status} | Card ID: {c.id} | Cluster: {c.cluster_id}")
    print(f"    Headline: {c.headline}")
    print(f"    Published at: {c.published_at}")

print("\n=== 3. REVIEW QUEUE FOR NATIONAL & TECH ===")
nat_tech_card_ids = [c.id for c in cards]
recent_rq = session.query(ReviewQueueItem).filter(ReviewQueueItem.card_id.in_(nat_tech_card_ids)).all()
print(f"Review queue items associated with these cards: {len(recent_rq)}")
for r in recent_rq:
    print(f"  - RQ ID: {r.id} | Card ID: {r.card_id} | Reasons: {r.reasons} | ResolvedAt: {r.resolved_at}")

session.close()
