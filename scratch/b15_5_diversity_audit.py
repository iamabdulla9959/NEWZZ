"""
B15.5 Candidate Pool & Feed Diversity Audit Script (READ-ONLY)
"""
import sys
import os
import json
import httpx
from pathlib import Path
from collections import Counter, defaultdict

# Paths
REPO_ROOT = Path("d:/News")
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "worker"))

from app.db import SessionLocal
from app.models import Card, Article, StoryCluster
from website_scraping.process_news import (
    load_articles_from_json,
    cluster_and_deduplicate,
    score_cluster_importance,
    NEWS_JSON_PATH,
)
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

def run_audit():
    print("=== 1. RAW INGESTION POOL ===")
    raw_articles = []
    missing_state = 0
    missing_category = 0
    missing_title = 0
    missing_url = 0
    with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                art = json.loads(line)
                raw_articles.append(art)
                if not art.get("state"):
                    missing_state += 1
                if not art.get("category"):
                    missing_category += 1
                if not art.get("title"):
                    missing_title += 1
                if not art.get("link"):
                    missing_url += 1
            except Exception:
                pass

    print(f"Total raw articles: {len(raw_articles)}")
    print(f"Missing state: {missing_state}")
    print(f"Missing category: {missing_category}")
    print(f"Missing title: {missing_title}")
    print(f"Missing URL: {missing_url}")

    raw_states = Counter(a.get("state") for a in raw_articles)
    raw_categories = Counter(a.get("category") for a in raw_articles)
    raw_sources = Counter(a.get("source") for a in raw_articles)

    print(f"State breakdown (top 15): {raw_states.most_common(15)}")
    print(f"Category breakdown: {raw_categories.most_common(15)}")

    # Valid articles after cleaning
    valid_articles = load_articles_from_json(NEWS_JSON_PATH)
    print(f"Valid articles after load_articles_from_json: {len(valid_articles)}")

    print("\n=== 2. CLUSTERING POOL & PRE-RANKING SELECTION ===")
    clusters = cluster_and_deduplicate(valid_articles)
    print(f"Total clusters formed: {len(clusters)}")

    cluster_states = Counter(c[0].get("state") for c in clusters)
    cluster_categories = Counter(str(c[0].get("category", "national")).lower() for c in clusters)

    print("Cluster state distribution (top 15):", cluster_states.most_common(15))
    print("Cluster category distribution:", cluster_categories.most_common(15))

    # Pre-ranking importance scoring
    ranked_clusters = []
    for c in clusters:
        imp_score, priority, kw_hits = score_cluster_importance(c)
        ranked_clusters.append({
            "cluster": c,
            "lead": c[0],
            "imp_score": imp_score,
            "priority": priority,
            "kw_hits": kw_hits,
            "state": c[0].get("state"),
            "category": str(c[0].get("category", "national")).lower(),
            "headline": c[0].get("title", ""),
        })

    ranked_clusters.sort(key=lambda x: x["imp_score"], reverse=True)

    # In run_pipeline, target_count = min(limit, len(ranked_clusters)) where limit=30
    survived_30 = ranked_clusters[:30]
    survived_states = Counter(x["state"] for x in survived_30)
    survived_categories = Counter(x["category"] for x in survived_30)

    print(f"\nTop 30 clusters survived pre-ranking selection:")
    print("Survived states:", dict(survived_states))
    print("Survived categories:", dict(survived_categories))

    # Database published cards
    db = SessionLocal()
    published_cards = db.query(Card).filter(Card.verified_status == "published").all()
    pub_states = Counter(c.state for c in published_cards)
    pub_categories = Counter(c.category for c in published_cards)
    db.close()

    print(f"\nPublished cards in DB: {len(published_cards)}")
    print("Published states:", dict(pub_states))
    print("Published categories:", dict(pub_categories))

    # State Diversity Loss Table
    target_states = [
        "Andhra Pradesh", "Karnataka", "Telangana", "Tamil Nadu",
        "Kerala", "Maharashtra", "Bihar", "Assam", "Madhya Pradesh"
    ]
    print("\n=== 4. STATE DIVERSITY LOSS ===")
    state_rows = []
    for st in target_states:
        c_count = sum(1 for c in clusters if c[0].get("state") == st)
        s_count = sum(1 for x in survived_30 if x["state"] == st)
        lost = c_count - s_count
        loss_pct = (lost / c_count * 100) if c_count > 0 else 0
        state_rows.append((st, c_count, s_count, lost, loss_pct))
        print(f"{st:18s} | Valid: {c_count:2d} | Survived: {s_count:2d} | Lost: {lost:2d} | Loss%: {loss_pct:5.1f}%")

    other_c = sum(1 for c in clusters if c[0].get("state") and c[0].get("state") not in target_states)
    other_s = sum(1 for x in survived_30 if x["state"] and x["state"] not in target_states)
    other_lost = other_c - other_s
    other_pct = (other_lost / other_c * 100) if other_c > 0 else 0
    print(f"{'Other Indian states':18s} | Valid: {other_c:2d} | Survived: {other_s:2d} | Lost: {other_lost:2d} | Loss%: {other_pct:5.1f}%")

    nat_c = sum(1 for c in clusters if not c[0].get("state"))
    nat_s = sum(1 for x in survived_30 if not x["state"])
    nat_lost = nat_c - nat_s
    nat_pct = (nat_lost / nat_c * 100) if nat_c > 0 else 0
    print(f"{'National/Global':18s} | Valid: {nat_c:2d} | Survived: {nat_s:2d} | Lost: {nat_lost:2d} | Loss%: {nat_pct:5.1f}%")

    print("\n=== 5. CATEGORY DIVERSITY LOSS ===")
    all_cats = [
        "technology", "politics", "business", "national", "international",
        "science", "health", "sports", "entertainment", "environment",
        "state", "education"
    ]
    cat_rows = []
    for cat in all_cats:
        c_count = sum(1 for c in clusters if str(c[0].get("category", "national")).lower() == cat)
        s_count = sum(1 for x in survived_30 if x["category"] == cat)
        lost = c_count - s_count
        loss_pct = (lost / c_count * 100) if c_count > 0 else 0
        cat_rows.append((cat, c_count, s_count, lost, loss_pct))
        print(f"{cat:15s} | Valid: {c_count:2d} | Survived: {s_count:2d} | Lost: {lost:2d} | Loss%: {loss_pct:5.1f}%")

    print("\n=== 6. IMPORTANCE BIAS TEST ===")
    selected = ranked_clusters[:30]
    discarded = ranked_clusters[30:]

    sel_imp = [x["imp_score"] for x in selected]
    disc_imp = [x["imp_score"] for x in discarded]

    print(f"Selected count: {len(selected)} | Avg Importance Score: {sum(sel_imp)/len(sel_imp):.2f}")
    print(f"Discarded count: {len(discarded)} | Avg Importance Score: {sum(disc_imp)/len(disc_imp):.2f}")

    # Inspect top 10 ranked clusters
    print("\nTop 10 Pre-ranking Clusters:")
    for i, x in enumerate(ranked_clusters[:10], 1):
        print(f"{i:2d}. [Score: {x['imp_score']:5.1f} | State: {str(x['state']):15s} | Cat: {x['category']:10s}] {x['headline'][:60]}")

    # Inspect Bihar article position
    print("\n=== 7. BIHAR VS NON-BIHAR TRACE ===")
    bihar_clusters = [x for x in ranked_clusters if x["state"] == "Bihar"]
    print(f"Bihar clusters found: {len(bihar_clusters)}")
    for b in bihar_clusters:
        rank_idx = ranked_clusters.index(b) + 1
        print(f"  Rank #{rank_idx} in pre-ranking: Score={b['imp_score']} | Title={b['headline'][:60]}")

    # Trace 10 non-Bihar articles from different states
    test_states_trace = ["Karnataka", "Andhra Pradesh", "Tamil Nadu", "Maharashtra", "Kerala", "Telangana", "Gujarat", "Rajasthan", "Punjab", "Odisha"]
    print("\nTracing 10 non-Bihar states:")
    for st in test_states_trace:
        st_clusters = [x for x in ranked_clusters if x["state"] == st]
        if st_clusters:
            top_st = st_clusters[0]
            rank_idx = ranked_clusters.index(top_st) + 1
            survived = rank_idx <= 30
            print(f"  {st:15s} | Best cluster rank: #{rank_idx:3d} (Score: {top_st['imp_score']:4.1f}) | Survived pre-ranking? {survived} | Title: {top_st['headline'][:50]}")
        else:
            print(f"  {st:15s} | No clusters found!")

    print("\n=== 10. COUNTERFACTUAL TEST ===")
    # Simulate final ranking for candidate pool sizes: 22, 50, 100, All
    # Using FeedRankingEngine formula
    def evaluate_candidates(c_list, user_state=None, user_cat_order=None):
        results = []
        for item in c_list:
            c = item["cluster"] if "cluster" in item else item
            lead = c[0]
            hl = lead.get("title", "")
            sum_text = lead.get("summary", "")
            cat = str(lead.get("category", "national")).lower()
            st = lead.get("state")
            
            # Dimensions & Importance
            dims, imp = ImportanceEngine.analyze_event_text(hl, sum_text, cat)
            urg, _ = UrgencyEngine.calculate_urgency(hl, sum_text)
            ver, _ = VerificationEngine.calculate_verification([{"name": a.get("source", ""), "tier": "2"} for a in c])
            rel = RelevanceEngine.calculate_relevance(
                story_category=cat,
                story_state=st,
                user_state=user_state,
                user_category_order=user_cat_order,
            )
            out = FeedRankingEngine.compute_final_score(
                objective_importance=imp,
                urgency=urg,
                freshness=25.0,
                personal_relevance=rel,
                verification_confidence=ver,
            )
            results.append({
                "headline": hl,
                "state": st,
                "category": cat,
                "final_score": out.final_feed_score,
                "importance": imp,
                "urgency": urg,
                "relevance": rel,
            })
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results

    pool_sizes = [22, 50, 100, len(ranked_clusters)]
    for ps in pool_sizes:
        subset = ranked_clusters[:ps]
        res = evaluate_candidates(subset)
        top10 = res[:10]
        top10_states = Counter(x["state"] for x in top10)
        top10_cats = Counter(x["category"] for x in top10)
        bihar_rank = next((idx + 1 for idx, x in enumerate(res) if x["state"] == "Bihar"), "N/A")
        print(f"\nPool size: {ps}")
        print(f"Top 10 States: {dict(top10_states)}")
        print(f"Top 10 Categories: {dict(top10_cats)}")
        print(f"Bihar flood rank: #{bihar_rank} (Score: {res[0]['final_score'] if res else 0})")
        print(f"Top 3 headlines:")
        for k, x in enumerate(top10[:3], 1):
            print(f"  {k}. [{x['state']} | {x['category']} | Score: {x['final_score']}] {x['headline'][:55]}")

    print("\n=== 8. PERSONALIZATION TEST (With all clusters vs current 22 pool) ===")
    users = [
        ("User A (AP)", "Andhra Pradesh", ["politics", "technology", "business", "national"]),
        ("User B (Karnataka)", "Karnataka", ["technology", "business", "politics", "national"]),
        ("User C (Bihar)", "Bihar", ["national", "politics", "technology", "business"]),
    ]
    for u_name, u_st, u_cats in users:
        print(f"\n--- {u_name} ---")
        # Current 22 pool
        res_current = evaluate_candidates(ranked_clusters[:22], user_state=u_st, user_cat_order=u_cats)
        user_st_count_current = sum(1 for x in res_current[:10] if x["state"] == u_st)
        print(f"With CURRENT 22 pool -> Top 10 has {user_st_count_current} stories from {u_st}")
        print(f"  Top 3 in current: {[x['headline'][:40] for x in res_current[:3]]}")
        
        # With ALL clusters
        res_all = evaluate_candidates(ranked_clusters, user_state=u_st, user_cat_order=u_cats)
        user_st_count_all = sum(1 for x in res_all[:10] if x["state"] == u_st)
        print(f"With ALL clusters pool -> Top 10 has {user_st_count_all} stories from {u_st}")
        print(f"  Top 3 with all: {[(x['state'], round(x['final_score'], 1), x['headline'][:40]) for x in res_all[:3]]}")

if __name__ == "__main__":
    run_audit()
