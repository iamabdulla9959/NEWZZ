import sqlite3
import json

conn = sqlite3.connect("d:/News/newsreels.db")
c = conn.cursor()

c.execute("""
SELECT sc.id, count(a.id), max(s.category), max(s.name), max(a.title)
FROM story_clusters sc
JOIN articles a ON a.cluster_id = sc.id
JOIN sources s ON a.source_id = s.id
GROUP BY sc.id
HAVING count(a.id) >= 1
""")
rows = c.fetchall()
print(f"Total clusters with at least 1 article: {len(rows)}")

cats = {}
for r in rows:
    cat = r[2] or "unknown"
    cats[cat] = cats.get(cat, 0) + 1

print("Clusters by category:", cats)
conn.close()
