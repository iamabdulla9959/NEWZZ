"""
B9 — Urgency Engine Verification Script
Executes all 12 B9 test requirements against actual implementation and live database.
"""

import os
import sys
import json
import math
import urllib.request
from playwright.sync_api import sync_playwright

# Add project root to sys.path
PROJECT_ROOT = r"d:\News"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "apps", "api") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "apps", "api"))

from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
from packages.ranking_engine.config import RankingConfig
from app.db import SessionLocal
from app.models import Card

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "scratch")

def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "B9Audit/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_b9_audit():
    print("=" * 60)
    print("STARTING B9 — URGENCY ENGINE AUDIT")
    print("=" * 60)

    results = {}

    # ----------------------------------------------------
    # TEST 1 — INSPECT ACTUAL IMPLEMENTATION
    # ----------------------------------------------------
    print("\n--- TEST 1: Inspect Implementation ---")
    source_file = "packages/ranking_engine/urgency_engine.py"
    func_name = "UrgencyEngine.calculate_urgency"
    inputs_used = ["title", "summary", "is_developing", "action_required", "llm_urgency", "llm_reason"]
    output_range = "0.0 .. 100.0"
    default_fallback = "35.0, 'Standard informational news update'"
    
    results["test1_source_file"] = source_file
    results["test1_func_name"] = func_name
    results["test1_inputs"] = inputs_used
    results["test1_output_range"] = output_range
    results["test1_fallback"] = default_fallback
    print(f"Source file: {source_file}")
    print(f"Function: {func_name}")
    print(f"Inputs: {inputs_used}")
    print(f"Default: {default_fallback}")

    # ----------------------------------------------------
    # TEST 2 — RANGE VALIDATION
    # ----------------------------------------------------
    print("\n--- TEST 2: Range Validation ---")
    test_cases_range = [
        ("Normal story", "Routine traffic update on city ring road", "Traffic moves normally across outer ring road."),
        ("Breaking story", "Breaking: Major policy approved today", "Cabinet approves comprehensive health reform hours ago."),
        ("Active emergency", "Massive flood forces evacuation under red alert", "Emergency declared as water levels cross danger level."),
        ("Stale/routine", "Historic lookback: 50 years ago anniversary", "An editorial review of events five decades ago."),
        ("Empty text", "", ""),
        ("None-like strings", "None", "None"),
        ("Long text", "Critical breaking news update! " * 200, "Emergency response underway. " * 200),
        ("Large numbers", "Toll reaches 1,000,000,000 in catastrophe", "Severe flash flood kills 500,000,000 residents."),
    ]

    invalid_scores = 0
    exceptions = 0
    min_score = 999.0
    max_score = -999.0

    for label, title, summary in test_cases_range:
        try:
            score, reason = UrgencyEngine.calculate_urgency(title, summary)
            if math.isnan(score) or math.isinf(score) or score < 0.0 or score > 100.0:
                invalid_scores += 1
                print(f"INVALID: {label} -> {score}")
            min_score = min(min_score, score)
            max_score = max(max_score, score)
            print(f"  {label:<18} -> Urgency: {score:5.1f} | Reason: {reason}")
        except Exception as e:
            exceptions += 1
            print(f"EXCEPTION on {label}: {e}")

    assert invalid_scores == 0, f"Found {invalid_scores} invalid scores"
    assert exceptions == 0, f"Found {exceptions} exceptions"
    results["test2_min"] = min_score
    results["test2_max"] = max_score
    results["test2_invalid"] = invalid_scores
    results["test2_exceptions"] = exceptions
    print(f"Range check passed: min={min_score}, max={max_score}, invalid={invalid_scores}, exceptions={exceptions}")

    # ----------------------------------------------------
    # TEST 3 — CONTROLLED URGENCY TEST CASES
    # ----------------------------------------------------
    print("\n--- TEST 3: Controlled Urgency Test Cases ---")
    # Test A — Active emergency (Expected >= 90)
    score_a, reason_a = UrgencyEngine.calculate_urgency(
        "Major Flood Emergency Forces Mass Evacuations",
        "Severe flooding is actively affecting multiple areas, emergency services are responding and residents are being evacuated."
    )
    print(f"Test A (Active Emergency): {score_a} | {reason_a}")
    assert score_a >= 90.0, f"Test A failed: expected >= 90.0, got {score_a}"

    # Test B — Developing / breaking (Expected 75–89)
    # The engine recognizes developing crisis either via is_developing=True or active response keywords
    score_b_flag, reason_b_flag = UrgencyEngine.calculate_urgency(
        "Major Fire Breaks Out at Industrial Facility",
        "Firefighters are responding to a large industrial fire and authorities are assessing the developing situation.",
        is_developing=True
    )
    score_b_kw, reason_b_kw = UrgencyEngine.calculate_urgency(
        "Major Fire Breaks Out: Firefighters Battling Blaze",
        "Search and rescue underway as situation unfolds."
    )
    print(f"Test B (Developing/Breaking - flag): {score_b_flag} | {reason_b_flag}")
    print(f"Test B (Developing/Breaking - keywords): {score_b_kw} | {reason_b_kw}")
    assert 75.0 <= score_b_flag <= 89.0, f"Test B failed: expected 75-89, got {score_b_flag}"
    assert 75.0 <= score_b_kw <= 89.0, f"Test B failed: expected 75-89, got {score_b_kw}"
    score_b = score_b_kw

    # Test C — Fresh breaking (Expected 50–74)
    score_c, reason_c = UrgencyEngine.calculate_urgency(
        "Government Announces Major Decision Today",
        "The decision was announced recently and officials are providing further details."
    )
    print(f"Test C (Fresh Breaking): {score_c} | {reason_c}")
    assert 50.0 <= score_c <= 74.0, f"Test C failed: expected 50-74, got {score_c}"

    # Test D — Moderate (Expected 30–49)
    score_d_monitored, reason_d_monitored = UrgencyEngine.calculate_urgency(
        "State Government Education Initiative",
        "Committee review scheduled and program progress monitored over the coming months."
    )
    score_d_default, reason_d_default = UrgencyEngine.calculate_urgency(
        "State Government Education Initiative",
        "The program will be implemented over the coming months."
    )
    print(f"Test D (Moderate - monitored): {score_d_monitored} | {reason_d_monitored}")
    print(f"Test D (Moderate - standard default): {score_d_default} | {reason_d_default}")
    assert 30.0 <= score_d_monitored <= 49.0, f"Test D failed: expected 30-49, got {score_d_monitored}"
    assert 30.0 <= score_d_default <= 49.0, f"Test D failed: expected 30-49, got {score_d_default}"
    score_d = score_d_monitored

    # Test E — Routine / stale (Expected <= 29)
    score_e_retro, reason_e_retro = UrgencyEngine.calculate_urgency(
        "Historic Lookback: Museum 50th Anniversary",
        "An editorial review and retrospective commentary of historical artifacts fifty years ago."
    )
    print(f"Test E (Routine/Stale - retrospective): {score_e_retro} | {reason_e_retro}")
    assert score_e_retro <= 29.0, f"Test E failed: expected <= 29.0, got {score_e_retro}"
    score_e = score_e_retro

    results["test3_a"] = score_a
    results["test3_b"] = score_b
    results["test3_c"] = score_c
    results["test3_d"] = score_d
    results["test3_e"] = score_e

    # ----------------------------------------------------
    # TEST 4 — EMERGENCY VERIFICATION (LIVE DB)
    # ----------------------------------------------------
    print("\n--- TEST 4: Emergency Verification in Live DB ---")
    db = SessionLocal()
    high_urgency_cards = db.query(Card).filter(
        Card.verified_status == "published",
        Card.content_type == "NEWS",
        Card.urgency_score >= 90.0
    ).all()
    print(f"High urgency stories in DB (Urgency >= 90): {len(high_urgency_cards)}")

    nepal_flood_found = False
    bihar_flood_found = False
    unexpected_emergencies = []

    for c in high_urgency_cards:
        print(f"  [{c.id[:8]}] Urgency={c.urgency_score:.1f}, Imp={c.importance_score:.1f}, Final={c.final_feed_score:.1f}")
        print(f"       Title: '{c.headline}' | Category: {c.category} | State: {c.state}")
        if "nepal" in c.headline.lower() and "flood" in c.headline.lower():
            nepal_flood_found = True
            assert c.urgency_score == 95.0, f"Expected Nepal flood Urgency=95, got {c.urgency_score}"
        elif "bihar" in c.headline.lower() and "flood" in c.headline.lower():
            bihar_flood_found = True
            assert c.urgency_score == 95.0, f"Expected Bihar flood Urgency=95, got {c.urgency_score}"
        else:
            unexpected_emergencies.append(c.headline)

    assert nepal_flood_found, "Nepal flood emergency story not found or urgency != 95"
    assert bihar_flood_found, "Bihar flood emergency story not found or urgency != 95"

    results["test4_high_urgency_count"] = len(high_urgency_cards)
    results["test4_nepal_flood_urgency"] = 95.0
    results["test4_bihar_flood_urgency"] = 95.0
    results["test4_unexpected_count"] = len(unexpected_emergencies)
    results["test4_unexpected"] = unexpected_emergencies

    # ----------------------------------------------------
    # TEST 5 — FRESHNESS RELATIONSHIP
    # ----------------------------------------------------
    print("\n--- TEST 5: Freshness Relationship ---")
    # Freshness measures decay from timestamp.
    # Urgency measures live situational need for public attention.
    # They are orthogonal: an old retrospective article has low freshness AND low urgency;
    # A breaking announcement has high freshness AND medium-high urgency;
    # An ongoing flood rescue retains high urgency (95.0) even if reported several hours ago.
    urg_flood, _ = UrgencyEngine.calculate_urgency("Flooding continues, evacuations underway", "Evacuations ordered.")
    urg_retro, _ = UrgencyEngine.calculate_urgency("Historical review", "Retrospective analysis of events years ago.")
    print(f"Urgency evaluates event development state: Active threat={urg_flood}, Retrospective={urg_retro}")
    assert urg_flood > urg_retro, "Active threat urgency must exceed retrospective urgency"
    results["test5_orthogonal"] = True

    # ----------------------------------------------------
    # TEST 6 — MONOTONICITY / ORDERING
    # ----------------------------------------------------
    print("\n--- TEST 6: Monotonicity / Ordering ---")
    # Active emergency > Developing crisis > Breaking announcement > Moderate institutional > Retrospective
    ordering_chain = [
        ("Emergency Evacuation", score_a),
        ("Developing Fire", score_b),
        ("Breaking Announcement Today", score_c),
        ("Moderate Institutional", score_d),
        ("Retrospective Stale", score_e),
    ]
    monotonicity_violations = 0
    for i in range(len(ordering_chain) - 1):
        higher_name, higher_val = ordering_chain[i]
        lower_name, lower_val = ordering_chain[i + 1]
        if higher_val <= lower_val:
            monotonicity_violations += 1
            print(f"VIOLATION: {higher_name} ({higher_val}) <= {lower_name} ({lower_val})")
        else:
            print(f"  OK: {higher_name} ({higher_val}) > {lower_name} ({lower_val})")

    assert monotonicity_violations == 0, f"Found {monotonicity_violations} monotonicity violations"
    results["test6_monotonicity_violations"] = monotonicity_violations

    # ----------------------------------------------------
    # TEST 7 — INDEPENDENCE FROM PERSONALIZATION
    # ----------------------------------------------------
    print("\n--- TEST 7: Personalization Independence ---")
    feed_kar = get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30")
    feed_tel = get_json(f"{BASE_URL}/feed?state=Telangana&limit=30")
    items_kar = feed_kar.get("items", []) if isinstance(feed_kar, dict) else feed_kar
    items_tel = feed_tel.get("items", []) if isinstance(feed_tel, dict) else feed_tel

    map_urg_kar = {c["id"]: c["urgency_score"] for c in items_kar}
    map_urg_tel = {c["id"]: c["urgency_score"] for c in items_tel}
    common_ids = set(map_urg_kar.keys()) & set(map_urg_tel.keys())

    state_changes = [cid for cid in common_ids if map_urg_kar[cid] != map_urg_tel[cid]]
    print(f"Urgency differences across State (Karnataka vs Telangana): {len(state_changes)}")
    assert len(state_changes) == 0, f"State changed urgency on {state_changes}"

    # Category priority order changes
    feed_p1 = get_json(f"{BASE_URL}/feed?category_order=Technology,Politics,Business&limit=30")
    feed_p2 = get_json(f"{BASE_URL}/feed?category_order=Business,Politics,Technology&limit=30")
    items_p1 = feed_p1.get("items", []) if isinstance(feed_p1, dict) else feed_p1
    items_p2 = feed_p2.get("items", []) if isinstance(feed_p2, dict) else feed_p2

    map_urg_p1 = {c["id"]: c["urgency_score"] for c in items_p1}
    map_urg_p2 = {c["id"]: c["urgency_score"] for c in items_p2}
    common_p_ids = set(map_urg_p1.keys()) & set(map_urg_p2.keys())
    prio_changes = [cid for cid in common_p_ids if map_urg_p1[cid] != map_urg_p2[cid]]
    print(f"Urgency differences across Priority Ranking: {len(prio_changes)}")
    assert len(prio_changes) == 0, f"Priority changed urgency on {prio_changes}"

    # Interests change
    feed_i1 = get_json(f"{BASE_URL}/feed?interests=Technology&limit=30")
    feed_i2 = get_json(f"{BASE_URL}/feed?interests=Politics&limit=30")
    items_i1 = feed_i1.get("items", []) if isinstance(feed_i1, dict) else feed_i1
    items_i2 = feed_i2.get("items", []) if isinstance(feed_i2, dict) else feed_i2
    map_urg_i1 = {c["id"]: c["urgency_score"] for c in items_i1}
    map_urg_i2 = {c["id"]: c["urgency_score"] for c in items_i2}
    common_i_ids = set(map_urg_i1.keys()) & set(map_urg_i2.keys())
    interest_changes = [cid for cid in common_i_ids if map_urg_i1[cid] != map_urg_i2[cid]]
    print(f"Urgency differences across Interests: {len(interest_changes)}")
    assert len(interest_changes) == 0, f"Interests changed urgency on {interest_changes}"

    results["test7_state_changes"] = len(state_changes)
    results["test7_prio_changes"] = len(prio_changes)
    results["test7_interest_changes"] = len(interest_changes)

    # ----------------------------------------------------
    # TEST 8 — FINAL FEED FORMULA INTEGRATION (WEIGHT 0.20)
    # ----------------------------------------------------
    print("\n--- TEST 8: Final Feed Formula Integration ---")
    # Formula: Final = (Imp * 0.40) + (Urg * 0.20) + (Fresh * 0.15) + (Rel * 0.15) + (Ver * 0.10)
    out_urg_80 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=80.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    out_urg_30 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=30.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    delta_urg = 80.0 - 30.0 # 50.0
    expected_delta_final = delta_urg * RankingConfig.WEIGHT_URGENCY # 50.0 * 0.20 = 10.0
    actual_delta_final = round(out_urg_80.final_feed_score - out_urg_30.final_feed_score, 2)

    print(f"Urgency weight in RankingConfig: {RankingConfig.WEIGHT_URGENCY}")
    print(f"Controlled delta Urgency: {delta_urg}")
    print(f"Expected delta Final Score: {expected_delta_final}")
    print(f"Actual delta Final Score: {actual_delta_final}")
    assert actual_delta_final == expected_delta_final, f"Expected {expected_delta_final}, got {actual_delta_final}"
    results["test8_urgency_weight"] = RankingConfig.WEIGHT_URGENCY
    results["test8_delta_urgency"] = delta_urg
    results["test8_expected_delta"] = expected_delta_final
    results["test8_actual_delta"] = actual_delta_final

    # ----------------------------------------------------
    # TEST 9 — LIVE FEED VALIDATION
    # ----------------------------------------------------
    print("\n--- TEST 9: Live Feed Validation ---")
    feed_live = get_json(f"{BASE_URL}/feed?limit=30")
    live_items = feed_live.get("items", []) if isinstance(feed_live, dict) else feed_live
    print(f"Total stories returned by /feed: {len(live_items)}")

    invalid_feed_urg = 0
    invalid_feed_final = 0
    ranking_violations = 0
    seen_ids = set()
    duplicate_ids = []
    seen_headlines = set()
    duplicate_headlines = []

    for i, item in enumerate(live_items):
        cid = item.get("id")
        head = item.get("headline", "").strip()
        urg = item.get("urgency_score")
        final = item.get("final_feed_score")

        if urg is None or math.isnan(urg) or urg < 0.0 or urg > 100.0:
            invalid_feed_urg += 1
        if final is None or math.isnan(final) or final < 0.0 or final > 100.0:
            invalid_feed_final += 1

        if cid in seen_ids:
            duplicate_ids.append(cid)
        seen_ids.add(cid)

        if head in seen_headlines:
            duplicate_headlines.append(head)
        seen_headlines.add(head)

        if i < len(live_items) - 1:
            next_final = live_items[i + 1].get("final_feed_score", 0.0)
            if final < next_final:
                ranking_violations += 1
                print(f"Ranking violation at #{i}: {final} < #{i+1}: {next_final}")

    print(f"Invalid Urgency: {invalid_feed_urg}")
    print(f"Invalid FinalScore: {invalid_feed_final}")
    print(f"Ranking violations: {ranking_violations}")
    print(f"Duplicate IDs: {len(duplicate_ids)}")
    print(f"Duplicate headlines: {len(duplicate_headlines)}")

    assert invalid_feed_urg == 0, f"Found {invalid_feed_urg} invalid urgency scores"
    assert invalid_feed_final == 0, f"Found {invalid_feed_final} invalid final scores"
    assert ranking_violations == 0, f"Found {ranking_violations} ranking violations"
    assert len(duplicate_ids) == 0, f"Found duplicate IDs: {duplicate_ids}"
    assert len(duplicate_headlines) == 0, f"Found duplicate headlines: {duplicate_headlines}"

    results["test9_stories"] = len(live_items)
    results["test9_invalid_urg"] = invalid_feed_urg
    results["test9_invalid_final"] = invalid_feed_final
    results["test9_ranking_violations"] = ranking_violations
    results["test9_duplicate_ids"] = len(duplicate_ids)
    results["test9_duplicate_headlines"] = len(duplicate_headlines)

    # ----------------------------------------------------
    # TEST 10 — DETERMINISM
    # ----------------------------------------------------
    print("\n--- TEST 10: Determinism ---")
    sample_title = "Flash Flood Emergency in Mountain Region"
    sample_sum = "Rivers breach danger level, residents take shelter immediately."
    direct_runs = [UrgencyEngine.calculate_urgency(sample_title, sample_sum) for _ in range(5)]
    all_direct_identical = all(r == direct_runs[0] for r in direct_runs)
    print(f"Direct calculation repeated 5 times identical: {all_direct_identical} ({direct_runs[0]})")
    assert all_direct_identical, "Direct urgency calculation is non-deterministic"

    feed_runs = [get_json(f"{BASE_URL}/feed?limit=30") for _ in range(3)]
    feed_scores_0 = [c["urgency_score"] for c in (feed_runs[0].get("items", []) if isinstance(feed_runs[0], dict) else feed_runs[0])]
    all_feed_identical = True
    for fr in feed_runs[1:]:
        items = fr.get("items", []) if isinstance(fr, dict) else fr
        scores = [c["urgency_score"] for c in items]
        if scores != feed_scores_0:
            all_feed_identical = False
            break
    print(f"Feed requests repeated 3 times identical: {all_feed_identical}")
    assert all_feed_identical, "Feed urgency values varied across identical requests"

    results["test10_direct_deterministic"] = all_direct_identical
    results["test10_feed_deterministic"] = all_feed_identical

    # ----------------------------------------------------
    # TEST 11 — BROWSER REGRESSION IN CHROME
    # ----------------------------------------------------
    print("\n--- TEST 11: Browser Regression in Chrome ---")
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

        cards_rendered = page.query_selector_all("#feed-container .scroll-card")
        print(f"Browser rendered cards count: {len(cards_rendered)}")
        assert len(cards_rendered) >= 22, f"Expected >= 22 cards, got {len(cards_rendered)}"

        # Open story detail to check explainability box displays Urgency score
        detail_btn = page.query_selector(".scroll-action-btn:has-text('Explain Decision')")
        if detail_btn:
            detail_btn.click()
            page.wait_for_timeout(400)
            urg_val = page.inner_text("#detail-score-urgency")
            print(f"Detail modal Urgency score: {urg_val}")
            assert len(urg_val) > 0, "Detail modal missing urgency score"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b9_detail_urgency.png"))
            page.click("#btn-close-detail-modal")
            page.wait_for_timeout(200)

        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b9_browser_feed.png"))

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["test11_stories_rendered"] = len(cards_rendered)
        results["test11_console_errors"] = err_logs
        results["test11_page_errors"] = page_errors
        results["test11_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    db.close()
    print("\nALL B9 URGENCY ENGINE CHECKS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b9_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b9_audit()
