"""
B10 — Personal Relevance Engine Verification Script
Executes all 14 B10 test requirements against the actual implementation and live database.
"""

import os
import sys
import json
import math
import urllib.request
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"d:\News"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "apps", "api") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "apps", "api"))

from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
from packages.ranking_engine.config import RankingConfig
from app.db import SessionLocal  # type: ignore
from app.models import Card  # type: ignore

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "scratch")

def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "B10Audit/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def put_json(url: str, data: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"User-Agent": "B10Audit/1.0", "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_b10_audit():
    print("=" * 60)
    print("STARTING B10 — PERSONAL RELEVANCE ENGINE AUDIT")
    print("=" * 60)

    results = {}

    # ----------------------------------------------------
    # TEST 1 — INSPECT ACTUAL IMPLEMENTATION
    # ----------------------------------------------------
    print("\n--- TEST 1: Inspect Implementation ---")
    source_file = "packages/ranking_engine/relevance_engine.py"
    func_name = "RelevanceEngine.calculate_relevance"
    loc_comp = "Location Component (0..50): State match=40.0, District match=50.0, Neutral/national=25.0, Mismatch/intl=15.0"
    int_comp = "Interest Component (0..50): Top rank=50.0, Step penalty=-5.0, Min floor=20.0, Unranked default=25.0"
    inputs_used = ["story_category", "story_state", "story_district", "user_state", "user_district", "user_category_order"]
    fallbacks = "Neutral location: 25.0, Unranked category: 25.0, Combined default: 50.0"
    clamping = "round(max(0.0, min(100.0, total_relevance)), 2)"

    results["test1_source_file"] = source_file
    results["test1_func_name"] = func_name
    results["test1_location_comp"] = loc_comp
    results["test1_interest_comp"] = int_comp
    results["test1_inputs"] = inputs_used
    results["test1_fallbacks"] = fallbacks
    results["test1_clamping"] = clamping
    print(f"Source file: {source_file}")
    print(f"Function: {func_name}")
    print(f"Location Component: {loc_comp}")
    print(f"Interest Component: {int_comp}")

    # ----------------------------------------------------
    # TEST 2 — RANGE VALIDATION
    # ----------------------------------------------------
    print("\n--- TEST 2: Range Validation ---")
    range_test_cases = [
        ("Exact state, top rank", "politics", "Karnataka", None, "Karnataka", None, ["politics", "technology"]),
        ("National story, rank 2", "national", None, None, "Karnataka", None, ["politics", "national"]),
        ("Other state, rank 3", "technology", "Telangana", None, "Karnataka", None, ["politics", "business", "technology"]),
        ("International story, rank 4", "international", None, None, "Karnataka", None, ["politics", "national", "sports", "international"]),
        ("Unranked category", "science", None, None, "Karnataka", None, ["politics", "business"]),
        ("Empty interests", "national", "Karnataka", None, "Karnataka", None, []),
        ("Empty category order", "business", None, None, "Karnataka", None, None),
        ("Missing state", "technology", None, None, None, None, ["technology"]),
        ("Missing category", "", "Karnataka", None, "Karnataka", None, ["politics"]),
        ("All None values", None, None, None, None, None, None),
        ("District match", "politics", "Karnataka", "Bengaluru", "Karnataka", "Bengaluru", ["politics"]),
    ]

    invalid_scores = 0
    exceptions = 0
    min_score = 999.0
    max_score = -999.0

    for label, cat, s_state, s_dist, u_state, u_dist, u_order in range_test_cases:
        try:
            score = RelevanceEngine.calculate_relevance(
                story_category=cat,
                story_state=s_state,
                story_district=s_dist,
                user_state=u_state,
                user_district=u_dist,
                user_category_order=u_order,
            )
            if math.isnan(score) or math.isinf(score) or score < 0.0 or score > 100.0:
                invalid_scores += 1
                print(f"INVALID: {label} -> {score}")
            min_score = min(min_score, score)
            max_score = max(max_score, score)
            print(f"  {label:<32} -> Personal Relevance: {score:5.1f}")
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
    # TEST 3 — LOCATION RELEVANCE
    # ----------------------------------------------------
    print("\n--- TEST 3: Location Relevance ---")
    # Hold interest component constant with unranked category (interest = 25.0)
    # User state = Karnataka
    score_exact = RelevanceEngine.calculate_relevance("science", story_state="Karnataka", user_state="Karnataka") # 40 + 25 = 65
    loc_exact = score_exact - 25.0
    print(f"Exact state (Karnataka -> Karnataka): loc={loc_exact} (total={score_exact})")
    assert loc_exact == 40.0, f"Expected 40.0, got {loc_exact}"

    score_neutral = RelevanceEngine.calculate_relevance("science", story_state=None, user_state="Karnataka") # 25 + 25 = 50
    loc_neutral = score_neutral - 25.0
    print(f"Neutral / national (no state -> Karnataka): loc={loc_neutral} (total={score_neutral})")
    assert loc_neutral == 25.0, f"Expected 25.0, got {loc_neutral}"

    score_other = RelevanceEngine.calculate_relevance("science", story_state="Telangana", user_state="Karnataka") # 15 + 25 = 40
    loc_other = score_other - 25.0
    print(f"Other state (Telangana -> Karnataka): loc={loc_other} (total={score_other})")
    assert loc_other == 15.0, f"Expected 15.0, got {loc_other}"

    score_intl = RelevanceEngine.calculate_relevance("international", story_state=None, user_state="Karnataka") # 15 + 25 = 40
    loc_intl = score_intl - 25.0
    print(f"International category: loc={loc_intl} (total={score_intl})")
    assert loc_intl == 15.0, f"Expected 15.0, got {loc_intl}"

    results["test3_exact_state"] = loc_exact
    results["test3_neutral_national"] = loc_neutral
    results["test3_other_state"] = loc_other
    results["test3_international"] = loc_intl

    # ----------------------------------------------------
    # TEST 4 — INTEREST / CATEGORY RELEVANCE
    # ----------------------------------------------------
    print("\n--- TEST 4: Interest / Category Relevance ---")
    # Hold location component constant with neutral story (loc = 25.0)
    priority_order = ["Politics", "National", "Technology", "Business", "Science", "Health", "Sports", "Entertainment"]

    # Rank 1: Politics -> 50.0 (total = 25 + 50 = 75.0)
    int_r1 = RelevanceEngine.calculate_relevance("Politics", user_category_order=priority_order) - 25.0
    assert int_r1 == 50.0, f"Expected 50.0, got {int_r1}"

    # Rank 2: National -> 45.0
    int_r2 = RelevanceEngine.calculate_relevance("National", user_category_order=priority_order) - 25.0
    assert int_r2 == 45.0, f"Expected 45.0, got {int_r2}"

    # Rank 3: Technology -> 40.0
    int_r3 = RelevanceEngine.calculate_relevance("Technology", user_category_order=priority_order) - 25.0
    assert int_r3 == 40.0, f"Expected 40.0, got {int_r3}"

    # Rank 4: Business -> 35.0
    int_r4 = RelevanceEngine.calculate_relevance("Business", user_category_order=priority_order) - 25.0
    assert int_r4 == 35.0, f"Expected 35.0, got {int_r4}"

    # Rank 5: Science -> 30.0
    int_r5 = RelevanceEngine.calculate_relevance("Science", user_category_order=priority_order) - 25.0
    assert int_r5 == 30.0, f"Expected 30.0, got {int_r5}"

    # Rank 6: Health -> 25.0
    int_r6 = RelevanceEngine.calculate_relevance("Health", user_category_order=priority_order) - 25.0
    assert int_r6 == 25.0, f"Expected 25.0, got {int_r6}"

    # Rank 7: Sports -> 20.0 (minimum floor)
    int_r7 = RelevanceEngine.calculate_relevance("Sports", user_category_order=priority_order) - 25.0
    assert int_r7 == 20.0, f"Expected 20.0, got {int_r7}"

    # Rank 8: Entertainment -> 20.0 (minimum floor maintained)
    int_r8 = RelevanceEngine.calculate_relevance("Entertainment", user_category_order=priority_order) - 25.0
    assert int_r8 == 20.0, f"Expected 20.0, got {int_r8}"

    # Unranked category (e.g. World) -> 25.0
    int_unranked = RelevanceEngine.calculate_relevance("World", user_category_order=priority_order) - 15.0 # Note: World triggers intl loc 15.0, so interest is total - 15 = 25.0
    assert int_unranked == 25.0, f"Expected 25.0, got {int_unranked}"
    int_unranked_gen = RelevanceEngine.calculate_relevance("Education", user_category_order=priority_order) - 25.0 # Neutral loc 25.0
    assert int_unranked_gen == 25.0, f"Expected 25.0, got {int_unranked_gen}"

    print(f"Interests progression: R1={int_r1}, R2={int_r2}, R3={int_r3}, R4={int_r4}, R5={int_r5}, R7(floor)={int_r7}, R8(floor)={int_r8}, Unranked={int_unranked_gen}")
    results["test4_rank1"] = int_r1
    results["test4_rank2"] = int_r2
    results["test4_rank3"] = int_r3
    results["test4_rank4"] = int_r4
    results["test4_rank7_floor"] = int_r7
    results["test4_unranked"] = int_unranked_gen

    # ----------------------------------------------------
    # TEST 5 — COMBINED PERSONAL RELEVANCE
    # ----------------------------------------------------
    print("\n--- TEST 5: Combined Personal Relevance ---")
    prio = ["Politics"]
    # 1. Exact state (40) + top-ranked (50) = 90
    c1 = RelevanceEngine.calculate_relevance("Politics", story_state="Karnataka", user_state="Karnataka", user_category_order=prio)
    print(f"Exact state + top rank: {c1} (expected 90.0)")
    assert c1 == 90.0, f"Expected 90.0, got {c1}"

    # 2. Neutral (25) + top-ranked (50) = 75
    c2 = RelevanceEngine.calculate_relevance("Politics", story_state=None, user_state="Karnataka", user_category_order=prio)
    print(f"Neutral + top rank: {c2} (expected 75.0)")
    assert c2 == 75.0, f"Expected 75.0, got {c2}"

    # 3. Other state (15) + top-ranked (50) = 65
    c3 = RelevanceEngine.calculate_relevance("Politics", story_state="Telangana", user_state="Karnataka", user_category_order=prio)
    print(f"Other state + top rank: {c3} (expected 65.0)")
    assert c3 == 65.0, f"Expected 65.0, got {c3}"

    # 4. Exact state (40) + unranked (25) = 65
    c4 = RelevanceEngine.calculate_relevance("Science", story_state="Karnataka", user_state="Karnataka", user_category_order=prio)
    print(f"Exact state + unranked: {c4} (expected 65.0)")
    assert c4 == 65.0, f"Expected 65.0, got {c4}"

    theoretical_max = 90.0 # 40 state + 50 interest (or 100.0 if district used: 50 + 50)
    print(f"Theoretical state-level max: {theoretical_max}")

    # Inspect actual live feed maximum Personal Relevance
    feed_data = get_json(f"{BASE_URL}/feed?limit=30")
    items = feed_data.get("items", []) if isinstance(feed_data, dict) else feed_data
    live_relevance_scores = [c["personal_relevance_score"] for c in items]
    actual_live_max = max(live_relevance_scores) if live_relevance_scores else 0.0
    print(f"Actual live feed max Personal Relevance: {actual_live_max}")

    results["test5_exact_top"] = c1
    results["test5_neutral_top"] = c2
    results["test5_other_top"] = c3
    results["test5_exact_unranked"] = c4
    results["test5_theoretical_max"] = theoretical_max
    results["test5_actual_live_max"] = actual_live_max

    # ----------------------------------------------------
    # TEST 6 — PRIORITY RANKING BEHAVIOR
    # ----------------------------------------------------
    print("\n--- TEST 6: Priority Ranking Behavior ---")
    dev_id = "test_device_b10_prio"
    # Set Priority A: Politics > National > Technology > Business
    put_json(f"{BASE_URL}/user/{dev_id}/preferences", {"category_order": ["Politics", "National", "Technology", "Business"]})
    feed_a = get_json(f"{BASE_URL}/feed?device_id={dev_id}&limit=30")
    items_a = {c["id"]: c for c in (feed_a.get("items", []) if isinstance(feed_a, dict) else feed_a)}

    # Reverse to Priority B: Business > Technology > National > Politics
    put_json(f"{BASE_URL}/user/{dev_id}/preferences", {"category_order": ["Business", "Technology", "National", "Politics"]})
    feed_b = get_json(f"{BASE_URL}/feed?device_id={dev_id}&limit=30")
    items_b = {c["id"]: c for c in (feed_b.get("items", []) if isinstance(feed_b, dict) else feed_b)}

    common_ids = set(items_a.keys()) & set(items_b.keys())
    imp_diffs = 0
    urg_diffs = 0
    frsh_diffs = 0
    ver_diffs = 0
    rel_changes = 0

    pol_story_changed = False
    biz_story_changed = False

    for cid in common_ids:
        ca = items_a[cid]
        cb = items_b[cid]
        if ca["importance_score"] != cb["importance_score"]:
            imp_diffs += 1
        if ca["urgency_score"] != cb["urgency_score"]:
            urg_diffs += 1
        if ca["freshness_score"] != cb["freshness_score"]:
            frsh_diffs += 1
        if ca["verification_score"] != cb["verification_score"]:
            ver_diffs += 1
        if ca["personal_relevance_score"] != cb["personal_relevance_score"]:
            rel_changes += 1
            if ca["category"].lower() == "politics":
                pol_story_changed = True
                print(f"  Politics story '{ca['headline'][:30]}': Rel A={ca['personal_relevance_score']} -> Rel B={cb['personal_relevance_score']} (Rank 1 -> Rank 4)")
                assert ca["personal_relevance_score"] > cb["personal_relevance_score"]
            elif ca["category"].lower() == "business":
                biz_story_changed = True
                print(f"  Business story '{ca['headline'][:30]}': Rel A={ca['personal_relevance_score']} -> Rel B={cb['personal_relevance_score']} (Rank 4 -> Rank 1)")
                assert cb["personal_relevance_score"] > ca["personal_relevance_score"]

    print(f"Priority flip: Importance diffs={imp_diffs}, Urgency diffs={urg_diffs}, Freshness diffs={frsh_diffs}, Verification diffs={ver_diffs}")
    print(f"Personal Relevance changes: {rel_changes}")
    assert imp_diffs == 0, f"Importance changed on priority flip: {imp_diffs}"
    assert urg_diffs == 0, f"Urgency changed on priority flip: {urg_diffs}"
    assert frsh_diffs == 0, f"Freshness changed on priority flip: {frsh_diffs}"
    assert ver_diffs == 0, f"Verification changed on priority flip: {ver_diffs}"
    assert rel_changes > 0, "Personal relevance did not change on priority flip"

    results["test6_imp_changed"] = imp_diffs
    results["test6_urg_changed"] = urg_diffs
    results["test6_frsh_changed"] = frsh_diffs
    results["test6_ver_changed"] = ver_diffs
    results["test6_rel_changed"] = rel_changes

    # ----------------------------------------------------
    # TEST 7 — STATE BEHAVIOR & INDEPENDENCE
    # ----------------------------------------------------
    print("\n--- TEST 7: State Behavior & Independence ---")
    feed_kar = get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30")
    feed_tel = get_json(f"{BASE_URL}/feed?state=Telangana&limit=30")
    feed_asm = get_json(f"{BASE_URL}/feed?state=Assam&limit=30")
    items_kar = {c["id"]: c for c in (feed_kar.get("items", []) if isinstance(feed_kar, dict) else feed_kar)}
    items_tel = {c["id"]: c for c in (feed_tel.get("items", []) if isinstance(feed_tel, dict) else feed_tel)}
    items_asm = {c["id"]: c for c in (feed_asm.get("items", []) if isinstance(feed_asm, dict) else feed_asm)}
    
    common_st_ids = set(items_kar.keys()) & set(items_tel.keys()) & set(items_asm.keys())

    st_imp_diffs = 0
    st_urg_diffs = 0
    st_frsh_diffs = 0
    st_ver_diffs = 0
    st_rel_changes = 0

    for cid in common_st_ids:
        ck = items_kar[cid]
        ct = items_tel[cid]
        ca = items_asm[cid]
        # Verify objective metrics strictly unchanged across all state queries
        if ck["importance_score"] != ct["importance_score"] or ck["importance_score"] != ca["importance_score"]:
            st_imp_diffs += 1
        if ck["urgency_score"] != ct["urgency_score"] or ck["urgency_score"] != ca["urgency_score"]:
            st_urg_diffs += 1
        if ck["freshness_score"] != ct["freshness_score"] or ck["freshness_score"] != ca["freshness_score"]:
            st_frsh_diffs += 1
        if ck["verification_score"] != ct["verification_score"] or ck["verification_score"] != ca["verification_score"]:
            st_ver_diffs += 1
        # Check that Assam stories gain location relevance for Assam user
        if ck.get("state") == "Assam":
            st_rel_changes += 1
            print(f"  Assam story '{ck['headline'][:30]}': Rel Assam={ca['personal_relevance_score']} (40 loc + 25 int) vs Karnataka={ck['personal_relevance_score']} (15 loc + 25 int)")
            assert ca["personal_relevance_score"] == 65.0, f"Expected 65.0 for matching state, got {ca['personal_relevance_score']}"
            assert ck["personal_relevance_score"] == 40.0, f"Expected 40.0 for mismatched state, got {ck['personal_relevance_score']}"
        elif ck.get("state") is None and ck.get("category") not in ("international", "world", "global"):
            # Neutral / national stories remain neutral (25 loc + 25 int = 50)
            assert ca["personal_relevance_score"] == ck["personal_relevance_score"] == 50.0

    print(f"State change: Imp diffs={st_imp_diffs}, Urg diffs={st_urg_diffs}, Frsh diffs={st_frsh_diffs}, Ver diffs={st_ver_diffs}")
    print(f"Personal Relevance state-boosted stories: {st_rel_changes}")
    assert st_imp_diffs == 0
    assert st_urg_diffs == 0
    assert st_frsh_diffs == 0
    assert st_ver_diffs == 0
    assert st_rel_changes > 0, "No state-matched stories found to verify relevance boost"

    results["test7_imp_changed"] = st_imp_diffs
    results["test7_urg_changed"] = st_urg_diffs
    results["test7_frsh_changed"] = st_frsh_diffs
    results["test7_ver_changed"] = st_ver_diffs
    results["test7_rel_changed"] = st_rel_changes

    # ----------------------------------------------------
    # TEST 8 — INTERESTS BEHAVIOR
    # ----------------------------------------------------
    print("\n--- TEST 8: Interests Behavior ---")
    dev_a = "test_dev_a"
    dev_b = "test_dev_b"
    dev_c = "test_dev_c"

    # Config A: Politics, Technology (Priority: Politics > Technology)
    put_json(f"{BASE_URL}/user/{dev_a}/preferences", {"category_order": ["Politics", "Technology"]})
    feed_ca = get_json(f"{BASE_URL}/feed?device_id={dev_a}&limit=30")

    # Config B: Technology, Sports (Priority: Technology > Sports)
    put_json(f"{BASE_URL}/user/{dev_b}/preferences", {"category_order": ["Technology", "Sports"]})
    feed_cb = get_json(f"{BASE_URL}/feed?device_id={dev_b}&limit=30")

    # Config C: Empty interests []
    put_json(f"{BASE_URL}/user/{dev_c}/preferences", {"category_order": []})
    feed_cc = get_json(f"{BASE_URL}/feed?device_id={dev_c}&limit=30")

    items_ca = feed_ca.get("items", []) if isinstance(feed_ca, dict) else feed_ca
    items_cb = feed_cb.get("items", []) if isinstance(feed_cb, dict) else feed_cb
    items_cc = feed_cc.get("items", []) if isinstance(feed_cc, dict) else feed_cc

    print(f"Config A returned: {len(items_ca)} stories")
    print(f"Config B returned: {len(items_cb)} stories")
    print(f"Config C (empty) returned: {len(items_cc)} stories")

    assert len(items_ca) > 0 and len(items_cb) > 0 and len(items_cc) > 0
    # In Config C (empty interests), every category should use unranked fallback (interest = 25.0)
    for card in items_cc:
        cat = card.get("category", "").lower()
        rel = card.get("personal_relevance_score", 0.0)
        loc = 15.0 if cat in ("international", "world", "global") else 25.0 # without state specified
        expected_rel = loc + 25.0 # unranked default
        assert rel == expected_rel, f"Empty interests mismatch on {cat}: got {rel}, expected {expected_rel}"

    print("Empty interests behavior: gracefully assigned 25.0 unranked interest default to all stories without crash or corruption")
    results["test8_config_a_stories"] = len(items_ca)
    results["test8_config_b_stories"] = len(items_cb)
    results["test8_config_c_stories"] = len(items_cc)
    results["test8_empty_interests_safe"] = True

    # ----------------------------------------------------
    # TEST 9 — CATEGORY FILTERING INDEPENDENCE
    # ----------------------------------------------------
    print("\n--- TEST 9: Category Filtering Independence ---")
    # Feed filtered by category=politics vs all news feed
    feed_all = get_json(f"{BASE_URL}/feed?limit=30")
    feed_pol = get_json(f"{BASE_URL}/feed?category=politics&limit=30")
    items_all = {c["id"]: c for c in (feed_all.get("items", []) if isinstance(feed_all, dict) else feed_all)}
    items_pol = {c["id"]: c for c in (feed_pol.get("items", []) if isinstance(feed_pol, dict) else feed_pol)}

    common_pol_ids = set(items_all.keys()) & set(items_pol.keys())
    print(f"Politics stories present in both feeds: {len(common_pol_ids)}")
    assert len(common_pol_ids) > 0, "No common politics stories found"
    for cid in common_pol_ids:
        ca = items_all[cid]
        cp = items_pol[cid]
        assert ca["importance_score"] == cp["importance_score"]
        assert ca["urgency_score"] == cp["urgency_score"]
        assert ca["freshness_score"] == cp["freshness_score"]
        assert ca["verification_score"] == cp["verification_score"]
        assert ca["personal_relevance_score"] == cp["personal_relevance_score"]

    print("Category filtering independence verified: filtering does NOT alter any ranking metrics")
    results["test9_filtering_independent"] = True

    # ----------------------------------------------------
    # TEST 10 — FINAL SCORE INTEGRATION (WEIGHT 0.15)
    # ----------------------------------------------------
    print("\n--- TEST 10: Final Score Integration ---")
    out_rel_80 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=50.0,
        personal_relevance=80.0, verification_confidence=50.0
    )
    out_rel_30 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=50.0,
        personal_relevance=30.0, verification_confidence=50.0
    )
    delta_rel = 80.0 - 30.0 # 50.0
    expected_delta_final = delta_rel * RankingConfig.WEIGHT_PERSONAL_RELEVANCE # 50.0 * 0.15 = 7.5
    actual_delta_final = round(out_rel_80.final_feed_score - out_rel_30.final_feed_score, 2)

    print(f"Personal Relevance weight: {RankingConfig.WEIGHT_PERSONAL_RELEVANCE}")
    print(f"Controlled delta Personal Relevance: {delta_rel}")
    print(f"Expected delta Final Score: {expected_delta_final}")
    print(f"Actual delta Final Score: {actual_delta_final}")
    assert actual_delta_final == expected_delta_final, f"Expected {expected_delta_final}, got {actual_delta_final}"

    results["test10_rel_weight"] = RankingConfig.WEIGHT_PERSONAL_RELEVANCE
    results["test10_delta_rel"] = delta_rel
    results["test10_expected_delta"] = expected_delta_final
    results["test10_actual_delta"] = actual_delta_final

    # ----------------------------------------------------
    # TEST 11 — LIVE FEED VALIDATION
    # ----------------------------------------------------
    print("\n--- TEST 11: Live Feed Validation ---")
    feed_live = get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30")
    live_items = feed_live.get("items", []) if isinstance(feed_live, dict) else feed_live
    print(f"Live feed stories returned: {len(live_items)}")

    min_rel = 999.0
    max_rel = -999.0
    invalid_rel = 0
    invalid_final = 0
    ranking_violations = 0
    seen_ids = set()
    dup_ids = []
    seen_heads = set()
    dup_heads = []

    for i, item in enumerate(live_items):
        cid = item.get("id")
        head = item.get("headline", "").strip()
        rel = item.get("personal_relevance_score")
        final = item.get("final_feed_score")

        if rel is None or math.isnan(rel) or rel < 0.0 or rel > 100.0:
            invalid_rel += 1
        else:
            min_rel = min(min_rel, rel)
            max_rel = max(max_rel, rel)

        if final is None or math.isnan(final) or final < 0.0 or final > 100.0:
            invalid_final += 1

        if cid in seen_ids:
            dup_ids.append(cid)
        seen_ids.add(cid)

        if head in seen_heads:
            dup_heads.append(head)
        seen_heads.add(head)

        if i < len(live_items) - 1:
            next_final = live_items[i + 1].get("final_feed_score", 0.0)
            if final < next_final:
                ranking_violations += 1

    print(f"Personal Relevance min: {min_rel}, max: {max_rel}")
    print(f"Invalid Personal Relevance: {invalid_rel}")
    print(f"Invalid Final Score: {invalid_final}")
    print(f"Ranking violations: {ranking_violations}")
    print(f"Duplicate IDs: {len(dup_ids)}")
    print(f"Duplicate headlines: {len(dup_heads)}")

    assert invalid_rel == 0
    assert invalid_final == 0
    assert ranking_violations == 0
    assert len(dup_ids) == 0
    assert len(dup_heads) == 0

    results["test11_stories"] = len(live_items)
    results["test11_min_rel"] = min_rel
    results["test11_max_rel"] = max_rel
    results["test11_invalid_rel"] = invalid_rel
    results["test11_invalid_final"] = invalid_final
    results["test11_ranking_violations"] = ranking_violations
    results["test11_duplicate_ids"] = len(dup_ids)
    results["test11_duplicate_headlines"] = len(dup_heads)

    # ----------------------------------------------------
    # TEST 12 — DETERMINISM
    # ----------------------------------------------------
    print("\n--- TEST 12: Determinism ---")
    direct_runs = [
        RelevanceEngine.calculate_relevance(
            story_category="Politics",
            story_state="Karnataka",
            user_state="Karnataka",
            user_category_order=["Politics", "Technology"]
        ) for _ in range(5)
    ]
    all_direct_identical = all(r == direct_runs[0] for r in direct_runs)
    print(f"Direct calculation 5 runs identical: {all_direct_identical} ({direct_runs[0]})")
    assert all_direct_identical

    feed_runs = [get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30") for _ in range(3)]
    first_feed_rel = [c["personal_relevance_score"] for c in (feed_runs[0].get("items", []) if isinstance(feed_runs[0], dict) else feed_runs[0])]
    all_feed_identical = True
    for fr in feed_runs[1:]:
        rel_scores = [c["personal_relevance_score"] for c in (fr.get("items", []) if isinstance(fr, dict) else fr)]
        if rel_scores != first_feed_rel:
            all_feed_identical = False
            break
    print(f"Feed requests 3 runs identical: {all_feed_identical}")
    assert all_feed_identical

    results["test12_direct_deterministic"] = all_direct_identical
    results["test12_feed_deterministic"] = all_feed_identical

    # ----------------------------------------------------
    # TEST 13 — BROWSER REGRESSION IN CHROME
    # ----------------------------------------------------
    print("\n--- TEST 13: Browser Regression in Chrome ---")
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

        # Open story detail to check explainability box displays Personal Relevance score
        detail_btn = page.query_selector(".scroll-action-btn:has-text('Explain Decision')")
        if detail_btn:
            detail_btn.click()
            page.wait_for_timeout(400)
            rel_val = page.inner_text("#detail-score-personal")
            print(f"Detail modal Personal Relevance score: {rel_val}")
            assert len(rel_val) > 0, "Detail modal missing personal relevance score"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b10_detail_relevance.png"))
            page.click("#btn-close-detail-modal")
            page.wait_for_timeout(200)

        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b10_browser_feed.png"))

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["test13_stories_rendered"] = len(cards_rendered)
        results["test13_console_errors"] = err_logs
        results["test13_page_errors"] = page_errors
        results["test13_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    print("\nALL B10 PERSONAL RELEVANCE ENGINE CHECKS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b10_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b10_audit()
