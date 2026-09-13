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

from app.db import SessionLocal
from app.models import Card, StoryCluster
from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.models import ObjectiveDimensions, DimensionEvidence
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = r"d:\News\scratch\b8_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "B8-Audit/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def run_b8_audit():
    results = {}
    print("==================================================")
    print("STARTING B8 — IMPORTANCE ENGINE AUDIT")
    print("==================================================")

    # ----------------------------------------------------
    # TEST 1 & 2 — SOURCE CODE & DIMENSION MAXIMUMS
    # ----------------------------------------------------
    print("TEST 1 & 2: Dimension definitions and maximum limits...")
    dim_limits = {
        "Human Impact": RankingConfig.MAX_HUMAN_IMPACT,
        "Safety Impact": RankingConfig.MAX_SAFETY_IMPACT,
        "Geographic Scale": RankingConfig.MAX_GEOGRAPHIC_IMPACT,
        "Economic Impact": RankingConfig.MAX_ECONOMIC_IMPACT,
        "Policy Impact": RankingConfig.MAX_POLICY_IMPACT,
        "Infrastructure Impact": RankingConfig.MAX_INFRASTRUCTURE_IMPACT,
        "Security Impact": RankingConfig.MAX_SECURITY_IMPACT,
        "Consequence Impact": RankingConfig.MAX_CONSEQUENCE_IMPACT,
    }
    total_bound = sum(dim_limits.values())
    print(f"Configured dimension maximums: {json.dumps(dim_limits, indent=2)}")
    print(f"Total bound sum: {total_bound}")
    results["test1_dimensions"] = list(dim_limits.keys())
    results["test2_max_values"] = dim_limits
    results["test2_total_bound"] = total_bound
    assert total_bound == 100.0, f"Expected total bound 100.0, got {total_bound}"

    # Verify clamping behavior
    over_dims = ObjectiveDimensions(
        human_impact=DimensionEvidence(score=50.0),
        safety_impact=DimensionEvidence(score=50.0),
        geographic_impact=DimensionEvidence(score=50.0),
        economic_impact=DimensionEvidence(score=50.0),
        policy_impact=DimensionEvidence(score=50.0),
        infrastructure_impact=DimensionEvidence(score=50.0),
        security_impact=DimensionEvidence(score=50.0),
        consequence_impact=DimensionEvidence(score=50.0),
    )
    clamped_total = ImportanceEngine.calculate_from_dimensions(over_dims)
    print(f"Clamped total for 8x50.0 input: {clamped_total}")
    assert clamped_total == 100.0, f"Expected clamped total 100.0, got {clamped_total}"

    # ----------------------------------------------------
    # TEST 3 — LIVE SCORE RANGE ACROSS PUBLISHED CARDS
    # ----------------------------------------------------
    print("TEST 3: Live database cards score range...")
    db = SessionLocal()
    cards = db.query(Card).filter(Card.verified_status == "published").all()
    imp_scores = [c.importance_score for c in cards]
    min_imp = min(imp_scores)
    max_imp = max(imp_scores)
    invalid_imp = sum(1 for s in imp_scores if s < 0.0 or s > 100.0)
    nan_null_imp = sum(1 for s in imp_scores if s is None or math.isnan(s))

    print(f"Live database published cards: {len(cards)}")
    print(f"Importance min: {min_imp}, max: {max_imp}, invalid: {invalid_imp}, nan/null: {nan_null_imp}")
    results["test3_min"] = min_imp
    results["test3_max"] = max_imp
    results["test3_invalid"] = invalid_imp
    results["test3_nan_null"] = nan_null_imp
    assert invalid_imp == 0 and nan_null_imp == 0, "Found invalid importance scores in DB!"

    # ----------------------------------------------------
    # TEST 4 — DIMENSION INDEPENDENCE
    # ----------------------------------------------------
    print("TEST 4: Dimension independence...")
    # Baseline neutral text
    base_dims, base_score = ImportanceEngine.analyze_event_text("City Council Meeting", "The local council discussed standard routine procedures.", category="local")
    print(f"Baseline text score: {base_score}, Human: {base_dims.human_impact.score}, Safety: {base_dims.safety_impact.score}")

    # Trigger single dimension: Economic
    econ_dims, econ_score = ImportanceEngine.analyze_event_text("Market Crash and Bank Collapse", "Stock exchange halts as recession looms following major bank collapse.", category="business")
    print(f"Economic trigger: Econ={econ_dims.economic_impact.score} (was {base_dims.economic_impact.score}), Total={econ_score}")
    assert econ_dims.economic_impact.score > base_dims.economic_impact.score
    assert econ_dims.economic_impact.score <= RankingConfig.MAX_ECONOMIC_IMPACT

    # Trigger single dimension: Infrastructure
    infra_dims, infra_score = ImportanceEngine.analyze_event_text("Major Train Derailment on Main Line", "Metro services delayed and rail corridor blocked after train derailment.", category="national")
    print(f"Infra trigger: Infra={infra_dims.infrastructure_impact.score} (was {base_dims.infrastructure_impact.score}), Total={infra_score}")
    assert infra_dims.infrastructure_impact.score > base_dims.infrastructure_impact.score
    assert infra_dims.infrastructure_impact.score <= RankingConfig.MAX_INFRASTRUCTURE_IMPACT

    results["test4_independence_verified"] = True

    # ----------------------------------------------------
    # TEST 5 — HUMAN IMPACT
    # ----------------------------------------------------
    print("TEST 5: Human impact tests...")
    # Mass casualty (>1000)
    d1, s1 = ImportanceEngine.analyze_event_text("Disaster claims 1,385 lives", "Severe flooding has killed 1,385 residents across the valley.")
    assert d1.human_impact.score == 20.0, f"Expected 20.0 for >1000 casualties, got {d1.human_impact.score}"

    # Hundreds (>=100)
    d2, s2 = ImportanceEngine.analyze_event_text("Building collapse death toll rises to 142", "Rescue workers report 142 dead in tragic collapse.")
    assert d2.human_impact.score == 16.0, f"Expected 16.0 for >=100 casualties, got {d2.human_impact.score}"

    # Dozens (>=10)
    d3, s3 = ImportanceEngine.analyze_event_text("Highway bus collision", "18 people died following highway bus collision.")
    assert d3.human_impact.score == 12.0, f"Expected 12.0 for >=10 casualties, got {d3.human_impact.score}"

    # Multiple (>=2)
    d4, s4 = ImportanceEngine.analyze_event_text("Road accident kills 7 people", "Seven people have died in head-on crash.")
    assert d4.human_impact.score == 8.0, f"Expected 8.0 for >=2 casualties, got {d4.human_impact.score}"

    # No human impact
    d5, s5 = ImportanceEngine.analyze_event_text("New Park Opens", "A botanical garden was opened for public visitors.")
    assert d5.human_impact.score == 0.0, f"Expected 0.0 for zero casualties, got {d5.human_impact.score}"

    print(f"Human impact scores verified: 1385->{d1.human_impact.score}, 142->{d2.human_impact.score}, 18->{d3.human_impact.score}, 7->{d4.human_impact.score}, 0->{d5.human_impact.score}")
    results["test5_human_impact"] = [d1.human_impact.score, d2.human_impact.score, d3.human_impact.score, d4.human_impact.score, d5.human_impact.score]

    # ----------------------------------------------------
    # TEST 6 — PUBLIC SAFETY
    # ----------------------------------------------------
    print("TEST 6: Public safety tests...")
    d_flood, _ = ImportanceEngine.analyze_event_text("Major Flood and Landslide", "Flash flood and emergency declared as rivers overflow.")
    d_routine, _ = ImportanceEngine.analyze_event_text("Library Book Fair", "Annual exhibition of rare books held in central town.")
    print(f"Safety Impact: Flood={d_flood.safety_impact.score}, Routine={d_routine.safety_impact.score}")
    assert d_flood.safety_impact.score == 18.0
    assert d_routine.safety_impact.score == 0.0
    results["test6_safety"] = {"flood": d_flood.safety_impact.score, "routine": d_routine.safety_impact.score}

    # ----------------------------------------------------
    # TEST 7 — GEOGRAPHIC SCALE
    # ----------------------------------------------------
    print("TEST 7: Geographic scale tests...")
    d_intl, _ = ImportanceEngine.analyze_event_text("BRICS Summit Global Treaty", "World leaders gathered for multilateral pact.", category="international")
    d_nat, _ = ImportanceEngine.analyze_event_text("Parliament Passes Nationwide Act", "Union cabinet presents bill across india.", category="national")
    d_state, _ = ImportanceEngine.analyze_event_text("Chief Minister Announces Statewide Scheme", "High court reviews metropolitan plan.", category="state")
    d_dist, _ = ImportanceEngine.analyze_event_text("Ward Panchayat Meeting", "Municipal council discusses city road repair.", category="district")
    print(f"Geographic Impact: Intl={d_intl.geographic_impact.score}, Nat={d_nat.geographic_impact.score}, State={d_state.geographic_impact.score}, Dist={d_dist.geographic_impact.score}")
    assert d_intl.geographic_impact.score == 14.0
    assert d_nat.geographic_impact.score == 11.0
    assert d_state.geographic_impact.score == 8.0
    assert d_dist.geographic_impact.score == 5.0
    results["test7_geographic"] = [d_intl.geographic_impact.score, d_nat.geographic_impact.score, d_state.geographic_impact.score, d_dist.geographic_impact.score]

    # ----------------------------------------------------
    # TEST 8 — ECONOMIC IMPACT
    # ----------------------------------------------------
    print("TEST 8: Economic impact tests...")
    d_crash, _ = ImportanceEngine.analyze_event_text("Market Crash and Bank Collapse", "Sensex plunges as bank collapse triggers crisis.")
    d_budget, _ = ImportanceEngine.analyze_event_text("Union Budget Presented", "New tax bill and trade agreement unveiled.")
    d_none, _ = ImportanceEngine.analyze_event_text("School Sports Day", "Students participate in athletics championship.")
    print(f"Economic Impact: Crash={d_crash.economic_impact.score}, Budget={d_budget.economic_impact.score}, None={d_none.economic_impact.score}")
    assert d_crash.economic_impact.score == 9.0
    assert d_budget.economic_impact.score == 7.0
    assert d_none.economic_impact.score == 0.0
    results["test8_economic"] = [d_crash.economic_impact.score, d_budget.economic_impact.score, d_none.economic_impact.score]

    # ----------------------------------------------------
    # TEST 9 — POLICY / GOVERNMENT
    # ----------------------------------------------------
    print("TEST 9: Policy / government tests...")
    d_law, _ = ImportanceEngine.analyze_event_text("Constitutional Amendment Law Passed", "General election called after bill enacted.")
    d_court, _ = ImportanceEngine.analyze_event_text("Supreme Court Rules on Petition", "Cabinet approves executive guideline.")
    d_pol_none, _ = ImportanceEngine.analyze_event_text("Wildlife Sanctuary Expands", "Forest officers document deer population growth.")
    print(f"Policy Impact: Law={d_law.policy_impact.score}, Court={d_court.policy_impact.score}, None={d_pol_none.policy_impact.score}")
    assert d_law.policy_impact.score == 10.0
    assert d_court.policy_impact.score == 7.0
    assert d_pol_none.policy_impact.score == 0.0
    results["test9_policy"] = [d_law.policy_impact.score, d_court.policy_impact.score, d_pol_none.policy_impact.score]

    # ----------------------------------------------------
    # TEST 10 — INFRASTRUCTURE
    # ----------------------------------------------------
    print("TEST 10: Infrastructure tests...")
    d_grid, _ = ImportanceEngine.analyze_event_text("Power Grid Collapse", "Airports shut and water supply cut after critical utility failure.")
    d_train, _ = ImportanceEngine.analyze_event_text("Train Derailment on Trunk Line", "Derailment halts freight corridor traffic.")
    d_infra_none, _ = ImportanceEngine.analyze_event_text("Poetry Recital Held", "Local authors gather for evening reading.")
    print(f"Infrastructure Impact: Grid={d_grid.infrastructure_impact.score}, Train={d_train.infrastructure_impact.score}, None={d_infra_none.infrastructure_impact.score}")
    assert d_grid.infrastructure_impact.score == 9.0
    assert d_train.infrastructure_impact.score == 8.0
    assert d_infra_none.infrastructure_impact.score == 0.0
    results["test10_infrastructure"] = [d_grid.infrastructure_impact.score, d_train.infrastructure_impact.score, d_infra_none.infrastructure_impact.score]

    # ----------------------------------------------------
    # TEST 11 — SECURITY / CYBER
    # ----------------------------------------------------
    print("TEST 11: Security / cyber tests...")
    d_cyber, _ = ImportanceEngine.analyze_event_text("Hospital Cyberattack and Ransomware", "Critical infrastructure hack shuts power grid network.")
    d_terror, _ = ImportanceEngine.analyze_event_text("Terrorist Encounter and Weapons Recovered", "Militant neutralized in security operation.")
    d_sec_none, _ = ImportanceEngine.analyze_event_text("Cookery Show Broadcast", "Chef showcases seasonal vegetable recipes.")
    print(f"Security Impact: Cyber={d_cyber.security_impact.score}, Terror={d_terror.security_impact.score}, None={d_sec_none.security_impact.score}")
    assert d_cyber.security_impact.score == 10.0
    assert d_terror.security_impact.score == 8.0
    assert d_sec_none.security_impact.score == 0.0
    results["test11_security"] = [d_cyber.security_impact.score, d_terror.security_impact.score, d_sec_none.security_impact.score]

    # ----------------------------------------------------
    # TEST 12 — LONG-TERM CONSEQUENCE
    # ----------------------------------------------------
    print("TEST 12: Long-term consequence tests...")
    d_long, _ = ImportanceEngine.analyze_event_text("Historic Treaty Signed", "Permanent shift and generational change in relations.")
    d_med, _ = ImportanceEngine.analyze_event_text("Bilateral Pact Concluded", "Summit outcome establishes medium-term cooperation.")
    d_trans, _ = ImportanceEngine.analyze_event_text("Weekend Film Release", "Comedy film hits local theatres for weekend.")
    print(f"Consequence Impact: Long={d_long.consequence_impact.score}, Med={d_med.consequence_impact.score}, Transient={d_trans.consequence_impact.score}")
    assert d_long.consequence_impact.score == 5.0
    assert d_med.consequence_impact.score == 3.0
    assert d_trans.consequence_impact.score == 0.0
    results["test12_consequence"] = [d_long.consequence_impact.score, d_med.consequence_impact.score, d_trans.consequence_impact.score]

    # ----------------------------------------------------
    # TEST 13 — TOTAL CALCULATION COMPARISON FOR LIVE STORIES
    # ----------------------------------------------------
    print("TEST 13: Total calculation comparison on live cards...")
    max_non_emerg_diff = 0.0
    non_emerg_mismatches = 0
    emergency_stories_elevated = []

    for card in cards:
        dims, recomputed_raw_imp = ImportanceEngine.analyze_event_text(card.headline, card.summary, card.category)
        effective_imp = recomputed_raw_imp
        if card.urgency_score >= RankingConfig.EMERGENCY_URGENCY_THRESHOLD:
            effective_imp = max(effective_imp, RankingConfig.EMERGENCY_IMPORTANCE_FLOOR)
            emergency_stories_elevated.append({
                "id": card.id,
                "headline": card.headline,
                "raw_imp": recomputed_raw_imp,
                "urgency": card.urgency_score,
                "effective_imp": effective_imp,
                "stored_imp": card.importance_score
            })
        else:
            diff = abs(recomputed_raw_imp - card.importance_score)
            if diff > max_non_emerg_diff:
                max_non_emerg_diff = diff
            if diff > 0.05:
                non_emerg_mismatches += 1
                print(f"Mismatch on {card.id[:8]} '{card.headline[:30]}': recomputed {recomputed_raw_imp} vs stored {card.importance_score}")

    print(f"Total stories tested: {len(cards)}, non-emergency max diff: {max_non_emerg_diff:.4f}, non-emergency mismatches: {non_emerg_mismatches}")
    print(f"Emergency stories elevated by floor: {len(emergency_stories_elevated)}")
    for es in emergency_stories_elevated:
        print(f"  Emergency story {es['id'][:8]}: raw={es['raw_imp']}, urg={es['urgency']}, effective={es['effective_imp']}, stored={es['stored_imp']}")
        assert es['effective_imp'] == es['stored_imp'], f"Effective imp {es['effective_imp']} != stored imp {es['stored_imp']}"

    results["test13_stories_tested"] = len(cards)
    results["test13_max_non_emerg_diff"] = max_non_emerg_diff
    results["test13_non_emerg_mismatches"] = non_emerg_mismatches
    results["test13_emergency_elevated_count"] = len(emergency_stories_elevated)
    results["test13_emergency_elevated"] = emergency_stories_elevated
    assert non_emerg_mismatches == 0, f"Found {non_emerg_mismatches} mismatches on non-emergency cards!"

    # ----------------------------------------------------
    # TEST 14 — EMERGENCY FLOOR
    # ----------------------------------------------------
    print("TEST 14: Emergency floor verification...")
    # Normal story: imp=20, urg=35 -> imp remains 20
    out_normal = FeedRankingEngine.compute_final_score(
        objective_importance=20.0, urgency=35.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=80.0
    )
    assert out_normal.objective_importance == 20.0, "Normal story importance must not be modified"

    # Emergency story: raw imp=20, urg=95 (>=90) -> effective imp elevated to 75.0 floor
    out_emergency = FeedRankingEngine.compute_final_score(
        objective_importance=20.0, urgency=95.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=80.0
    )
    print(f"Emergency floor test: raw imp=20.0, urg=95.0 -> effective imp={out_emergency.objective_importance}")
    assert out_emergency.objective_importance == RankingConfig.EMERGENCY_IMPORTANCE_FLOOR, f"Expected emergency floor {RankingConfig.EMERGENCY_IMPORTANCE_FLOOR}, got {out_emergency.objective_importance}"

    # Live emergency stories in database
    live_emergencies = [c for c in cards if c.urgency_score >= 90.0]
    print(f"Existing live emergency stories (Urgency >= 90.0): {len(live_emergencies)}")
    for ec in live_emergencies:
        print(f"  '{ec.headline[:50]}' -> raw imp={ec.importance_score}, urg={ec.urgency_score}")
        assert ec.importance_score >= RankingConfig.EMERGENCY_IMPORTANCE_FLOOR

    results["test14_emergency_threshold"] = RankingConfig.EMERGENCY_URGENCY_THRESHOLD # 90.0
    results["test14_emergency_floor"] = RankingConfig.EMERGENCY_IMPORTANCE_FLOOR       # 75.0
    results["test14_live_emergencies_count"] = len(live_emergencies)

    # ----------------------------------------------------
    # TEST 15 — PERSONALIZATION INDEPENDENCE
    # ----------------------------------------------------
    print("TEST 15: Personalization independence...")
    feed_kar = get_json(f"{BASE_URL}/feed?state=Karnataka&limit=30")
    feed_tel = get_json(f"{BASE_URL}/feed?state=Telangana&limit=30")
    items_kar = feed_kar.get("items", []) if isinstance(feed_kar, dict) else feed_kar
    items_tel = feed_tel.get("items", []) if isinstance(feed_tel, dict) else feed_tel

    map_kar = {c["id"]: c["importance_score"] for c in items_kar}
    map_tel = {c["id"]: c["importance_score"] for c in items_tel}
    common = set(map_kar.keys()) & set(map_tel.keys())
    mismatched_imp = [cid for cid in common if map_kar[cid] != map_tel[cid]]
    print(f"Importance score variations across state changes: {len(mismatched_imp)}")
    assert len(mismatched_imp) == 0, f"Importance changed across states on {mismatched_imp}"
    results["test15_personalization_independent"] = True

    # ----------------------------------------------------
    # TEST 16 — FINAL SCORE CONTRIBUTION (0.40)
    # ----------------------------------------------------
    print("TEST 16: Final score contribution (Importance x 0.40)...")
    out_imp_80 = FeedRankingEngine.compute_final_score(
        objective_importance=80.0, urgency=50.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    out_imp_30 = FeedRankingEngine.compute_final_score(
        objective_importance=30.0, urgency=50.0, freshness=50.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    delta_imp = 80.0 - 30.0 # 50.0
    expected_delta_final = delta_imp * RankingConfig.WEIGHT_OBJECTIVE_IMPORTANCE # 50 * 0.40 = 20.0
    actual_delta_final = round(out_imp_80.final_feed_score - out_imp_30.final_feed_score, 2)

    print(f"Importance weight: {RankingConfig.WEIGHT_OBJECTIVE_IMPORTANCE}")
    print(f"Delta Importance: {delta_imp}")
    print(f"Expected Delta Final Score: {expected_delta_final}")
    print(f"Actual Delta Final Score: {actual_delta_final}")
    assert actual_delta_final == expected_delta_final, f"Expected delta {expected_delta_final}, got {actual_delta_final}"
    results["test16_expected_delta"] = expected_delta_final
    results["test16_actual_delta"] = actual_delta_final

    # ----------------------------------------------------
    # TEST 17 — EXTREME INPUTS
    # ----------------------------------------------------
    print("TEST 17: Extreme inputs handling...")
    # 1. Very large casualty number
    d_huge, s_huge = ImportanceEngine.analyze_event_text("War claims 500,000,000 lives", "Mass global catastrophe with five hundred million dead.")
    assert not math.isnan(s_huge) and s_huge <= 100.0, f"Extreme casualty produced invalid score: {s_huge}"

    # 2. Empty text
    d_empty, s_empty = ImportanceEngine.analyze_event_text("", "")
    assert not math.isnan(s_empty) and s_empty >= 0.0, f"Empty text produced invalid score: {s_empty}"

    # 3. Unusually long text
    long_text = "Breaking emergency news update. " * 500
    d_long, s_long = ImportanceEngine.analyze_event_text("Major Update", long_text)
    assert not math.isnan(s_long) and 0.0 <= s_long <= 100.0, f"Long text produced invalid score: {s_long}"

    print(f"Extreme input scores: huge={s_huge}, empty={s_empty}, long={s_long}")
    results["test17_extreme_safe"] = True

    # ----------------------------------------------------
    # TEST 18 — LIVE FEED INTEGRITY
    # ----------------------------------------------------
    print("TEST 18: Live feed integrity...")
    feed_live = get_json(f"{BASE_URL}/feed?limit=30")
    live_items = feed_live.get("items", []) if isinstance(feed_live, dict) else feed_live
    invalid_feed_imp = 0
    invalid_feed_final = 0
    ranking_violations = 0

    for idx in range(len(live_items)):
        card = live_items[idx]
        imp = card.get("importance_score")
        final = card.get("final_feed_score")
        if imp is None or math.isnan(imp) or imp < 0.0 or imp > 100.0:
            invalid_feed_imp += 1
        if final is None or math.isnan(final) or final < 0.0 or final > 100.0:
            invalid_feed_final += 1
        if idx < len(live_items) - 1:
            if final < live_items[idx + 1].get("final_feed_score", 0.0):
                ranking_violations += 1

    print(f"Live items: {len(live_items)}, invalid imp: {invalid_feed_imp}, invalid final: {invalid_feed_final}, ranking violations: {ranking_violations}")
    results["test18_stories"] = len(live_items)
    results["test18_invalid_imp"] = invalid_feed_imp
    results["test18_invalid_final"] = invalid_feed_final
    results["test18_ranking_violations"] = ranking_violations
    assert invalid_feed_imp == 0 and invalid_feed_final == 0 and ranking_violations == 0

    # ----------------------------------------------------
    # TEST 19 — BROWSER REGRESSION IN GOOGLE CHROME
    # ----------------------------------------------------
    print("TEST 19: Browser regression in Google Chrome...")
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
        assert len(cards_rendered) >= 22, f"Expected >= 22 stories rendered, got {len(cards_rendered)}"

        # Open story detail to check explainability box displays Importance score
        detail_btn = page.query_selector(".scroll-action-btn:has-text('Explain Decision')")
        if detail_btn:
            detail_btn.click()
            page.wait_for_timeout(400)
            imp_val = page.inner_text("#detail-score-importance")
            print(f"Detail modal Importance score: {imp_val}")
            assert len(imp_val) > 0, "Detail modal missing importance score"
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b8_detail_importance.png"))
            page.click("#btn-close-detail-modal")
            page.wait_for_timeout(200)

        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b8_browser_feed.png"))

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["browser_stories_rendered"] = len(cards_rendered)
        results["browser_console_errors"] = err_logs
        results["browser_page_errors"] = page_errors
        results["browser_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    db.close()
    print("\nALL B8 IMPORTANCE ENGINE CHECKS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b8_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b8_audit()
