import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "d:/News/apps/api")
from app.db import SessionLocal  # type: ignore
from app.models import Article  # type: ignore

session = SessionLocal()
for a in session.query(Article).filter(Article.cluster_id.in_(["31050e53-29c2-4eaa-808a-713268f0d8f0", "88837dc6-2df1-4e5b-82bf-c021c58ced8a"])):
    print(f"=== {a.title} ({a.cluster_id}) ===")
    raw = a.raw_text or ""
    for word in ["trauma", "injured", "admission", "hospital", "dead", "toll", "survivor", "10", "6", "7"]:
        pos = 0
        found_cnt = 0
        while found_cnt < 3:
            idx = raw.lower().find(word, pos)
            if idx == -1:
                break
            snippet = raw[max(0, idx - 40):min(len(raw), idx + 140)].replace("\n", " ")
            print(f"  [{word}]: ...{snippet}...")
            pos = idx + len(word) + 40
            found_cnt += 1
session.close()
