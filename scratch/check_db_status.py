import sqlite3
import json

conn = sqlite3.connect("d:/News/newsreels.db")
c = conn.cursor()

print("--- TABLE COUNTS ---")
for table in ["sources", "articles", "story_clusters", "cards", "review_queue", "card_sources"]:
    try:
        c.execute(f"SELECT count(*) FROM {table}")
        print(f"{table}: {c.fetchone()[0]}")
    except Exception as e:
        print(f"{table}: {e}")

print("\n--- CARDS BY STATUS & CATEGORY ---")
c.execute("SELECT verified_status, category, count(*) FROM cards GROUP BY verified_status, category")
for row in c.fetchall():
    print(row)

print("\n--- SAMPLE PENDING CARDS ---")
c.execute("SELECT id, headline, category, verified_status FROM cards WHERE verified_status = 'pending_review' LIMIT 5")
for row in c.fetchall():
    print(row)

print("\n--- SAMPLE PUBLISHED CARDS ---")
c.execute("SELECT id, headline, category, verified_status FROM cards WHERE verified_status = 'published'")
for row in c.fetchall():
    print(row)

conn.close()
