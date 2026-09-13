"""
B15.6 CAPACITY VERIFICATION
Verifies: >= 400 published reels, >= 40 per primary category, all 28 states.
"""
import sys, os
from pathlib import Path

# Add monorepo to path
repo = Path(__file__).resolve().parent.parent
for d in [str(repo), str(repo / "apps" / "api")]:
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from dotenv import load_dotenv
    load_dotenv(repo / ".env")
except Exception:
    pass

import sqlite3, json

DB_PATH = repo / "newsreels.db"
PASS = True
FAILURES = []

def check(cond, msg):
    global PASS
    if not cond:
        PASS = False
        FAILURES.append(f"  FAIL: {msg}")
        print(f"  [FAIL] {msg}")
    else:
        print(f"  [PASS] {msg}")

print("=" * 70)
print("B15.6 CAPACITY VERIFICATION")
print("=" * 70)

if not DB_PATH.exists():
    print(f"ERROR: Database not found at {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# 1. Total published cards
cur.execute("SELECT count(*) FROM cards WHERE verified_status='published' AND content_type='NEWS'")
total = cur.fetchone()[0]
print(f"\n[1] TOTAL PUBLISHED REELS: {total}")
check(total >= 400, f"Total >= 400 (got {total})")

# 2. Per primary category
PRIMARY = ["Technology", "Politics", "Business", "National", "World",
           "Science", "Health", "Sports", "Entertainment", "Environment"]

print("\n[2] PRIMARY CATEGORY COUNTS (>= 40 each required):")
cur.execute(
    "SELECT lower(category), count(*) FROM cards WHERE verified_status='published' AND content_type='NEWS' GROUP BY lower(category)"
)
cat_rows = {r[0]: r[1] for r in cur.fetchall()}

# Print all categories in DB first
print(f"    All categories in DB: {dict(cat_rows)}")

for cat in PRIMARY:
    count = cat_rows.get(cat.lower(), 0)
    check(count >= 40, f"{cat} >= 40 (got {count})")

# 3. All 28 Indian states
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal",
]

print("\n[3] STATE COVERAGE (all 28 required):")
cur.execute(
    "SELECT state, count(*) FROM cards WHERE verified_status='published' AND content_type='NEWS' AND state IS NOT NULL GROUP BY state"
)
state_rows = {r[0]: r[1] for r in cur.fetchall()}
print(f"    States with data: {len(state_rows)} / 28")

for state in STATES:
    count = state_rows.get(state, 0)
    check(count > 0, f"{state} has state-specific reels (got {count})")

# 4. No duplicate IDs
cur.execute("SELECT id, count(*) FROM cards WHERE verified_status='published' GROUP BY id HAVING count(*) > 1")
dup_ids = cur.fetchall()
check(len(dup_ids) == 0, f"No duplicate card IDs (found {len(dup_ids)})")

# 5. No duplicate headlines
cur.execute("SELECT headline, count(*) FROM cards WHERE verified_status='published' GROUP BY lower(headline) HAVING count(*) > 1")
dup_headlines = cur.fetchall()
check(len(dup_headlines) <= 5, f"Minimal duplicate headlines (found {len(dup_headlines)}, <= 5 allowed)")

# 6. Canonical categories only
NON_CANONICAL = {"tech", "international", "intl", "india", "global", "world news", "economy", "climate"}
cur.execute("SELECT DISTINCT lower(category) FROM cards WHERE verified_status='published'")
db_cats = {r[0] for r in cur.fetchall()}
bad_cats = db_cats & NON_CANONICAL
check(len(bad_cats) == 0, f"All categories canonical (non-canonical found: {bad_cats})")

# 7. Valid timestamps
cur.execute(
    "SELECT count(*) FROM cards WHERE verified_status='published' AND (published_at IS NULL AND created_at IS NULL)"
)
missing_ts = cur.fetchone()[0]
check(missing_ts == 0, f"All published cards have timestamps (missing: {missing_ts})")

conn.close()

print("\n" + "=" * 70)
if PASS:
    print("B15.6 CAPACITY VERIFICATION: PASS")
else:
    print("B15.6 CAPACITY VERIFICATION: FAIL")
    print("\nFAILURES:")
    for f in FAILURES:
        print(f)
print("=" * 70)
sys.exit(0 if PASS else 1)
