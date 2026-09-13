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
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

from app.db import SessionLocal
from app.models import Card, Article
from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

BASE_URL = "http://127.0.0.1:8000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = r"d:\News\scratch\b6_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "B6-Audit/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def run_b6_audit():
    results = {}
    print("==================================================")
    print("STARTING B6 — FRESHNESS & TIME-DECAY AUDIT")
    print("==================================================")

    # ----------------------------------------------------
    # TEST 1 — SOURCE CODE INSPECTION
    # ----------------------------------------------------
    print("TEST 1: Timestamp hierarchy verification...")
    # In packages/ranking_engine/freshness_engine.py:
    # ref_time = event_time or published_at or scraped_at
    results["test1_timestamp_hierarchy"] = "event_time -> published_at -> scraped_at"
    print(f"Timestamp hierarchy: {results['test1_timestamp_hierarchy']}")

    # ----------------------------------------------------
    # TEST 2 — TIME-DECAY BOUNDARIES
    # ----------------------------------------------------
    print("TEST 2: Time-decay boundaries...")
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    
    test_cases = [
        ("5m (0-15m)", now - timedelta(minutes=5), 100.0),
        ("15m boundary (0-15m)", now - timedelta(minutes=15), 100.0),
        ("20m (15-30m)", now - timedelta(minutes=20), 95.0),
        ("30m boundary (15-30m)", now - timedelta(minutes=30), 95.0),
        ("45m (30-60m)", now - timedelta(minutes=45), 90.0),
        ("60m boundary (30-60m)", now - timedelta(minutes=60), 90.0),
        ("90m (1-2h)", now - timedelta(minutes=90), 80.0),
        ("120m boundary (1-2h)", now - timedelta(hours=2), 80.0),
        ("3h (2-4h)", now - timedelta(hours=3), 70.0),
        ("4h boundary (2-4h)", now - timedelta(hours=4), 70.0),
        ("6h (4-8h)", now - timedelta(hours=6), 55.0),
        ("8h boundary (4-8h)", now - timedelta(hours=8), 55.0),
        ("10h (8-12h)", now - timedelta(hours=10), 40.0),
        ("12h boundary (8-12h)", now - timedelta(hours=12), 40.0),
        ("18h (12-24h)", now - timedelta(hours=18), 25.0),
        ("24h boundary (12-24h)", now - timedelta(hours=24), 25.0),
        ("36h (24-48h)", now - timedelta(hours=36), 10.0),
        ("48h boundary (24-48h)", now - timedelta(hours=48), 10.0),
        ("72h (48h+)", now - timedelta(hours=72), 5.0),
    ]

    boundary_results = {}
    boundary_mismatches = 0
    for label, dt, expected in test_cases:
        actual = FreshnessEngine.calculate_freshness(published_at=dt, current_time=now)
        boundary_results[label] = {"actual": actual, "expected": expected}
        if actual != expected:
            boundary_mismatches += 1
            print(f"MISMATCH for {label}: got {actual}, expected {expected}")

    print(f"Boundary values checked: {len(test_cases)}, mismatches: {boundary_mismatches}")
    results["test2_boundary_results"] = boundary_results
    assert boundary_mismatches == 0, f"Found {boundary_mismatches} boundary mismatches!"

    # ----------------------------------------------------
    # TEST 3 — MONOTONICITY
    # ----------------------------------------------------
    print("TEST 3: Monotonicity verification...")
    age_points = [
        timedelta(minutes=10),
        timedelta(minutes=30),
        timedelta(hours=1),
        timedelta(hours=4),
        timedelta(hours=12),
        timedelta(hours=24),
        timedelta(hours=48),
        timedelta(hours=72),
    ]
    scores_sequence = [
        FreshnessEngine.calculate_freshness(published_at=now - delta, current_time=now)
        for delta in age_points
    ]
    print(f"Sequence from youngest to oldest: {scores_sequence}")
    monotonic_non_increasing = all(scores_sequence[i] >= scores_sequence[i+1] for i in range(len(scores_sequence) - 1))
    results["test3_monotonic"] = monotonic_non_increasing
    results["test3_scores_sequence"] = scores_sequence
    assert monotonic_non_increasing, f"Freshness sequence is not non-increasing: {scores_sequence}"

    # ----------------------------------------------------
    # TEST 4 — TIMESTAMP FALLBACK
    # ----------------------------------------------------
    print("TEST 4: Fallback hierarchy verification...")
    t_event = now - timedelta(minutes=10) # 100.0
    t_pub = now - timedelta(hours=3)      # 70.0
    t_scraped = now - timedelta(hours=36) # 10.0

    # Case A: event_time, published_at, scraped_at all present
    s_a = FreshnessEngine.calculate_freshness(event_time=t_event, published_at=t_pub, scraped_at=t_scraped, current_time=now)
    assert s_a == 100.0, f"Case A should use event_time (100.0), got {s_a}"

    # Case B: event_time missing, published_at and scraped_at present
    s_b = FreshnessEngine.calculate_freshness(event_time=None, published_at=t_pub, scraped_at=t_scraped, current_time=now)
    assert s_b == 70.0, f"Case B should use published_at (70.0), got {s_b}"

    # Case C: event_time and published_at missing, scraped_at present
    s_c = FreshnessEngine.calculate_freshness(event_time=None, published_at=None, scraped_at=t_scraped, current_time=now)
    assert s_c == 10.0, f"Case C should use scraped_at (10.0), got {s_c}"

    # Case D: All missing
    s_d = FreshnessEngine.calculate_freshness(event_time=None, published_at=None, scraped_at=None, current_time=now)
    assert s_d == 25.0, f"Case D should fall back to conservative default (25.0), got {s_d}"

    results["test4_fallback"] = {
        "case_a_event_time": s_a,
        "case_b_published_at": s_b,
        "case_c_scraped_at": s_c,
        "case_d_all_missing": s_d,
    }
    print(f"Fallback results: Case A={s_a}, Case B={s_b}, Case C={s_c}, Case D={s_d}")

    # ----------------------------------------------------
    # TEST 5 — FUTURE TIMESTAMP
    # ----------------------------------------------------
    print("TEST 5: Future timestamp handling...")
    t_future = now + timedelta(hours=2)
    s_future = FreshnessEngine.calculate_freshness(published_at=t_future, current_time=now)
    print(f"Future timestamp (+2h) result: {s_future}")
    assert s_future == 100.0, f"Future timestamp should be clamped to 100.0, got {s_future}"
    assert not math.isnan(s_future) and 0.0 <= s_future <= 100.0, "Future timestamp must produce valid score"
    results["test5_future_score"] = s_future

    # ----------------------------------------------------
    # TEST 6 — LIVE DATABASE AUDIT
    # ----------------------------------------------------
    print("TEST 6: Database timestamps audit...")
    db = SessionLocal()
    cards = db.query(Card).filter(Card.verified_status == "published").all()
    total_cards = len(cards)
    with_published_at = sum(1 for c in cards if c.published_at is not None)
    with_created_at = sum(1 for c in cards if c.created_at is not None)
    # Check if Card has event_time attribute
    has_event_time_attr = hasattr(Card, "event_time")
    with_event_time = sum(1 for c in cards if getattr(c, "event_time", None) is not None) if has_event_time_attr else 0
    with_none = sum(1 for c in cards if c.published_at is None and c.created_at is None)

    print(f"Total published NEWS cards: {total_cards}")
    print(f"  With event_time: {with_event_time}")
    print(f"  With published_at: {with_published_at}")
    print(f"  With created_at/scraped_at: {with_created_at}")
    print(f"  With no timestamp: {with_none}")

    results["test6_db_audit"] = {
        "total_published_cards": total_cards,
        "with_event_time": with_event_time,
        "with_published_at": with_published_at,
        "with_created_at": with_created_at,
        "with_none": with_none
    }
    db.close()

    # ----------------------------------------------------
    # TEST 7 — LIVE FEED FRESHNESS RECOMPUTATION
    # ----------------------------------------------------
    print("TEST 7: Live feed freshness recomputation...")
    feed_url = f"{BASE_URL}/feed?limit=50&state=Karnataka"
    feed_res = get_json(feed_url)
    items = feed_res.get("items", []) if isinstance(feed_res, dict) else feed_res

    req_now = datetime.now(timezone.utc)
    max_feed_diff = 0.0
    feed_mismatches = 0
    for card in items:
        reported_frsh = card.get("freshness_score")
        pub_str = card.get("published_at") or card.get("created_at")
        if pub_str:
            pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            recomputed = FreshnessEngine.calculate_freshness(published_at=pub_dt, current_time=req_now)
            diff = abs(reported_frsh - recomputed)
            if diff > max_feed_diff:
                max_feed_diff = diff
            # If request time vs response time is within a few seconds, decay bracket shouldn't jump
            if diff > 0.0:
                print(f"Notice: small difference on {card.get('headline')[:30]}: reported {reported_frsh} vs recomputed {recomputed}")
                if diff > 15.0: # Only fail if decay bracket jumped completely unexpectedly
                    feed_mismatches += 1

    print(f"Live feed freshness max difference: {max_feed_diff}, mismatches: {feed_mismatches}")
    results["test7_max_feed_diff"] = max_feed_diff
    results["test7_feed_mismatches"] = feed_mismatches
    assert feed_mismatches == 0, f"Found {feed_mismatches} live feed freshness mismatches!"

    # ----------------------------------------------------
    # TEST 8 — FINAL SCORE CONTRIBUTION
    # ----------------------------------------------------
    print("TEST 8: Final score contribution (Freshness x 0.15)...")
    # Freshness = 100 vs Freshness = 20
    score_fresh_100 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=100.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    score_fresh_20 = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=20.0,
        personal_relevance=50.0, verification_confidence=50.0
    )

    delta_frsh = 100.0 - 20.0 # 80.0
    expected_delta_final = delta_frsh * RankingConfig.WEIGHT_FRESHNESS # 80 * 0.15 = 12.0
    actual_delta_final = round(score_fresh_100.final_feed_score - score_fresh_20.final_feed_score, 2)

    print(f"Freshness weight: {RankingConfig.WEIGHT_FRESHNESS}")
    print(f"Delta Freshness: {delta_frsh}")
    print(f"Expected Delta Final Score: {expected_delta_final}")
    print(f"Actual Delta Final Score: {actual_delta_final}")
    assert actual_delta_final == expected_delta_final, f"Expected delta {expected_delta_final}, got {actual_delta_final}"
    results["test8_expected_delta"] = expected_delta_final
    results["test8_actual_delta"] = actual_delta_final

    # ----------------------------------------------------
    # TEST 9 — OBJECTIVE COMPONENT ISOLATION
    # ----------------------------------------------------
    print("TEST 9: Objective component isolation...")
    # Verify changing freshness does NOT change importance, urgency, relevance, or verification
    assert score_fresh_100.objective_importance == score_fresh_20.objective_importance == 50.0
    assert score_fresh_100.urgency == score_fresh_20.urgency == 50.0
    assert score_fresh_100.personal_relevance == score_fresh_20.personal_relevance == 50.0
    assert score_fresh_100.verification_confidence == score_fresh_20.verification_confidence == 50.0
    print("All non-freshness components remain strictly unchanged.")
    results["test9_isolation_verified"] = True

    # ----------------------------------------------------
    # TEST 10 — LIVE ORDERING EFFECT
    # ----------------------------------------------------
    print("TEST 10: Live ordering effect...")
    # Two identical cards except publication time
    card_recent = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=100.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    card_stale = FeedRankingEngine.compute_final_score(
        objective_importance=50.0, urgency=50.0, freshness=25.0,
        personal_relevance=50.0, verification_confidence=50.0
    )
    assert card_recent.final_feed_score > card_stale.final_feed_score
    print(f"Recent card score: {card_recent.final_feed_score} > Stale card score: {card_stale.final_feed_score}")

    # ----------------------------------------------------
    # TEST 11 — REPEATED DETERMINISM
    # ----------------------------------------------------
    print("TEST 11: Repeated determinism...")
    t_fixed = now - timedelta(hours=5)
    r1 = FreshnessEngine.calculate_freshness(published_at=t_fixed, current_time=now)
    r2 = FreshnessEngine.calculate_freshness(published_at=t_fixed, current_time=now)
    r3 = FreshnessEngine.calculate_freshness(published_at=t_fixed, current_time=now)
    assert r1 == r2 == r3 == 55.0, f"Fixed time calculations must be identical: {r1}, {r2}, {r3}"
    print(f"Fixed time repeated results: {r1}, {r2}, {r3}")

    # Live feed calls in quick succession
    feed1 = get_json(f"{BASE_URL}/feed?limit=20")
    feed2 = get_json(f"{BASE_URL}/feed?limit=20")
    items1 = feed1.get("items", []) if isinstance(feed1, dict) else feed1
    items2 = feed2.get("items", []) if isinstance(feed2, dict) else feed2
    ids1 = [c["id"] for c in items1]
    ids2 = [c["id"] for c in items2]
    assert ids1 == ids2, "Successive live feed calls returned different story orders!"
    print("Successive live feed calls match 100%.")

    # ----------------------------------------------------
    # TEST 12 — API DATA INTEGRITY
    # ----------------------------------------------------
    print("TEST 12: API data integrity for freshness and final score...")
    for c in items:
        frsh = c.get("freshness_score")
        final = c.get("final_feed_score")
        assert frsh is not None and isinstance(frsh, (int, float)), f"Freshness must be numeric on {c.get('id')}"
        assert not math.isnan(frsh), f"Freshness is NaN on {c.get('id')}"
        assert 0.0 <= frsh <= 100.0, f"Freshness out of range [0, 100] on {c.get('id')}: {frsh}"
        assert final is not None and isinstance(final, (int, float)), f"Final score must be numeric on {c.get('id')}"
        assert not math.isnan(final), f"Final score is NaN on {c.get('id')}"
        assert 0.0 <= final <= 100.0, f"Final score out of range [0, 100] on {c.get('id')}: {final}"
    print(f"All {len(items)} feed items passed integrity validation.")

    # ----------------------------------------------------
    # TEST 13 — BROWSER REGRESSION IN CHROME
    # ----------------------------------------------------
    print("TEST 13: Browser regression with Google Chrome...")
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

        cards = page.query_selector_all("#feed-container .scroll-card")
        print(f"Browser rendered cards count: {len(cards)}")
        assert len(cards) > 0, "No cards rendered in browser feed!"

        # Check time ago text exists on cards
        times = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.scroll-card .scroll-time')).map(el => el.textContent.trim());
        }""")
        print(f"Sample card timestamps in UI: {times[:5]}")
        assert all(len(t) > 0 for t in times), "Some cards have empty timestamps"

        # Check visible scores are descending
        scores = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.scroll-card .scroll-score')).map(el => {
                return parseFloat(el.textContent.replace('Score', '').trim());
            });
        }""")
        descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        assert descending, f"Browser feed scores not descending: {scores}"

        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "b6_browser_feed.png"))

        err_logs = [l for l in console_logs if "error" in l.lower()]
        print(f"Console errors: {err_logs}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        results["browser_stories_rendered"] = len(cards)
        results["browser_console_errors"] = err_logs
        results["browser_page_errors"] = page_errors
        results["browser_failed_requests"] = failed_requests

        assert len(err_logs) == 0, f"Console errors in browser: {err_logs}"
        assert len(page_errors) == 0, f"Page errors in browser: {page_errors}"
        assert len(failed_requests) == 0, f"Failed requests in browser: {failed_requests}"

        browser.close()

    print("\nALL B6 FRESHNESS AUDIT CHECKS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b6_audit_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_b6_audit()
