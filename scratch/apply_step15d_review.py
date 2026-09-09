import sys
sys.path.insert(0, "d:/News/apps/api")
sys.path.insert(0, "d:/News/apps/worker")
from dotenv import load_dotenv
load_dotenv("d:/News/.env")
from app.db import SessionLocal
from app.models import Card, ReviewQueueItem
from datetime import datetime, timezone

session = SessionLocal()

# 1. Update Card #4 (Delhi building collapse) with resolved, verified text
c4 = session.query(Card).filter(Card.id == "3ed772c3-b090-4dfe-a123-038795618d3c").first()
if c4:
    c4.headline = "Delhi building collapse: 7 dead, officials suspended"
    c4.summary = (
        "A multi-storey building collapsed in Satya Niketan in southwest Delhi on Sunday. "
        "Rescue teams continued working at the site as the death toll rose to seven on Monday. "
        "Reports differ on the number of people hurt, as hospital staff received eleven patients in total, "
        "with three admitted for treatment and others declared dead. "
        "Five municipal officials were suspended, and police arrested the building owner in Rajasthan."
    )
    c4.verified_status = "published"
    c4.published_at = datetime.now(timezone.utc)
    print(f"Card {c4.id} updated with resolved discrepancy and marked published.")

# 2. Reject Card #5 (Satya Niketan duplicate with faulty '10 injured' claim and 'disaster' banned word)
c5 = session.query(Card).filter(Card.id == "a94cd4da-1310-428b-8ec1-6567b902a34d").first()
if c5:
    c5.verified_status = "rejected"
    print(f"Card {c5.id} set to rejected (factual error + duplicate of c4).")

# 3. Reject Card #3 (BRS duplicate with inaccurate headline calling MLC an MLA)
c3 = session.query(Card).filter(Card.id == "fcdeabc4-6b30-4562-bb9a-807c477f9d06").first()
if c3:
    c3.verified_status = "rejected"
    print(f"Card {c3.id} set to rejected (headline inaccuracy + duplicate of c1).")

session.commit()

# 4. Check new counts
from sqlalchemy import func
print("\n=== UPDATED PUBLISHED CARDS BY CATEGORY ===")
counts = session.query(Card.category, func.count(Card.id)).filter(Card.verified_status == "published").group_by(Card.category).all()
for cat, cnt in counts:
    print(f"  {cat}: {cnt}")

total = session.query(func.count(Card.id)).filter(Card.verified_status == "published").scalar()
print(f"Total Published: {total}")

session.close()
