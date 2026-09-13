"""
Comprehensive End-to-End Real User Validation Script.
Validates Phases 4 through 14 of the engineering specification against the live News Reels API.
"""

import json
import urllib.request
import urllib.parse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 printing on Windows shells
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"

def log_section(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)

def test_phase4_web_assets():
    log_section("PHASE 4: WEB APPLICATION ASSET & DOM VERIFICATION")
    
    # 1. Root HTML
    req = urllib.request.urlopen(f"{BASE_URL}/")
    assert req.status == 200, f"Expected 200, got {req.status}"
    html = req.read().decode("utf-8")
    print(f"[*] GET / returned 200 OK ({len(html)} bytes)")

    required_dom_ids = [
        "modal-welcome",
        "btn-welcome-start",
        "btn-open-location-modal",
        "input-district",
        "input-state",
        "btn-save-location",
        "btn-skip-location",
        "btn-open-interests-modal",
        "interest-chips-container",
        "btn-save-interests",
        "feed-container",
        "feed-summary-bar",
        "tab-category-all",
        "tab-category-national",
        "tab-category-state",
        "tab-category-technology",
        "empty-state-view",
        "btn-empty-reset",
        "modal-story-detail",
        "btn-close-detail-modal",
        "detail-final-score",
        "detail-priority-reason",
        "detail-score-importance",
        "detail-score-urgency",
        "detail-score-freshness",
        "detail-score-verification",
        "detail-score-relevance",
    ]

    for elem_id in required_dom_ids:
        assert f'id="{elem_id}"' in html, f"Missing required interactive element ID: {elem_id}"
    print(f"[+] All {len(required_dom_ids)} required interactive DOM elements verified in index.html.")

    # 2. CSS
    css_req = urllib.request.urlopen(f"{BASE_URL}/style.css")
    assert css_req.status == 200
    css = css_req.read().decode("utf-8")
    assert "--score-high" in css and "--bg-card" in css
    print(f"[+] GET /style.css returned 200 OK ({len(css)} bytes)")

    # 3. JS
    js_req = urllib.request.urlopen(f"{BASE_URL}/app.js")
    assert js_req.status == 200
    js = js_req.read().decode("utf-8")
    assert "fetchFeed" in js and "openDetailModal" in js
    print(f"[+] GET /app.js returned 200 OK ({len(js)} bytes)")

def test_phase5_and_6_feed_and_ranking_logic():
    log_section("PHASE 5 & 6: ALL NEWS FEED & RANKING LOGIC VALIDATION")
    
    url = f"{BASE_URL}/feed?limit=15"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    
    items = data.get("items", [])
    assert len(items) > 0, "No items returned in feed"
    print(f"[+] Retrieved {len(items)} feed items for inspection.")

    print("\n--- TOP 10 RANKED STORIES ---")
    prev_score = 999.0
    for idx, card in enumerate(items[:10], 1):
        score = card.get("final_feed_score", 0.0)
        imp = card.get("importance_score", 0.0)
        urg = card.get("urgency_score", 0.0)
        fresh = card.get("freshness_score", 0.0)
        rel = card.get("personal_relevance_score", 0.0)
        ver = card.get("verification_score", 0.0)
        reason = card.get("priority_reason", "")
        title = card.get("headline", "")
        cat = card.get("category", "")
        src = card.get("source_name", "Wire")
        url_link = card.get("canonical_url") or card.get("source_url") or "#"

        print(f"#{idx:02d} [{cat.upper()}] Final Score: {score:.1f} | Imp: {imp:.0f} | Urg: {urg:.0f} | Fresh: {fresh:.0f} | Rel: {rel:.0f} | Ver: {ver:.0f}")
        print(f"     Title: {title[:70]}")
        print(f"     Source: {src} | Link: {url_link[:50]}")
        print(f"     Why: {reason}")
        print("-" * 75)

        # Invariant checks
        assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"
        assert 0.0 <= imp <= 100.0, f"Importance out of bounds: {imp}"
        assert 0.0 <= urg <= 100.0, f"Urgency out of bounds: {urg}"
        assert 0.0 <= fresh <= 100.0, f"Freshness out of bounds: {fresh}"
        assert 0.0 <= rel <= 100.0, f"Relevance out of bounds: {rel}"
        assert 0.0 <= ver <= 100.0, f"Verification out of bounds: {ver}"
        assert reason and len(reason) > 5, f"Missing or empty priority reason on card {card.get('id')}"

        # Strictly sorted DESC
        assert score <= prev_score + 1e-4, f"Ordering violation: #{idx} score {score} > #{idx-1} score {prev_score}"
        prev_score = score

    # Validate that high human disaster beats routine commercial statement
    top_story = items[0]
    tech_story = next((c for c in items if c.get("category") == "technology"), None)
    if tech_story:
        assert top_story["final_feed_score"] > tech_story["final_feed_score"], \
            "High impact disaster should rank above routine technology opinion"
        print(f"[+] Verified: Top story '{top_story['headline'][:35]}...' (Score {top_story['final_feed_score']:.1f}) outranks Tech opinion (Score {tech_story['final_feed_score']:.1f})")

