import os
import json
import random
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app.db import SessionLocal
from app.models import Article, StoryCluster, Card, ReviewQueueItem

db = SessionLocal()

def extract_cluster(cluster):
    articles = db.query(Article).filter(Article.cluster_id == cluster.id).all()
    card = db.query(Card).filter(Card.cluster_id == cluster.id).first()
    return {
        "cluster_id": cluster.id,
        "eligible": cluster.eligible,
        "flagged_conflict": cluster.flagged_conflict,
        "conflict_notes": cluster.conflict_notes,
        "card": {
            "headline": card.headline,
            "summary": card.summary,
            "status": card.verified_status
        } if card else None,
        "articles": [
            {
                "title": a.title,
                "text": a.raw_text,
                "source": a.source.name,
                "wire": getattr(a, "wire_attribution", None)
            } for a in articles
        ]
    }

published_cards = db.query(Card).filter(Card.verified_status == 'published').all()
pub_samples = random.sample(published_cards, min(30, len(published_cards)))
pub_data = [extract_cluster(c.cluster) for c in pub_samples if c.cluster]

ineligible = db.query(StoryCluster).filter(StoryCluster.eligible == False).all()
pending_cards = db.query(Card).filter(Card.verified_status == 'pending_review').all()
hold_samples = random.sample(ineligible, min(20, len(ineligible)))
hold_data = [extract_cluster(c) for c in hold_samples]
if pending_cards:
    pend_samples = random.sample(pending_cards, min(10, len(pending_cards)))
    hold_data.extend([extract_cluster(c.cluster) for c in pend_samples if c.cluster])

conflict = db.query(StoryCluster).filter(StoryCluster.flagged_conflict == True).all()
conf_samples = random.sample(conflict, min(10, len(conflict)))
conf_data = [extract_cluster(c) for c in conf_samples]

multi = []
for c in db.query(StoryCluster).all():
    if db.query(Article).filter(Article.cluster_id == c.id).count() >= 2:
        multi.append(c)

multi_samples = random.sample(multi, min(10, len(multi)))
multi_data = [extract_cluster(c) for c in multi_samples]

out = {
    "published": pub_data,
    "hold": hold_data,
    "conflict": conf_data,
    "multi": multi_data
}
with open("audit_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print({k: len(v) for k, v in out.items()})
