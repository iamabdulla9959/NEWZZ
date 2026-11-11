import sys
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / ".env")

db_path = _repo_root / "newsreels.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# 1. Identify cards with synthetic boilerplate
cur.execute("""
    SELECT id, headline, summary, state, category, created_by 
    FROM cards 
    WHERE summary LIKE '%In a significant development%' 
       OR summary LIKE '%The dispatch highlights key operational developments%'
       OR summary LIKE '%Technical committees and administrative task forces%'
""")
fake_cards = cur.fetchall()
print(f"Total cards with synthetic boilerplate found in newsreels.db: {len(fake_cards)}")

# 2. Delete seed cards that are completely fake or obsolete
cur.execute("""
    DELETE FROM card_sources 
    WHERE card_id IN (
        SELECT id FROM cards 
        WHERE (created_by = 'seed' OR created_by = 'dev_testing')
          AND (summary LIKE '%In a significant development%' OR summary LIKE '%Technical committees%')
    )
""")
cur.execute("""
    DELETE FROM cards 
    WHERE (created_by = 'seed' OR created_by = 'dev_testing')
      AND (summary LIKE '%In a significant development%' OR summary LIKE '%Technical committees%')
""")
deleted_seed = cur.rowcount
print(f"Deleted {deleted_seed} obsolete seed cards with fake text.")

# 3. For any remaining live_pipeline cards with fake text, delete them so fresh ingestion repopulates them cleanly
cur.execute("""
    DELETE FROM card_sources 
    WHERE card_id IN (
        SELECT id FROM cards 
        WHERE summary LIKE '%In a significant development%' 
           OR summary LIKE '%The dispatch highlights key operational developments%'
           OR summary LIKE '%Technical committees and administrative task forces%'
    )
""")
cur.execute("""
    DELETE FROM cards 
    WHERE summary LIKE '%In a significant development%' 
       OR summary LIKE '%The dispatch highlights key operational developments%'
       OR summary LIKE '%Technical committees and administrative task forces%'
""")
deleted_fake = cur.rowcount
print(f"Deleted {deleted_fake} remaining cards with fake boilerplate.")

conn.commit()

# Check remaining count
cur.execute("SELECT count(*) FROM cards")
print("Remaining cards in newsreels.db:", cur.fetchone()[0])

conn.close()

