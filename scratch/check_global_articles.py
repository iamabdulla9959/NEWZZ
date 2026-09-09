import sqlite3

conn = sqlite3.connect("d:/News/newsreels.db")
c = conn.cursor()

c.execute("""
SELECT a.id, a.title, a.raw_text, s.name, s.category, a.url
FROM articles a
JOIN sources s ON a.source_id = s.id
WHERE s.category IN ('international', 'tech', 'science')
LIMIT 10
""")
rows = c.fetchall()
for r in rows:
    print(f"[{r[4]}] {r[3]}: {r[1]}")
    text = (r[2] or "").replace("\n", " ").strip()
    print(f"   Excerpt: {text[:150]}...")
    print(f"   URL: {r[5]}")
    print()

conn.close()
