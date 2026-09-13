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
from playwright.sync_api import sync_playwright

from app.db import SessionLocal  # type: ignore
from app.models import Card, CardSource, Source, StoryCluster  # type: ignore
from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = r"d:\News\scratch\b7_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "B7-Audit/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def run_b7_audit():
    results = {}
    print("==================================================")
    print("STARTING B7 — VERIFICATION & TRUST ENGINE AUDIT")
    print("==================================================")

    # ----------------------------------------------------
    # TEST 1 — SOURCE TIER DEFINITIONS
    # ----------------------------------------------------
    print("TEST 1: Source tier definitions...")
    tier1_list = sorted(list(RankingConfig.TIER_1_SOURCES))
    tier2_list = sorted(list(RankingConfig.TIER_2_SOURCES))
    print(f"Tier 1 sources ({len(tier1_list)}): {tier1_list}")
    print(f"Tier 2 sources ({len(tier2_list)}): {tier2_list}")
    results["test1_tier1"] = tier1_list
    results["test1_tier2"] = tier2_list

    # ----------------------------------------------------
    # TEST 2 — SCORE RULES
    # ----------------------------------------------------
    print("TEST 2: Score rules verification...")
    # 1. Conflict
    s_conflict, m_conflict = VerificationEngine.calculate_verification(
        [{"name": "BBC News"}, {"name": "Reuters"}], conflict_detected=True
    )
    # 2. Multiple Tier 1 independent sources
    s_multi_t1_2, m_multi_t1_2 = VerificationEngine.calculate_verification(
        [{"name": "BBC News"}, {"name": "Reuters"}]
    )
    s_multi_t1_3, m_multi_t1_3 = VerificationEngine.calculate_verification(
        [{"name": "BBC News"}, {"name": "Reuters"}, {"name": "The Hindu"}]
    )
    # 3. One Tier 1 + another source
    s_t1_plus_other, m_t1_plus_other = VerificationEngine.calculate_verification(
        [{"name": "Reuters"}, {"name": "Local Tribune"}]
    )
    # 4. One Tier 1
    s_single_t1, m_single_t1 = VerificationEngine.calculate_verification(
        [{"name": "Reuters"}]
    )
    # 5. Multiple Tier 2 sources
    s_multi_t2, m_multi_t2 = VerificationEngine.calculate_verification(
        [{"name": "Hindustan Times"}, {"name": "Livemint"}]
    )
    # 6. One Tier 2
    s_single_t2, m_single_t2 = VerificationEngine.calculate_verification(
        [{"name": "Hindustan Times"}]
    )
    # 7. One unclassified source
    s_unclassified, m_unclassified = VerificationEngine.calculate_verification(
        [{"name": "Random News Blog"}]
    )
    # 8. Zero sources
    s_zero, m_zero = VerificationEngine.calculate_verification([])

    rules_summary = {
        "conflict": s_conflict,                     # 45.0
        "multiple_tier1_2sources": s_multi_t1_2,     # 97.0 (95 + 2*1)
        "multiple_tier1_3sources": s_multi_t1_3,     # 98.0 (95 + 3*1)
        "tier1_plus_other": s_t1_plus_other,         # 90.0
        "single_tier1": s_single_t1,                 # 88.0
        "multiple_tier2": s_multi_t2,                # 82.0
        "single_tier2": s_single_t2,                 # 70.0
        "unclassified": s_unclassified,              # 55.0
        "zero_sources": s_zero                       # 40.0
    }
    print(f"Rules scores: {json.dumps(rules_summary, indent=2)}")
    results["test2_rules"] = rules_summary

    assert s_conflict == 45.0, f"Expected conflict 45.0, got {s_conflict}"
    assert s_multi_t1_2 == 97.0, f"Expected multiple Tier 1 (2 sources) 97.0, got {s_multi_t1_2}"
    assert s_multi_t1_3 == 98.0, f"Expected multiple Tier 1 (3 sources) 98.0, got {s_multi_t1_3}"
    assert s_t1_plus_other == 90.0, f"Expected Tier 1 + other 90.0, got {s_t1_plus_other}"
    assert s_single_t1 == 88.0, f"Expected single Tier 1 88.0, got {s_single_t1}"
    assert s_multi_t2 == 82.0, f"Expected multiple Tier 2 82.0, got {s_multi_t2}"
    assert s_single_t2 == 70.0, f"Expected single Tier 2 70.0, got {s_single_t2}"
    assert s_unclassified == 55.0, f"Expected unclassified 55.0, got {s_unclassified}"
    assert s_zero == 40.0, f"Expected zero sources 40.0, got {s_zero}"

    # ----------------------------------------------------
    # TEST 3 — CONFLICT HANDLING
    # ----------------------------------------------------
    print("TEST 3: Conflict handling...")
    db = SessionLocal()
    conflict_clusters = db.query(StoryCluster).filter(StoryCluster.flagged_conflict == True).all()
    print(f"Real database clusters with flagged_conflict: {len(conflict_clusters)}")
    results["test3_real_conflict_clusters"] = len(conflict_clusters)
    results["test3_controlled_conflict_score"] = s_conflict
    assert s_conflict == 45.0

    # ----------------------------------------------------
    # TEST 4, 5, 6, 7, 8 — SOURCE CASES
    # ----------------------------------------------------
    print("TEST 4-8: Source cases in DB and engine...")
    cards = db.query(Card).filter(Card.verified_status == "published").all()
    
    # Check if a live multi-tier1 card exists
    live_multi_t1 = next((c for c in cards if c.verification_score >= 95.0), None)
    if live_multi_t1:
        print(f"Live Multi-Tier 1 Card: ID={live_multi_t1.id[:8]} | Score={live_multi_t1.verification_score} | Headline='{live_multi_t1.headline[:40]}'")
        results["test4_live_multi_t1"] = {"id": live_multi_t1.id, "score": live_multi_t1.verification_score}

    # Check if a live single-tier1 card exists
    live_single_t1 = next((c for c in cards if 85.0 <= c.verification_score < 95.0), None)
    if live_single_t1:
        print(f"Live Single-Tier 1 Card: ID={live_single_t1.id[:8]} | Score={live_single_t1.verification_score} | Headline='{live_single_t1.headline[:40]}'")
        results["test5_live_single_t1"] = {"id": live_single_t1.id, "score": live_single_t1.verification_score}

    # Check if a live multi-tier2 card exists
    live_multi_t2 = next((c for c in cards if c.verification_score == 82.0), None)
    if live_multi_t2:
        print(f"Live Multi-Tier 2 Card: ID={live_multi_t2.id[:8]} | Score={live_multi_t2.verification_score} | Headline='{live_multi_t2.headline[:40]}'")
        results["test6_live_multi_t2"] = {"id": live_multi_t2.id, "score": live_multi_t2.verification_score}

    # Unclassified and zero source validation
    assert not math.isnan(s_unclassified) and 0.0 <= s_unclassified <= 100.0
    assert not math.isnan(s_zero) and 0.0 <= s_zero <= 100.0

    # ----------------------------------------------------
    # TEST 9 & 10 — SCORE RANGE & DISTRIBUTION
    # ----------------------------------------------------
    print("TEST 9 & 10: Live score range and distribution across cards...")
    distribution = {
        "multi_tier1": 0,
        "single_tier1": 0,
        "multi_tier2": 0,
        "single_tier2": 0,
        "unclassified": 0,
        "conflict": 0,
        "zero_sources": 0
    }
    all_scores = []

    for c in cards:
        srcs = [{"name": s.name, "tier": s.trust_tier} for s in c.sources]
        score, meta = VerificationEngine.calculate_verification(srcs, conflict_detected=False)
        all_scores.append(score)
        t1 = meta["tier1_source_count"]
        indep = meta["independent_source_count"]
        
        if len(srcs) == 0:
            distribution["zero_sources"] += 1
        elif t1 >= 2:
            distribution["multi_tier1"] += 1
        elif t1 == 1:
            distribution["single_tier1"] += 1
        elif indep >= 2:
            distribution["multi_tier2"] += 1
        elif meta["status"] == "single_reputable_source":
            distribution["single_tier2"] += 1
        else:
            distribution["unclassified"] += 1

    min_ver = min(all_scores)
    max_ver = max(all_scores)
    invalid_ver = sum(1 for s in all_scores if s < 0.0 or s > 100.0 or math.isnan(s))

    print(f"Verification Score Range: Min={min_ver}, Max={max_ver}, Invalid={invalid_ver}")
    print(f"Source Distribution: {distribution}")
    results["test9_min"] = min_ver
    results["test9_max"] = max_ver
    results["test9_invalid"] = invalid_ver
    results["test10_distribution"] = distribution
    assert invalid_ver == 0, f"Found {invalid_ver} invalid verification scores!"

    # ----------------------------------------------------
    # TEST 11 — FINAL SCORE CONTRIBUTION (0.10)
    # ----------------------------------------------------
    print("TEST 11: Final score contribution (Verification x 0.10)...")
    out_ver_100 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=100.0
    )
    out_ver_50 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    delta_ver = 100.0 - 50.0 # 50.0
    expected_delta_final = delta_ver * RankingConfig.WEIGHT_VERIFICATION # 50 * 0.10 = 5.0
    actual_delta_final = round(out_ver_100.final_feed_score - out_ver_50.final_feed_score, 2)

    print(f"Verification weight: {RankingConfig.WEIGHT_VERIFICATION}")
    print(f"Delta Verification: {delta_ver}")
    print(f"Expected Delta Final Score: {expected_delta_final}")
    print(f"Actual Delta Final Score: {actual_delta_final}")
    assert actual_delta_final == expected_delta_final, f"Expected delta {expected_delta_final}, got {actual_delta_final}"
    results["test11_expected_delta"] = expected_delta_final
    results["test11_actual_delta"] = actual_delta_final

    # ----------------------------------------------------
    # TEST 12 — OBJECTIVE COMPONENT ISOLATION
    # ----------------------------------------------------
    print("TEST 12: Objective component isolation...")
    assert out_ver_100.objective_importance == out_ver_50.objective_importance == 50.0
    assert out_ver_100.urgency == out_ver_50.urgency == 50.0
    assert out_ver_100.freshness == out_ver_50.freshness == 50.0
    assert out_ver_100.personal_relevance == out_ver_50.personal_relevance == 50.0
    print("Importance, Urgency, Freshness, Personal Relevance remain completely isolated and unchanged.")
    results["test12_isolation_verified"] = True

    # ----------------------------------------------------
    # TEST 13 — VERIFICATION VS PERSONALIZATION INDEPENDENCE
    # ----------------------------------------------------
    print("TEST 13: Verification vs Personalization independence...")
    feed_state_kar = get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30")
    feed_state_tel = get_json(f"{BASE_URL}/feed?state=Telangana&limit=30")

    items_kar = feed_state_kar.get("items", []) if isinstance(feed_state_kar, dict) else feed_state_kar
    items_tel = feed_state_tel.get("items", []) if isinstance(feed_state_tel, dict) else feed_state_tel

    # Map verification scores by card ID
    map_kar = {c["id"]: c["verification_score"] for c in items_kar}
    map_tel = {c["id"]: c["verification_score"] for c in items_tel}

    common_ids = set(map_kar.keys()) & set(map_tel.keys())
    mismatched_ver_scores = [cid for cid in common_ids if map_kar[cid] != map_tel[cid]]
    print(f"Common cards between Karnataka and Telangana feeds: {len(common_ids)}")
    print(f"Verification score changes across state changes: {len(mismatched_ver_scores)}")
    assert len(mismatched_ver_scores) == 0, f"Verification scores changed when state changed on cards: {mismatched_ver_scores}"
    results["test13_personalization_independence"] = True

    # ----------------------------------------------------
    # TEST 14 — REPEATED DETERMINISM
    # ----------------------------------------------------
    print("TEST 14: Repeated determinism...")
    src_test = [{"name": "The Hindu"}, {"name": "NDTV"}, {"name": "The Times of India"}]
    r1, _ = VerificationEngine.calculate_verification(src_test)
    r2, _ = VerificationEngine.calculate_verification(src_test)
    r3, _ = VerificationEngine.calculate_verification(src_test)
    assert r1 == r2 == r3 == 98.0, f"Repeated verification mismatch: {r1}, {r2}, {r3}"
    print(f"Repeated verification scores: {r1}, {r2}, {r3} (all 98.0)")
    results["test14_determinism"] = True

    # ----------------------------------------------------
    # TEST 15 — LIVE API DATA
    # ----------------------------------------------------
    print("TEST 15: Live API verification...")
    live_feed = get_json(f"{BASE_URL}/feed?limit=30")
    live_items = live_feed.get("items", []) if isinstance(live_feed, dict) else live_feed
    api_missing_ver = 0
    api_invalid_ver = 0
    for card in live_items:
        v = card.get("verification_score")
        if v is None:
            api_missing_ver += 1
        elif not isinstance(v, (int, float)) or math.isnan(v) or v < 0.0 or v > 100.0:
            api_invalid_ver += 1

    print(f"API items checked: {len(live_items)}, missing: {api_missing_ver}, invalid: {api_invalid_ver}")
    results["test15_api_missing"] = api_missing_ver
    results["test15_api_invalid"] = api_invalid_ver
    assert api_missing_ver == 0, "Missing verification score on API items!"
    assert api_invalid_ver == 0, "Invalid verification score on API items!"

    # ----------------------------------------------------
    # TEST 16 — SOURCE URL INTEGRITY
    # ----------------------------------------------------
    print("TEST 16: Source URL integrity...")
    malformed_urls = 0
    missing_sources = 0
    duplicate_sources = 0

    for c in cards:
        if not c.sources or len(c.sources) == 0:
            missing_sources += 1
        seen_urls = set()
        for s in c.sources:
            if not s.url or not (s.url.startswith("http://") or s.url.startswith("https://")):
                malformed_urls += 1
            if s.url in seen_urls:
                duplicate_sources += 1
            seen_urls.add(s.url)

    print(f"Source URL integrity: missing={missing_sources}, malformed={malformed_urls}, duplicate={duplicate_sources}")
    results["test16_missing_sources"] = missing_sources
    results["test16_malformed_urls"] = malformed_urls
    results["test16_duplicate_sources"] = duplicate_sources
    assert malformed_urls == 0, f"Found {malformed_urls} malformed URLs"

    # ----------------------------------------------------
    # TEST 17 — BROWSER REGRESSION IN GOOGLE CHROME
    # ----------------------------------------------------
    print("TEST 17: Browser regression in Google Chrome...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-quic"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        console_logs = []
        page_errors = []
        failed_requests = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}"))

        page.goto(BASE_URL)
        page.evaluate("""() => {
            localStorage.setItem('newsreels_onboarding_complete', 'true');
            localStorage.setItem('newsreels_state', 'Karnataka');
            localStorage.setItem('newsreels_interests', JSON.stringify(['Technology', 'Politics', 'Business', 'National']));
            localStorage.setItem('newsreels_priority_order', JSON.stringify(['Politics', 'National', 'Technology', 'Business']));
        }""")
        page.reload()
        page.wait_for_load_state("networkidle")

        rendered_cards = page.query_selector_all("#feed-container .scroll-card")
        print(f"Browser rendered cards: {len(rendered_cards)}")
        assert len(rendered_cards) > 0, "No cards rendered in browser!"

        # Check trust badges exist
        badges = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.scroll-card .scroll-badges .badge:last-child')).map(el => el.textContent.trim());
        }""")
        print(f"Sample trust badges in UI: {badges[:5]}")
        assert all(len(b) > 0 for b in badges), "Some cards have empty trust badges!"

        # Check scores are descending
        scores = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.scroll-card .scroll-score')).map(el => {
                return parseFloat(el.textContent.replace('Score', '').trim());
            });
        }""")
        descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        assert descending, f"Browser feed scores not descending: {scores}"

        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b7_browser_feed.png"))

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["browser_stories_rendered"] = len(rendered_cards)
        results["browser_console_errors"] = err_logs
        results["browser_page_errors"] = page_errors
        results["browser_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    db.close()
    print("\nALL B7 VERIFICATION & TRUST ENGINE CHECKS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b7_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b7_audit()