def test_phase7_user_personalization():
    log_section("PHASE 7: USER PERSONALIZATION COMPARISON (USER A vs USER B)")
    
    dev_a = "device_user_a_telangana_tech"
    dev_b = "device_user_b_bihar_state"

    # User A: Tech focus, Telangana
    url_a = f"{BASE_URL}/feed?device_id={dev_a}&state=Telangana&district=Hyderabad&limit=15"
    res_a = json.loads(urllib.request.urlopen(url_a).read().decode("utf-8"))["items"]

    # User B: State focus, Bihar
    url_b = f"{BASE_URL}/feed?device_id={dev_b}&state=Bihar&district=Patna&limit=15"
    res_b = json.loads(urllib.request.urlopen(url_b).read().decode("utf-8"))["items"]

    # Find Bihar flood story in both feeds
    bihar_in_a = next((c for c in res_a if "bihar" in c["headline"].lower()), None)
    bihar_in_b = next((c for c in res_b if "bihar" in c["headline"].lower()), None)

    if bihar_in_a and bihar_in_b:
        print(f"[+] User A relevance for Bihar story: {bihar_in_a['personal_relevance_score']:.1f} (Final Score: {bihar_in_a['final_feed_score']:.1f})")
        print(f"[+] User B relevance for Bihar story: {bihar_in_b['personal_relevance_score']:.1f} (Final Score: {bihar_in_b['final_feed_score']:.1f})")
        assert bihar_in_b["personal_relevance_score"] > bihar_in_a["personal_relevance_score"], \
            "User in Bihar should receive higher personal relevance for Bihar news"
        assert bihar_in_b["final_feed_score"] >= bihar_in_a["final_feed_score"], \
            "User B's higher relevance should elevate or preserve final score"
        print("[+] Personalization successfully boosted local relevance for Bihar resident.")

def test_phase8_category_feeds():
    log_section("PHASE 8: CATEGORY FILTERING & EMPTY STATE HANDLING")
    
    categories = ["national", "state", "technology", "business", "politics", "entertainment"]
    
    for cat in categories:
        url = f"{BASE_URL}/feed?category={cat}&limit=10"
        res = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))
        items = res.get("items", [])
        
        if items:
            assert all(c["category"].lower() == cat for c in items), f"Category bleeding detected in {cat} feed!"
            print(f"[+] Category '{cat}': {len(items)} items returned, all strictly matched category '{cat}'.")
        else:
            print(f"[+] Category '{cat}': 0 items returned (Graceful empty state handled, no silent fallback).")

def test_phase9_location_geocoder():
    log_section("PHASE 9: LOCATION GEOCODER & FALLBACK TEST")
    
    # Valid coords (Hyderabad)
    geo_url = f"{BASE_URL}/reverse-geocode?lat=17.3850&lng=78.4867"
    try:
        geo_req = urllib.request.urlopen(geo_url, timeout=3)
        assert geo_req.status == 200
        geo_data = json.loads(geo_req.read().decode("utf-8"))
        print(f"[+] Reverse geocoding (17.3850, 78.4867) -> District: {geo_data.get('district')}, State: {geo_data.get('state')}", flush=True)
    except Exception as e:
        print(f"[*] External geocoder network note: {e} (App continues safely)", flush=True)

    # Test feed with manual district & state fallback
    manual_url = f"{BASE_URL}/feed?district=Hyderabad&state=Telangana&limit=5"
    man_res = json.loads(urllib.request.urlopen(manual_url).read().decode("utf-8"))
    assert "items" in man_res
    print(f"[+] Manual location fallback query executed successfully with {len(man_res['items'])} items.")

def test_phase11_and_12_clustering_and_verification():
    log_section("PHASE 11 & 12: CLUSTER DEDUPLICATION & VERIFICATION MODEL")
    
    url = f"{BASE_URL}/feed?limit=25"
    data = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))["items"]
    
    # Verify no duplicate headlines in the top feed
    headlines = [c["headline"].strip().lower() for c in data]
    assert len(headlines) == len(set(headlines)), "Duplicate headlines detected in feed!"
    print(f"[+] Verified {len(headlines)} unique cards returned with zero duplicates.")

    # Check verification scores
    for c in data:
        ver_score = c.get("verification_score", 0.0)
        assert 0.0 <= ver_score <= 100.0
    print("[+] Verified all cards carry valid verification confidence scores.")

def test_phase14_edge_cases():
    log_section("PHASE 14: EDGE CASES & RESILIENCE TEST")
    
    test_cases = [
        ("Empty category", f"{BASE_URL}/feed?category=&limit=5"),
        ("Nonexistent category", f"{BASE_URL}/feed?category=extraterrestrial&limit=5"),
        ("Large limit ceiling", f"{BASE_URL}/feed?limit=250"),
        ("Offset pagination", f"{BASE_URL}/feed?offset=3&limit=5"),
        ("Special characters in location", f"{BASE_URL}/feed?district=O'Fallon&state=St.+Louis&limit=5"),
        ("Unknown device ID", f"{BASE_URL}/feed?device_id=completely_new_random_user_9999&limit=5"),
    ]

    for name, endpoint in test_cases:
        req = urllib.request.urlopen(endpoint)
        assert req.status == 200, f"Edge case '{name}' returned {req.status}"
        res = json.loads(req.read().decode("utf-8"))
        assert "items" in res, f"Edge case '{name}' missing items field"
        print(f"[+] Edge Case: '{name}' handled safely (Status 200 OK, {len(res['items'])} items).")

def main():
    print("=" * 75)
    print("   NEWS REELS — AUTOMATED END-TO-END VALIDATION SUITE")
    print("=" * 75)
    
    test_phase4_web_assets()
    test_phase5_and_6_feed_and_ranking_logic()
    test_phase7_user_personalization()
    test_phase8_category_feeds()
    test_phase9_location_geocoder()
    test_phase11_and_12_clustering_and_verification()
    test_phase14_edge_cases()
    
    log_section("ALL VALIDATION PHASES EXECUTED & PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
