import os
import pprint
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app.db import SessionLocal
from app.models import Article, StoryCluster, Card

db = SessionLocal()
print("Articles:", db.query(Article).count())
print("Clusters:", db.query(StoryCluster).count())

print("\nCluster Eligibility (eligible, flagged_conflict, count):")
import sqlalchemy as sa
res = db.query(StoryCluster.eligible, StoryCluster.flagged_conflict, sa.func.count(StoryCluster.id)).group_by(StoryCluster.eligible, StoryCluster.flagged_conflict).all()
pprint.pprint(res)

print("\nCards (verified_status, count):")
res = db.query(Card.verified_status, sa.func.count(Card.id)).group_by(Card.verified_status).all()
pprint.pprint(res)
