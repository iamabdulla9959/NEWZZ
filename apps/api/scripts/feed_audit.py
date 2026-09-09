import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import Card
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

def run_audit(district="Mumbai", state="Maharashtra"):
    db = SessionLocal()
    
    query = (
        db.query(Card)
        .options(selectinload(Card.sources))
        .filter(
            Card.verified_status == "published",
            sa.or_(Card.created_by.is_(None), Card.created_by != "dev_testing"),
        )
    )
    
    location_boost_expr = 0.0
    if district:
        query = query.filter(
            sa.or_(
                Card.district == district,
                Card.district.is_(None),
            )
        )
        location_boost_expr += sa.case({district: 50.0}, value=Card.district, else_=0.0)
    if state:
        query = query.filter(
            sa.or_(
                Card.state == state,
                Card.state.is_(None),
            )
        )
        location_boost_expr += sa.case({state: 20.0}, value=Card.state, else_=0.0)
        
    final_score_expr = Card.objective_score + location_boost_expr
    query = query.order_by(
        final_score_expr.desc(),
        Card.published_at.desc(),
        Card.created_at.desc(),
    )
    
    results = query.limit(20).all()
    
    print(f"=== Top 20 Feed Audit (Mocking District: {district}, State: {state}) ===")
    local_count = 0
    national_count = 0
    total_words = 0
    promotional_count = 0
    
    for idx, c in enumerate(results):
        score = db.scalar(sa.select(final_score_expr).where(Card.id == c.id))
        is_local = (c.district == district) if district else False
        if is_local:
            local_count += 1
        else:
            national_count += 1
            
        word_count = len(str(c.summary).split())
        total_words += word_count
        
        if c.priority_score <= 2:
            promotional_count += 1
            
        print(f"Rank {idx+1} | Score {score:.1f} | Local: {is_local} | Prio: {c.priority_score} | Words: {word_count}")
        print(f"Headline: {c.headline}")
        print("-" * 50)
        
    avg_words = total_words / len(results) if results else 0
    print("\n--- Summary Statistics ---")
    print(f"Top 20 Local Matches: {local_count}")
    print(f"Top 20 National/Global: {national_count}")
    print(f"Average Summary Length: {avg_words:.1f} words")
    print(f"Promotional/Junk in Top 20: {promotional_count}")
    
    db.close()

if __name__ == "__main__":
    run_audit()
