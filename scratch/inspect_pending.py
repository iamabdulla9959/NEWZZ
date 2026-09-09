import sqlite3

conn = sqlite3.connect("d:/News/newsreels.db")
c = conn.cursor()

c.execute("""
SELECT c.id, c.headline, c.summary, rq.reasons 
FROM cards c 
LEFT JOIN review_queue rq ON c.id = rq.card_id 
WHERE c.verified_status = 'pending_review' 
LIMIT 10
""")
rows = c.fetchall()
for r in rows:
    print("ID:", r[0])
    print("Headline:", r[1])
    print("Summary:", (r[2] or "")[:120])
    print("Reasons:", r[3])
    print("-" * 50)

c.execute("SELECT count(*) FROM cards WHERE summary != '' AND summary IS NOT NULL")
print("Cards with non-empty summary:", c.fetchone()[0])
c.execute("SELECT count(*) FROM cards WHERE summary = '' OR summary IS NULL")
print("Cards with EMPTY summary:", c.fetchone()[0])

conn.close()
