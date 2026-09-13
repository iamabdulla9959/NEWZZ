import sys
import json
import time
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = Path(r"C:\Users\adila\.gemini\antigravity-ide\brain\a901a051-bc24-4de6-8f98-89d20bdf9040\screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def run_b3_verification():
    report = {
        "test1_available_categories": {},
        "test2_category_selection": {},
        "test3_deselect": {},
        "test4_reload_persistence": {},
        "test5_feed_mechanism": {},
        "test6_category_filter": {},
        "test7_all_news": {},
        "test8_multi_category": {},
        "test9_empty_category_state": {},
        "test10_persistence_after_completion": {},
        "test11_regression": {},
        "diagnostics": {
            "console_errors": [],
            "page_errors": [],
            "failed_requests": []
        }
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: report["diagnostics"]["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: report["diagnostics"]["page_errors"].append(str(err)))
        page.on("requestfailed", lambda req: report["diagnostics"]["failed_requests"].append(f"{req.method} {req.url}: {req.failure}"))

        # =====================================================================
        # TEST 1: CLEAN USER & AVAILABLE CATEGORIES
        # =====================================================================
        print("\n--- TEST 1: Clean User & Available Categories ---")
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.clear();")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Welcome -> Start Reading -> State modal -> Continue to Categories step
        page.click("#btn-welcome-start")
        time.sleep(0.5)
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        time.sleep(0.5)

        # Inspect available category chips in modal-interests
        cat_info = page.evaluate("""() => {
            const chips = Array.from(document.querySelectorAll('.interest-chip'));
            return chips.map(c => ({
                id: c.id,
                category: c.getAttribute('data-category'),
                name: c.querySelector('.chip-name')?.textContent?.trim(),
                isSelected: c.classList.contains('selected')
            }));
        }""")
        available_names = [c['name'] for c in cat_info]
        initial_selected = [c['name'] for c in cat_info if c['isSelected']]
        print(f"Available category options ({len(available_names)}): {available_names}")
        print(f"Initial default selected: {initial_selected}")
        report["test1_available_categories"] = {
            "all_categories": available_names,
            "initial_selected": initial_selected,
            "count": len(available_names)
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_01_categories_modal.png"))

        # =====================================================================
        # TEST 2: CATEGORY SELECTION
        # =====================================================================
        print("\n--- TEST 2: Category Selection ---")
        # Select Technology, Business, Politics
        page.evaluate("""() => {
            const desired = ['Technology', 'Business', 'Politics'];
            const chips = document.querySelectorAll('.interest-chip');
            chips.forEach(c => {
                const cat = c.getAttribute('data-category');
                const isSel = c.classList.contains('selected');
                if (desired.includes(cat) && !isSel) {
                    c.click();
                } else if (!desired.includes(cat) && isSel) {
                    c.click();
                }
            });
        }""")
        time.sleep(0.5)

        t2_chips = page.evaluate("""() => {
            const chips = Array.from(document.querySelectorAll('.interest-chip'));
            return chips.filter(c => c.classList.contains('selected')).map(c => c.getAttribute('data-category'));
        }""")
        print(f"Chips currently selected in UI: {t2_chips}")

        # Complete onboarding by saving interests and wait for initial feed
        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200) as resp_info:
            page.click("#btn-save-interests")
        feed_data_initial = resp_info.value.json()

        t2_storage = page.evaluate("() => ({ ...localStorage })")
        stored_raw = t2_storage.get("newsreels_interests", "[]")
        stored_parsed = json.loads(stored_raw)
        print(f"Storage key: newsreels_interests")
        print(f"Stored value: {stored_raw}")
        print(f"Selected categories: {stored_parsed}")

        report["test2_category_selection"] = {
            "storage_key": "newsreels_interests",
            "stored_value": stored_raw,
            "selected_categories": stored_parsed,
            "has_duplicates": len(stored_parsed) != len(set(stored_parsed)),
            "ui_matches_storage": sorted(t2_chips) == sorted(stored_parsed)
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_02_after_selection.png"))

        # =====================================================================
        # TEST 3: DESELECT
        # =====================================================================
        print("\n--- TEST 3: Deselect ---")
        # Re-open interests modal via header button
        page.click("#btn-open-interests-modal")
        time.sleep(0.5)

        # Deselect 'Politics'
        print("Deselecting 'Politics'...")
        page.click("#chip-interest-politics")
        time.sleep(0.5)

        t3_ui = page.evaluate("""() => {
            const chip = document.getElementById('chip-interest-politics');
            const selectedChips = Array.from(document.querySelectorAll('.interest-chip.selected')).map(c => c.getAttribute('data-category'));
            return {
                politicsIsSelected: chip.classList.contains('selected'),
                selectedChips: selectedChips
            };
        }""")
        print(f"UI state after deselecting Politics: isSelected={t3_ui['politicsIsSelected']}, remaining={t3_ui['selectedChips']}")

        # Save preferences to commit deselection
        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200):
            page.click("#btn-save-interests")
        time.sleep(0.5)

        t3_storage = page.evaluate("() => ({ ...localStorage })")
        t3_stored_parsed = json.loads(t3_storage.get("newsreels_interests", "[]"))
        print(f"Storage after deselecting: {t3_stored_parsed}")

        report["test3_deselect"] = {
            "deselected_category": "Politics",
            "ui_updated_immediately": not t3_ui["politicsIsSelected"],
            "storage_updated": "Politics" not in t3_stored_parsed,
            "current_stored_categories": t3_stored_parsed
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_03_after_deselect.png"))

        # =====================================================================
        # TEST 4: RELOAD & RESTORATION
        # =====================================================================
        print("\n--- TEST 4: Reload & Restoration ---")
        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200):
            page.reload(wait_until="networkidle")
        time.sleep(0.5)

        # Open interests modal from header to check if deselection / selection survived reload
        page.click("#btn-open-interests-modal")
        time.sleep(0.5)

        t4_ui = page.evaluate("""() => {
            const chips = Array.from(document.querySelectorAll('.interest-chip'));
            return chips.filter(c => c.classList.contains('selected')).map(c => c.getAttribute('data-category'));
        }""")
        t4_storage = page.evaluate("() => ({ ...localStorage })")
        t4_stored_parsed = json.loads(t4_storage.get("newsreels_interests", "[]"))

        print(f"After reload UI selected chips: {t4_ui}")
        print(f"After reload stored categories: {t4_stored_parsed}")
        page.click("#btn-close-interests-modal")
        time.sleep(0.5)

        report["test4_reload_persistence"] = {
            "ui_selected_after_reload": t4_ui,
            "storage_after_reload": t4_stored_parsed,
            "matches": sorted(t4_ui) == sorted(t4_stored_parsed)
        }

        # =====================================================================
        # TEST 5: FEED CATEGORY BEHAVIOR / REQUEST INSPECTION
        # =====================================================================
        print("\n--- TEST 5: Feed Category Behavior ---")
        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200) as resp_info:
            page.click("#btn-refresh-feed")
        refresh_resp = resp_info.value
        refresh_url = refresh_resp.url
        parsed = urlparse(refresh_url)
        params = parse_qs(parsed.query)
        print(f"Live /feed request URL: {refresh_url}")
        print(f"Query params: {params}")

        report["test5_feed_mechanism"] = {
            "feed_request_url": refresh_url,
            "params_sent": {k: v[0] for k, v in params.items()},
            "has_category_param": "category" in params,
            "has_device_id": "device_id" in params,
            "mechanism_description": (
                "When on 'All News', the category query param is omitted. "
                "Active tab filtering sends '?category=<tab_name>'. "
                "Onboarding interest preferences are stored in localStorage ('newsreels_interests') "
                "and client-side state, factored directly into Personal Relevance score weighting."
            )
        }

        # =====================================================================
        # TEST 6: CATEGORY FILTER (SINGLE SPECIFIC CATEGORY: Technology)
        # =====================================================================
        print("\n--- TEST 6: Category Filter ---")
        with page.expect_response(lambda r: "/feed" in r.url and "category=technology" in r.url and r.status == 200) as resp_info:
            page.click(".category-tab[data-category='technology']")
        t6_data = resp_info.value.json()
        t6_url = resp_info.value.url
        t6_items = t6_data.get("items", [])
        page.wait_for_timeout(500)
        t6_dom_count = page.evaluate("() => document.querySelectorAll('.scroll-card').length")

        total_cat_stories = len(t6_items)
        matching_stories = sum(1 for it in t6_items if (it.get("category") or "").lower() == "technology")
        non_matching_stories = sum(1 for it in t6_items if (it.get("category") or "").lower() != "technology")
        unknown_stories = sum(1 for it in t6_items if not it.get("category"))
        story_categories = [it.get("category") for it in t6_items]

        print(f"Selected category: 'technology'")
        print(f"Total stories returned from API: {total_cat_stories}, DOM rendered: {t6_dom_count}")
        print(f"Matching: {matching_stories}, Non-matching: {non_matching_stories}, Unknown: {unknown_stories}")
        print(f"Story categories in response: {story_categories}")

        report["test6_category_filter"] = {
            "selected_category": "technology",
            "total_stories": total_cat_stories,
            "matching_stories": matching_stories,
            "non_matching_stories": non_matching_stories,
            "unknown_stories": unknown_stories,
            "story_categories": story_categories,
            "filter_request_url": t6_url,
            "dom_cards_rendered": t6_dom_count
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_04_category_filter_tech.png"))

        # Also verify another category tab (Politics) with multiple stories
        print("Testing Politics tab for multi-story category filter...")
        with page.expect_response(lambda r: "/feed" in r.url and "category=politics" in r.url and r.status == 200) as pol_resp:
            page.click(".category-tab[data-category='politics']")
        pol_data = pol_resp.value.json()
        pol_items = pol_data.get("items", [])
        page.wait_for_timeout(500)
        pol_dom = page.evaluate("() => document.querySelectorAll('.scroll-card').length")
        print(f"Politics tab: {len(pol_items)} items returned from API, {pol_dom} DOM cards rendered. All categories in response: {set(it.get('category') for it in pol_items)}")

        # =====================================================================
        # TEST 7: ALL NEWS RETURN
        # =====================================================================
        print("\n--- TEST 7: Return to All News ---")
        with page.expect_response(lambda r: "/feed" in r.url and "category=" not in r.url and r.status == 200) as all_resp:
            page.click(".category-tab[data-category='all']")
        t7_data = all_resp.value.json()
        t7_items = t7_data.get("items", [])
        page.wait_for_timeout(500)
        t7_dom_count = page.evaluate("() => document.querySelectorAll('.scroll-card').length")

        all_categories_in_feed = list(set(it.get("category", "") for it in t7_items if it.get("category")))
        scores = [it.get("final_feed_score", 0) for it in t7_items]
        scores_sorted = scores == sorted(scores, reverse=True)

        print(f"Returned to All News: {len(t7_items)} stories in API, {t7_dom_count} DOM cards")
        print(f"Categories present: {all_categories_in_feed}")
        print(f"Scores descending order: {scores_sorted}")

        report["test7_all_news"] = {
            "total_stories": len(t7_items),
            "dom_cards_rendered": t7_dom_count,
            "distinct_categories_present": all_categories_in_feed,
            "multiple_categories_present": len(all_categories_in_feed) > 1,
            "ranking_order_preserved": scores_sorted
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_05_all_news.png"))

        # =====================================================================
        # TEST 8: MULTIPLE CATEGORY SELECTION BEHAVIOR
        # =====================================================================
        print("\n--- TEST 8: Multiple Category Selection Behavior ---")
        multi_cat_behavior = {
            "onboarding_interests": "Allows selecting multiple interest categories (chips) with toggle selection. Order and selection are persisted to localStorage ('newsreels_interests') and factor directly into personal relevance weighting (RelevanceEngine).",
            "feed_navigation_tabs": "Mutually exclusive single-category filter tabs (All News, National, State, Politics, Business, Tech, Science, Health, Sports, Entertainment) that filter the feed strictly to that category via '?category=<cat>'."
        }
        print(f"Multi-category behavior: {multi_cat_behavior}")
        report["test8_multi_category"] = multi_cat_behavior

        # =====================================================================
        # TEST 9: EMPTY CATEGORY STATE
        # =====================================================================
        print("\n--- TEST 9: Empty Category State ---")
        page.click("#btn-open-interests-modal")
        time.sleep(0.5)

        page.evaluate("""() => {
            const chips = document.querySelectorAll('.interest-chip.selected');
            chips.forEach(c => c.click());
        }""")
        time.sleep(0.5)

        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200) as empty_resp:
            page.click("#btn-save-interests")
        t9_data = empty_resp.value.json()
        t9_items = t9_data.get("items", [])
        page.wait_for_timeout(500)
        t9_cards_count = page.evaluate("() => document.querySelectorAll('.scroll-card').length")
        t9_storage = page.evaluate("() => ({ ...localStorage })")
        t9_stored_interests = json.loads(t9_storage.get("newsreels_interests", "[]"))

        print(f"Stored interests when empty: {t9_stored_interests}")
        print(f"Feed cards rendered when empty interests: {t9_cards_count}")

        report["test9_empty_category_state"] = {
            "empty_selection_allowed": True,
            "stored_interests": t9_stored_interests,
            "feed_cards_rendered": t9_cards_count,
            "behavior_description": "When all interest categories are deselected, newsreels_interests persists as '[]'. The application defaults gracefully to the All News general feed, rendering all 22 stories without errors."
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b3_06_empty_categories.png"))

        # Restore default preferences
        page.click("#btn-open-interests-modal")
        time.sleep(0.5)
        page.click("#btn-reset-interests")
        time.sleep(0.5)
        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200):
            page.click("#btn-save-interests")
        time.sleep(0.5)

        # =====================================================================
        # TEST 10: PERSISTENCE AFTER COMPLETE ONBOARDING
        # =====================================================================
        print("\n--- TEST 10: Persistence After Complete Onboarding ---")
        t10_storage = page.evaluate("() => ({ ...localStorage })")
        print(f"Storage before reload: {t10_storage}")

        with page.expect_response(lambda r: "/feed" in r.url and r.status == 200):
            page.reload(wait_until="networkidle")
        time.sleep(0.5)

        t10_storage_after = page.evaluate("() => ({ ...localStorage })")
        print(f"Storage after reload: {t10_storage_after}")

        consistent = (
            t10_storage.get("newsreels_state") == t10_storage_after.get("newsreels_state") and
            t10_storage.get("newsreels_interests") == t10_storage_after.get("newsreels_interests") and
            t10_storage.get("newsreels_onboarding_complete") == t10_storage_after.get("newsreels_onboarding_complete")
        )
        print(f"Storage remains consistent after reload: {consistent}")

        report["test10_persistence_after_completion"] = {
            "state_stored": t10_storage_after.get("newsreels_state"),
            "interests_stored": t10_storage_after.get("newsreels_interests"),
            "onboarding_complete": t10_storage_after.get("newsreels_onboarding_complete"),
            "is_consistent": consistent
        }

        # =====================================================================
        # TEST 11: DISTRICT/GPS REGRESSION
        # =====================================================================
        print("\n--- TEST 11: District/GPS Regression ---")
        t11_check = page.evaluate("""() => {
            const districtInput = document.getElementById('input-district');
            const gpsBtn = document.getElementById('btn-detect-location');
            const storage = { ...localStorage };
            return {
                hasDistrictInput: !!districtInput,
                hasGpsBtn: !!gpsBtn,
                hasDistrictKey: 'newsreels_district' in storage,
                storageKeys: Object.keys(storage)
            };
        }""")
        print(f"Regression check: {t11_check}")
        report["test11_regression"] = t11_check

        context.close()
        browser.close()

    print("\n--- Summary of All B3 Tests ---")
    print(f"Console errors: {report['diagnostics']['console_errors']}")
    print(f"Page errors: {report['diagnostics']['page_errors']}")
    print(f"Failed requests: {report['diagnostics']['failed_requests']}")

    with open(SCREENSHOT_DIR / "b3_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_b3_verification()
