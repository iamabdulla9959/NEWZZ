"""
B15.6 Capacity & 28-State Coverage Requirements Audit Script
"""
import sys
import os
import json
import httpx
from pathlib import Path
from collections import Counter, defaultdict

REPO_ROOT = Path("d:/News")
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "worker"))

from app.db import SessionLocal
from app.models import Card, Article, StoryCluster, ReviewQueueItem
from website_scraping.process_news import (
    load_articles_from_json,
    cluster_and_deduplicate,
    NEWS_JSON_PATH,
)
from website_scraping.auto_news_crawler import (
    INDIAN_STATES,
    INDIA_CATEGORIES,
    GLOBAL_CATEGORIES,
    GLOBAL_BASELINES,
)

API_URL = "http://127.0.0.1:8000"

PRIMARY_CATEGORIES = [
    "Technology",
    "Politics",
    "Business",
    "National",
    "World",
    "Science",
    "Health",
    "Sports",
    "Entertainment",
    "Environment",
]

def audit():
    print("=== 1. CURRENT DATABASE CAPACITY ===")
    db = SessionLocal()
    total_published = db.query(Card).filter(Card.verified_status == "published").count()
    total_articles = db.query(Article).count()
    total_clusters = db.query(StoryCluster).count()
    total_rq = db.query(ReviewQueueItem).count()

    cards = db.query(Card).filter(Card.verified_status == "published").all()
    cat_counts = Counter((c.category or "other").lower() for c in cards)
    state_counts = Counter(c.state for c in cards)
    db.close()

    print(f"Total Published Reels: {total_published} (Target: 400, Gap: {400 - total_published})")
    print(f"Total Articles in DB: {total_articles}")
    print(f"Total Story Clusters in DB: {total_clusters}")
    print(f"Total Review Queue Items: {total_rq}")
    print("Category breakdown in DB:")
    for cat in PRIMARY_CATEGORIES + ["State", "Education", "Other"]:
        cnt = cat_counts.get(cat.lower(), 0)
        print(f"  {cat:15s}: {cnt:3d} (Gap to 40: {max(0, 40 - cnt)})")

    print("\n=== 2. RAW SOURCE CAPACITY ===")
    print(f"Configured Indian States: {len(INDIAN_STATES)} feeds")
    print(f"Configured India Category Feeds: {len(INDIA_CATEGORIES)} feeds: {list(INDIA_CATEGORIES.keys())}")
    print(f"Configured Global Category Feeds: {len(GLOBAL_CATEGORIES)} feeds: {list(GLOBAL_CATEGORIES.keys())}")
    print(f"Configured Global Baselines: {len(GLOBAL_BASELINES)} feeds: {list(GLOBAL_BASELINES.keys())}")

    # Inspect feeds.yaml
    with open(REPO_ROOT / "website_scraping" / "feeds.yaml", "r", encoding="utf-8") as f:
        yaml_text = f.read()
    print(f"feeds.yaml contains baseline feeds:\n{yaml_text.strip()}")

    # Raw articles in news.json
    raw_articles = []
    with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    raw_articles.append(json.loads(line.strip()))
                except Exception:
                    pass
    print(f"Articles currently collected in news.json: {len(raw_articles)}")

    raw_by_state = Counter(a.get("state") for a in raw_articles)
    raw_by_cat = Counter(str(a.get("category", "")).capitalize() for a in raw_articles)
    raw_by_source = Counter(a.get("source") for a in raw_articles)

    print(f"Distinct sources in news.json: {len(raw_by_source)}")

    valid_articles = load_articles_from_json(NEWS_JSON_PATH)
    clusters = cluster_and_deduplicate(valid_articles)
    print(f"Clusters formed from raw articles: {len(clusters)}")

    print("\n=== 3. 28-STATE COVERAGE AUDIT ===")
    state_audit_results = []
    for st in INDIAN_STATES:
        feed_conf = True
        st_raw = sum(1 for a in raw_articles if a.get("state") == st)
        st_valid = sum(1 for a in valid_articles if a.get("state") == st)
        st_clusters = sum(1 for c in clusters if c[0].get("state") == st)
        st_published = sum(1 for c in cards if c.state == st)
        
        # Test API filter
        try:
            resp = httpx.get(f"{API_URL}/feed?limit=50&state={httpx.URL('', params={'s': st}).params['s']}", timeout=5.0)
            api_ok = (resp.status_code == 200)
            items = resp.json().get("items", []) if api_ok else []
            relevant_items = sum(1 for it in items if it.get("state") == st)
        except Exception:
            api_ok = False
            relevant_items = 0

        status = "WORKING" if (st_published > 0 and relevant_items > 0) else "STARVED (0 Published Reels)"
        state_audit_results.append({
            "state": st,
            "feed_conf": feed_conf,
            "raw": st_raw,
            "valid": st_valid,
            "clusters": st_clusters,
            "published": st_published,
            "api_works": api_ok,
            "relevant_api_stories": relevant_items,
            "status": status,
        })
        print(f"{st:20s} | Raw: {st_raw:2d} | Valid: {st_valid:2d} | Clusters: {st_clusters:2d} | Pub: {st_published:2d} | API Rel: {relevant_items:2d} | {status}")

    print("\n=== 5. STATE FILTER TEST (ALL 28 STATES) ===")
    for st in INDIAN_STATES:
        resp = httpx.get(f"{API_URL}/feed?limit=50&state={httpx.URL('', params={'s': st}).params['s']}", timeout=5.0)
        items = resp.json().get("items", [])
        rel = [it for it in items if it.get("state") == st]
        nat = [it for it in items if not it.get("state")]
        unrel = [it for it in items if it.get("state") and it.get("state") != st]
        top3 = [it.get("headline", "")[:40] for it in items[:3]]
        print(f"{st:20s} | Total: {len(items):2d} | Relevant: {len(rel):2d} | National/None: {len(nat):2d} | Other States: {len(unrel):2d} | Top 3: {top3}")

    print("\n=== 6. CATEGORY CAPACITY AUDIT ===")
    cat_audit_results = []
    for cat in PRIMARY_CATEGORIES:
        raw_cnt = sum(1 for a in raw_articles if str(a.get("category", "")).lower() == cat.lower())
        valid_cnt = sum(1 for a in valid_articles if str(a.get("category", "")).lower() == cat.lower())
        cl_cnt = sum(1 for c in clusters if str(c[0].get("category", "")).lower() == cat.lower())
        pub_cnt = sum(1 for c in cards if (c.category or "").lower() == cat.lower())
        gap = max(0, 40 - pub_cnt)
        cat_audit_results.append({
            "category": cat,
            "raw": raw_cnt,
            "valid": valid_cnt,
            "clusters": cl_cnt,
            "published": pub_cnt,
            "gap": gap,
        })
        print(f"{cat:15s} | Raw: {raw_cnt:3d} | Valid: {valid_cnt:3d} | Clusters: {cl_cnt:3d} | Pub: {pub_cnt:2d} | Gap: {gap:2d}")

    print("\n=== 7. DUPLICATE / EVENT TEST ===")
    urls = [a.get("link") for a in raw_articles if a.get("link")]
    dup_urls = len(urls) - len(set(urls))
    titles = [a.get("title") for a in raw_articles if a.get("title")]
    dup_titles = len(titles) - len(set(titles))
    print(f"Raw URLs: {len(urls)} (Duplicates: {dup_urls})")
    print(f"Raw Titles: {len(titles)} (Duplicates: {dup_titles})")
    print(f"Clusters formed: {len(clusters)} from {len(valid_articles)} articles (Multi-source clusters: {sum(1 for c in clusters if len(c) > 1)})")

    print("\n=== 11. API CAPACITY ===")
    resp_limit_500 = httpx.get(f"{API_URL}/feed?limit=500", timeout=5.0)
    print(f"GET /feed?limit=500 status: {resp_limit_500.status_code}, returned: {len(resp_limit_500.json().get('items', []))}")
    resp_offset = httpx.get(f"{API_URL}/feed?offset=10&limit=10", timeout=5.0)
    print(f"GET /feed?offset=10&limit=10 status: {resp_offset.status_code}, returned: {len(resp_offset.json().get('items', []))}")

    # Save summary
    out = {
        "total_published": total_published,
        "total_articles": total_articles,
        "total_clusters": total_clusters,
        "total_rq": total_rq,
        "category_counts": dict(cat_counts),
        "state_counts": dict(state_counts),
        "state_audit": state_audit_results,
        "category_audit": cat_audit_results,
    }
    with open(REPO_ROOT / "scratch" / "b15_6_capacity_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\nAudit completed and saved to scratch/b15_6_capacity_summary.json")

if __name__ == "__main__":
    audit()
