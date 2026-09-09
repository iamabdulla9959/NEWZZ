import sys
import json
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "d:/News/apps/api")
sys.path.insert(0, "d:/News/apps/worker")
from dotenv import load_dotenv
load_dotenv("d:/News/.env")
from app.db import SessionLocal
from app.models import Card, ReviewQueueItem, StoryCluster, Article

session = SessionLocal()

cards = session.query(Card).filter(Card.category.in_(["national", "tech"])).all()

for i, c in enumerate(cards, 1):
    print(f"==================================================")
    print(f"CARD #{i}: [{c.category.upper()}] Status: {c.verified_status}")
    print(f"ID: {c.id}")
    print(f"Headline: {c.headline}")
    print(f"Summary:\n{c.summary}")
    
    # Review queue items
    rqs = session.query(ReviewQueueItem).filter(ReviewQueueItem.card_id == c.id).all()
    reasons = [r.reasons for r in rqs]
    print(f"\nFlagged Reasons: {reasons}")
    
    # Source articles in cluster
    cluster = session.query(StoryCluster).filter(StoryCluster.id == c.cluster_id).first()
    if cluster:
        articles = session.query(Article).filter(Article.cluster_id == cluster.id).all()
        print(f"\nCluster ID: {cluster.id} (Articles count: {len(articles)})")
        for j, a in enumerate(articles, 1):
            print(f"  --- Source {j}: {a.source.name if a.source else 'Unknown'} | Title: {a.title} ---")
            text = a.translated_text or a.raw_text or ""
            print(f"  Snippet: {text[:300]}...")
    print("\n")

session.close()
