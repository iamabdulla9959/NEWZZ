import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "d:/News/apps/api")
sys.path.insert(0, "d:/News/apps/worker")
from dotenv import load_dotenv
load_dotenv("d:/News/.env")

from app.db import SessionLocal
from app.models import Card
from worker.visuals import assign_card_visuals

session = SessionLocal()
cards = session.query(Card).filter(Card.verified_status == "published").all()
print(f"Backfilling visuals for {len(cards)} published cards...")

for c in cards:
    assign_card_visuals(c, session)
    print(f"[{c.category.upper()}] \"{c.headline[:40]}\"")
    if c.image_url:
        print(f"  -> Photo: {c.image_url[:55]}... | By: {c.image_author}")
    else:
        print("  -> [TYPOGRAPHY MODE] Sensitive or fallback (image_url=None)")

session.commit()
session.close()
print("Visual backfill complete!")
