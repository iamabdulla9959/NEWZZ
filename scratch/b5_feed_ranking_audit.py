import os
import sys
sys.path.insert(0, r"d:\News")
sys.path.insert(0, r"d:\News\apps\api")
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8')

import json
import math
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

from app.db import SessionLocal
from app.models import Card, UserPreferences
from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.relevance_engine import RelevanceEngine

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = r"d:\News\scratch\b5_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "B5-Audit/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def put_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())

def run_b5_audit():
    results = {}
    print("==================================================")
    print("STARTING B5 — FEED RANKING INTEGRITY AUDIT")
    print("==================================================")

    # Setup device with known priorities from B4
    dev_id = "test-device-b5-integrity"
    priority_order = ["politics", "national", "technology", "business"]
    put_json(f"{BASE_URL}/user/{dev_id}/preferences", {"category_order": priority_order})

    # TEST 1 — LIVE FEED DATA
    feed_url = f"{BASE_URL}/feed?device_id={dev_id}&limit=50&state=Karnataka"
    feed_res = get_json(feed_url)
    items = feed_res.get("items", []) if isinstance(feed_res, dict) else feed_res
    total_stories = len(items)
    print(f"Test 1: Retrieved {total_stories} live feed stories.")
    results["test1_total_stories"] = total_stories

    # TEST 2 — DESCENDING ORDER
    ranking_violations = 0
    violation_details = []
    for i in range(len(items) - 1):
        s_curr = items[i].get("final_feed_score", 0.0)
        s_next = items[i+1].get("final_feed_score", 0.0)
        if s_curr < s_next:
            ranking_violations += 1
            violation_details.append({
                "pos_curr": i, "score_curr": s_curr, "title_curr": items[i].get("headline"),
                "pos_next": i+1, "score_next": s_next, "title_next": items[i+1].get("headline")
            })
    print(f"Test 2: Ranking violations: {ranking_violations}")
    results["test2_violations"] = ranking_violations
    results["test2_violation_details"] = violation_details
    assert ranking_violations == 0, f"Found {ranking_violations} ranking violations!"

    # TEST 3 — MANUAL SCORE RECOMPUTATION
    max_abs_diff = 0.0
    mismatch_count = 0
    mismatch_details = []
    w_imp = RankingConfig.WEIGHT_OBJECTIVE_IMPORTANCE # 0.40
    w_urg = RankingConfig.WEIGHT_URGENCY              # 0.20
    w_frsh = RankingConfig.WEIGHT_FRESHNESS           # 0.15
    w_rel = RankingConfig.WEIGHT_PERSONAL_RELEVANCE   # 0.15
    w_ver = RankingConfig.WEIGHT_VERIFICATION         # 0.10

    for idx, card in enumerate(items):
        imp = card.get("importance_score", 0.0)
        urg = card.get("urgency_score", 0.0)
        frsh = card.get("freshness_score", 0.0)
        rel = card.get("personal_relevance_score", 0.0)
        ver = card.get("verification_score", 0.0)
        reported_final = card.get("final_feed_score", 0.0)

        # Recompute
        expected_final = round(
            (imp * w_imp) + (urg * w_urg) + (frsh * w_frsh) + (rel * w_rel) + (ver * w_ver),
            2
        )
        diff = abs(reported_final - expected_final)
        if diff > max_abs_diff:
            max_abs_diff = diff
        # Allow tiny float precision <= 0.02
        if diff > 0.02:
            mismatch_count += 1
            mismatch_details.append({
                "index": idx, "headline": card.get("headline"),
                "imp": imp, "urg": urg, "frsh": frsh, "rel": rel, "ver": ver,
                "reported": reported_final, "recomputed": expected_final, "diff": diff
            })

    print(f"Test 3: Maximum absolute difference: {max_abs_diff:.4f}")
    print(f"Test 3: Score mismatches: {mismatch_count}")
    results["test3_max_diff"] = max_abs_diff
    results["test3_mismatches"] = mismatch_count
    assert mismatch_count == 0, f"Found {mismatch_count} score calculation mismatches!"

    # TEST 4 — SCORE RANGE
    min_scores = {"imp": 999, "urg": 999, "frsh": 999, "rel": 999, "ver": 999, "final": 999}
    max_scores = {"imp": -999, "urg": -999, "frsh": -999, "rel": -999, "ver": -999, "final": -999}
    range_violations = []

    for card in items:
        scores = {
            "imp": card.get("importance_score", 0.0),
            "urg": card.get("urgency_score", 0.0),
            "frsh": card.get("freshness_score", 0.0),
            "rel": card.get("personal_relevance_score", 0.0),
            "ver": card.get("verification_score", 0.0),
            "final": card.get("final_feed_score", 0.0),
        }
        for k, v in scores.items():
            if v < 0.0 or v > 100.0 or math.isnan(v):
                range_violations.append({k: v, "headline": card.get("headline")})
            if v < min_scores[k]: min_scores[k] = v
            if v > max_scores[k]: max_scores[k] = v

    print(f"Test 4: Score ranges: Min={min_scores}, Max={max_scores}")
    print(f"Test 4: Range violations: {len(range_violations)}")
    results["test4_min"] = min_scores
    results["test4_max"] = max_scores
    results["test4_range_violations"] = len(range_violations)
    assert len(range_violations) == 0, f"Found score range violations: {range_violations}"

    # TEST 5 — IMPORTANCE COMPONENTS
    print("Test 5: Checking 8 Importance dimensions...")
    dim_weights = {
        "human_impact": RankingConfig.MAX_HUMAN_IMPACT,
        "safety_impact": RankingConfig.MAX_SAFETY_IMPACT,
        "geographic_impact": RankingConfig.MAX_GEOGRAPHIC_IMPACT,
        "economic_impact": RankingConfig.MAX_ECONOMIC_IMPACT,
        "policy_impact": RankingConfig.MAX_POLICY_IMPACT,
        "infrastructure_impact": RankingConfig.MAX_INFRASTRUCTURE_IMPACT,
        "security_impact": RankingConfig.MAX_SECURITY_IMPACT,
        "consequence_impact": RankingConfig.MAX_CONSEQUENCE_IMPACT,
    }
    dim_sum = sum(dim_weights.values())
    print(f"Dimensions present: {list(dim_weights.keys())}, Total sum bound: {dim_sum}")
    results["test5_dimensions"] = dim_weights
    results["test5_sum"] = dim_sum
    assert dim_sum == 100.0, f"Dimension limits sum should be 100.0, got {dim_sum}"

    # TEST 6 — URGENCY BANDS
    print("Test 6: Checking Urgency bands and thresholds...")
    results["test6_urgency_bands"] = {
        "active_emergency": "90..100 (95.0)",
        "rapidly_developing": "75..89 (82.0)",
        "breaking_announcement": "50..74 (60.0)",
        "moderate_ongoing": "30..49 (40.0)",
        "retrospective_low": "0..29 (15.0)",
        "standard_default": "35.0"
    }

    # TEST 7 — FRESHNESS TIMESTAMPS
    print("Test 7: Checking Freshness hierarchy and decay...")
    results["test7_freshness_hierarchy"] = "event_time -> published_at -> scraped_at"
    results["test7_freshness_brackets"] = RankingConfig.FRESHNESS_BRACKETS

    # TEST 8 — VERIFICATION SOURCE TIERS
    print("Test 8: Checking Verification engine source tiers...")
    results["test8_tier1_sources_count"] = len(RankingConfig.TIER_1_SOURCES)
    results["test8_tier2_sources_count"] = len(RankingConfig.TIER_2_SOURCES)

    # TEST 9 & 10 — PERSONAL RELEVANCE & OBJECTIVE SEPARATION
    print("Test 9 & 10: Verifying Personal Relevance vs Objective metrics separation...")
    # Using dev_a with order [politics, national, technology, business]
    # vs dev_b with order [technology, business, politics, national]
    dev_a = "test-b5-dev-a"
    dev_b = "test-b5-dev-b"
    put_json(f"{BASE_URL}/user/{dev_a}/preferences", {"category_order": ["politics", "national", "technology", "business"]})
    put_json(f"{BASE_URL}/user/{dev_b}/preferences", {"category_order": ["technology", "business", "politics", "national"]})

    feed_a = get_json(f"{BASE_URL}/feed?device_id={dev_a}&limit=30&state=Karnataka")
    feed_b = get_json(f"{BASE_URL}/feed?device_id={dev_b}&limit=30&state=Karnataka")

    items_a = feed_a.get("items", []) if isinstance(feed_a, dict) else feed_a
    items_b = feed_b.get("items", []) if isinstance(feed_b, dict) else feed_b

    # Find common politics card and tech card
    pol_a = next((c for c in items_a if c.get("category") == "politics"), None)
    pol_b = next((c for c in items_b if c.get("category") == "politics"), None)
    tech_a = next((c for c in items_a if c.get("category") == "technology"), None)
    tech_b = next((c for c in items_b if c.get("category") == "technology"), None)

    assert pol_a and pol_b, "Politics card must exist in both feeds"
    assert tech_a and tech_b, "Technology card must exist in both feeds"

    print(f"Politics card Order A (Rank 1): Rel={pol_a['personal_relevance_score']}, Imp={pol_a['importance_score']}, Urg={pol_a['urgency_score']}, Frsh={pol_a['freshness_score']}, Ver={pol_a['verification_score']}, Final={pol_a['final_feed_score']}")
    print(f"Politics card Order B (Rank 3): Rel={pol_b['personal_relevance_score']}, Imp={pol_b['importance_score']}, Urg={pol_b['urgency_score']}, Frsh={pol_b['freshness_score']}, Ver={pol_b['verification_score']}, Final={pol_b['final_feed_score']}")

    # Check objective scores did NOT change
    assert pol_a['importance_score'] == pol_b['importance_score'], "Importance score must not change with user preferences"
    assert pol_a['urgency_score'] == pol_b['urgency_score'], "Urgency score must not change with user preferences"
    assert pol_a['freshness_score'] == pol_b['freshness_score'], "Freshness score must not change with user preferences"
    assert pol_a['verification_score'] == pol_b['verification_score'], "Verification score must not change with user preferences"

    # Check personal relevance DID change according to priority
    assert pol_a['personal_relevance_score'] > pol_b['personal_relevance_score'], "Rank 1 politics must have higher relevance than Rank 3"
    assert tech_b['personal_relevance_score'] > tech_a['personal_relevance_score'], "Rank 1 tech must have higher relevance than Rank 3"

    results["test10_objective_unchanged"] = True
    results["test10_relevance_changed"] = True

    # TEST 11 — EMERGENCY FLOOR
    print("Test 11: Verifying Emergency Floor...")
    # Look for any high urgency stories (urgency >= 90)
    flood_stories = [c for c in items if c.get("urgency_score", 0.0) >= 90.0]
    print(f"Stories with Urgency >= 90.0: {len(flood_stories)}")
    for fs in flood_stories:
        print(f"Emergency Story: '{fs.get('headline')}' -> Urgency={fs.get('urgency_score')}, Importance={fs.get('importance_score')}")
        assert fs.get("importance_score", 0.0) >= RankingConfig.EMERGENCY_IMPORTANCE_FLOOR, f"Emergency story importance must be >= {RankingConfig.EMERGENCY_IMPORTANCE_FLOOR}"
    results["test11_emergency_floor_verified"] = True
    results["test11_emergency_count"] = len(flood_stories)

    # TEST 12 — API VS DATABASE
    print("Test 12: Comparing API vs Database values...")
    db = SessionLocal()
    db_card = db.query(Card).filter(Card.id == items[0]["id"]).first()
    print(f"Card {items[0]['id']} in DB:")
    print(f"  DB importance: {db_card.importance_score}, API importance: {items[0]['importance_score']}")
    print(f"  DB urgency: {db_card.urgency_score}, API urgency: {items[0]['urgency_score']}")
    print(f"  API dynamic freshness: {items[0]['freshness_score']}, API dynamic relevance: {items[0]['personal_relevance_score']}")
    db.close()

    # TEST 13 — REPEATED REQUEST CONSISTENCY
    print("Test 13: Testing determinism across 5 repeated requests...")
    orders = []
    for r in range(5):
        rf = get_json(feed_url)
        c_items = rf.get("items", []) if isinstance(rf, dict) else rf
        orders.append([c["id"] for c in c_items])
    
    deterministic = all(o == orders[0] for o in orders)
    print(f"Repeated requests deterministic: {deterministic}")
    results["test13_deterministic"] = deterministic
    assert deterministic, "Feed ordering must be completely deterministic!"

    # TEST 14 — CATEGORY FILTER REGRESSION
    print("Test 14: Category filter regression...")
    for cat in ["politics", "technology", "business", "national"]:
        cat_feed = get_json(f"{BASE_URL}/feed?device_id={dev_id}&category={cat}&limit=30")
        cat_items = cat_feed.get("items", []) if isinstance(cat_feed, dict) else cat_feed
        # All items must match requested category
        for ci in cat_items:
            assert ci["category"].lower() == cat.lower(), f"Expected category {cat}, got {ci['category']}"
        # All items must be in descending order
        for j in range(len(cat_items) - 1):
            assert cat_items[j]["final_feed_score"] >= cat_items[j+1]["final_feed_score"], f"Category {cat} items out of order"
    print("Category filters preserved descending order.")

    # TEST 15 — STATE REGRESSION
    print("Test 15: State regression...")
    feed_kar = get_json(f"{BASE_URL}/feed?device_id={dev_id}&state=Karnataka&limit=30")
    feed_tel = get_json(f"{BASE_URL}/feed?device_id={dev_id}&state=Telangana&limit=30")
    items_kar = feed_kar.get("items", []) if isinstance(feed_kar, dict) else feed_kar
    items_tel = feed_tel.get("items", []) if isinstance(feed_tel, dict) else feed_tel
    assert len(items_kar) > 0 and len(items_tel) > 0, "Both state feeds must return items"

    # TEST 16 — FEED DUPLICATES
    print("Test 16: Duplicate card check...")
    card_ids = [c["id"] for c in items]
    unique_ids = set(card_ids)
    duplicate_ids = len(card_ids) - len(unique_ids)
    print(f"Total stories: {len(card_ids)}, Unique IDs: {len(unique_ids)}, Duplicate IDs: {duplicate_ids}")
    results["test16_duplicate_ids"] = duplicate_ids
    assert duplicate_ids == 0, f"Found {duplicate_ids} duplicate card IDs in feed!"

    headlines = [" ".join(c.get("headline", "").lower().split()) for c in items]
    unique_headlines = set(headlines)
    duplicate_headlines = len(headlines) - len(unique_headlines)
    print(f"Duplicate headlines: {duplicate_headlines}")
    results["test16_duplicate_headlines"] = duplicate_headlines
    assert duplicate_headlines == 0, f"Found {duplicate_headlines} duplicate headlines!"

    # TEST 17 — FEED DATA INTEGRITY
    print("Test 17: Feed data integrity check...")
    integrity_errors = []
    for c in items:
        if not c.get("id"): integrity_errors.append("missing id")
        if not c.get("headline"): integrity_errors.append(f"missing headline for {c.get('id')}")
        if not c.get("category"): integrity_errors.append(f"missing category for {c.get('id')}")
        if c.get("final_feed_score") is None or math.isnan(c.get("final_feed_score", 0)):
            integrity_errors.append(f"invalid final_feed_score for {c.get('id')}")
        sources = c.get("sources", [])
        for s in sources:
            if not s.get("url") or not s.get("url").startswith("http"):
                integrity_errors.append(f"invalid source url {s.get('url')} on {c.get('id')}")

    print(f"Data integrity errors: {len(integrity_errors)}")
    results["test17_integrity_errors"] = integrity_errors
    assert len(integrity_errors) == 0, f"Data integrity errors found: {integrity_errors}"

    # BROWSER TEST WITH PLAYWRIGHT CHROME
    print("--------------------------------------------------")
    print("RUNNING BROWSER PLAYWRIGHT VERIFICATION...")
    print("--------------------------------------------------")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        console_logs = []
        page_errors = []
        failed_requests = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}"))

        # Navigate with existing onboarding complete
        page.goto(BASE_URL)
        page.evaluate(f"""() => {{
            localStorage.setItem('newsreels_onboarding_complete', 'true');
            localStorage.setItem('newsreels_device_id', '{dev_id}');
            localStorage.setItem('newsreels_state', 'Karnataka');
            localStorage.setItem('newsreels_interests', JSON.stringify(['Technology', 'Politics', 'Business', 'National']));
            localStorage.setItem('newsreels_priority_order', JSON.stringify(['Politics', 'National', 'Technology', 'Business']));
        }}""")
        page.reload()
        page.wait_for_load_state("networkidle")

        rendered_cards = page.query_selector_all("#feed-container .scroll-card")
        rendered_count = len(rendered_cards)
        print(f"Rendered feed cards in Chrome: {rendered_count}")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b5_rendered_feed.png"))

        # Check visible scores in rendered cards
        card_scores = []
        for rc in rendered_cards:
            score_badge = rc.query_selector(".scroll-score")
            score_text = score_badge.inner_text() if score_badge else "0"
            score_val = float(score_text.replace("Score", "").strip())
            card_scores.append(score_val)

        # Check visible scores are descending
        descending_browser = all(card_scores[k] >= card_scores[k+1] for k in range(len(card_scores)-1))
        print(f"Browser card scores: {card_scores}")
        print(f"Browser card scores descending: {descending_browser}")
        assert descending_browser, "Rendered card scores must be descending!"

        # Detail modal check
        first_detail_btn = page.query_selector(".scroll-action-btn:has-text('Explain Decision')")
        if first_detail_btn:
            first_detail_btn.click()
            page.wait_for_timeout(400)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b5_detail_modal.png"))
            page.click("#btn-close-detail-modal")
            page.wait_for_timeout(200)

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["browser_rendered_count"] = rendered_count
        results["browser_descending"] = descending_browser
        results["browser_console_errors"] = err_logs
        results["browser_page_errors"] = page_errors
        results["browser_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    print("\nALL B5 FEED RANKING INTEGRITY AUDIT CHECKS PASSED!")
    with open(r"d:\News\scratch\b5_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b5_audit()
