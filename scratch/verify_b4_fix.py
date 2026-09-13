import os
import sys
sys.path.insert(0, r"d:\News")
sys.path.insert(0, r"d:\News\apps\api")
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8')
import json
import time
from playwright.sync_api import sync_playwright
from app.db import SessionLocal
from app.models import UserPreferences

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = r"d:\News\scratch\b4_fix_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run_b4_verification():
    report = {}
    
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
        network_calls = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}"))
        
        def handle_response(res):
            if "/user" in res.url or "/preferences" in res.url or "/feed" in res.url:
                try:
                    network_calls.append({
                        "url": res.url,
                        "status": res.status,
                        "method": res.request.method,
                        "post_data": res.request.post_data
                    })
                except Exception:
                    pass
        page.on("response", handle_response)

        print("--- TEST 1 & 2: CLEAN ONBOARDING & SELECT CATEGORIES ---")
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        # Step 1: Welcome
        assert page.is_visible("#modal-welcome"), "Welcome modal must be visible on clean start"
        page.click("#btn-welcome-start")
        page.wait_for_timeout(300)

        # Step 2: State
        assert page.is_visible("#modal-location"), "State modal must be visible after Welcome"
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        page.wait_for_timeout(300)

        # Step 3: Categories
        assert page.is_visible("#modal-interests"), "Categories modal must be visible after State"
        # Select exactly 4 categories: Technology, Business, Politics, National
        page.evaluate("""() => {
            // Deselect everything first
            document.querySelectorAll('#interest-chips-container .interest-chip.selected').forEach(c => c.click());
            // Select our 4 categories in order
            ['Technology', 'Business', 'Politics', 'National'].forEach(cat => {
                const btn = document.querySelector(`#chip-interest-${cat.toLowerCase()}`);
                if (btn) btn.click();
            });
        }""")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_categories_selected.png"))

        # Click Continue in Categories step
        page.click("#btn-save-interests")
        page.wait_for_timeout(400)

        # Step 4: Priority Ranking Step!
        priority_visible = page.is_visible("#modal-priority")
        report["test1_priority_step_exists"] = priority_visible
        report["test1_selector"] = "#modal-priority"
        report["test1_heading"] = page.inner_text("#priority-modal-title")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_priority_ranking_modal.png"))
        print(f"Priority Step visible: {priority_visible}")
        print(f"Heading: {report['test1_heading']}")

        # Verify displayed categories in Priority modal
        priority_items = page.query_selector_all("#priority-list-container .priority-item")
        displayed_cats = [item.get_attribute("data-category") for item in priority_items]
        report["test2_priority_displayed_cats"] = displayed_cats
        print(f"Categories in Priority list: {displayed_cats}")
        assert displayed_cats == ["Technology", "Business", "Politics", "National"], f"Expected exactly 4 selected categories, got {displayed_cats}"

        print("--- TEST 3: REORDER USING UI BUTTONS (↑ and ↓) ---")
        # Initial: Technology(0), Business(1), Politics(2), National(3)
        # Goal: Politics(0), National(1), Technology(2), Business(3)
        # 1. Move Politics up twice:
        # Politics is at index 2. Click Up: Politics at 1, Business at 2.
        page.click("#btn-priority-up-politics")
        page.wait_for_timeout(200)
        # Click Up again: Politics at 0, Technology at 1.
        page.click("#btn-priority-up-politics")
        page.wait_for_timeout(200)

        # Current order: Politics(0), Technology(1), Business(2), National(3)
        # 2. Move National up:
        # National is at index 3. Click Up: National at 2, Business at 3.
        page.click("#btn-priority-up-national")
        page.wait_for_timeout(200)
        # Current order: Politics(0), Technology(1), National(2), Business(3)
        # Click Up again: National at 1, Technology at 2.
        page.click("#btn-priority-up-national")
        page.wait_for_timeout(200)

        # Final order: Politics, National, Technology, Business
        final_items = page.query_selector_all("#priority-list-container .priority-item")
        final_cats = [item.get_attribute("data-category") for item in final_items]
        report["test3_final_reordered_cats"] = final_cats
        print(f"Reordered categories in UI: {final_cats}")
        assert final_cats == ["Politics", "National", "Technology", "Business"], f"Reordering failed, got {final_cats}"
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_priority_reordered.png"))

        print("--- TEST 4 & 5 & 6: SAVE, STORAGE, BACKEND PERSISTENCE, COMPLETION ---")
        network_calls.clear()
        page.click("#btn-save-priority")
        page.wait_for_timeout(1000)

        # Check localStorage
        storage = page.evaluate("() => ({ ...localStorage })")
        report["test4_storage"] = storage
        print(f"LocalStorage after save: {json.dumps(storage, indent=2)}")
        assert storage.get("newsreels_onboarding_complete") == "true", "newsreels_onboarding_complete must be true"
        assert storage.get("newsreels_state") == "Karnataka", "newsreels_state must be Karnataka"
        assert json.loads(storage.get("newsreels_priority_order")) == ["Politics", "National", "Technology", "Business"], "Priority order stored correctly"

        # Check network call to PUT /user/{device_id}/preferences
        device_id = storage.get("newsreels_device_id")
        put_calls = [c for c in network_calls if f"/user/{device_id}/preferences" in c["url"] and c["method"] == "PUT"]
        report["test5_put_calls"] = put_calls
        print(f"PUT preferences network call: {json.dumps(put_calls, indent=2)}")
        assert len(put_calls) == 1, "PUT preferences request must have been sent exactly once"
        sent_body = json.loads(put_calls[0]["post_data"])
        assert sent_body.get("category_order") == ["politics", "national", "technology", "business"], f"Unexpected sent body: {sent_body}"

        # Check database directly
        db = SessionLocal()
        db_pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
        assert db_pref is not None, "UserPreferences record must exist in database"
        report["test5_db_category_order"] = db_pref.category_order
        print(f"Database category_order for device {device_id}: {db_pref.category_order}")
        assert db_pref.category_order == ["politics", "national", "technology", "business"], "Database matches sent order"
        db.close()

        # Check feed rendered
        feed_cards = page.query_selector_all("#feed-container .scroll-card")
        report["test6_feed_card_count"] = len(feed_cards)
        print(f"Feed card count after completion: {len(feed_cards)}")
        assert len(feed_cards) > 0, "Feed must be populated after onboarding"
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_feed_loaded.png"))

        print("--- TEST 7: RELOAD AFTER COMPLETION ---")
        page.reload()
        page.wait_for_load_state("networkidle")
        welcome_visible_after_reload = page.is_visible("#modal-welcome")
        priority_visible_after_reload = page.is_visible("#modal-priority")
        feed_cards_after_reload = page.query_selector_all("#feed-container .scroll-card")
        assert not welcome_visible_after_reload, "Welcome modal must not appear on reload after completion"
        assert not priority_visible_after_reload, "Priority modal must not appear on reload after completion"
        assert len(feed_cards_after_reload) == len(feed_cards), "Feed cards must load directly after reload"

        print("--- TEST 8: RANKING ENGINE VERIFICATION ---")
        # Fetch current feed data with the saved priority order (Politics=Rank 1, National=Rank 2, Tech=Rank 3)
        feed_data = page.evaluate(f"""async () => {{
            const res = await fetch('{BASE_URL}/feed?device_id={device_id}&limit=30');
            return await res.json();
        }}""")
        items = feed_data if isinstance(feed_data, list) else feed_data.get("items", [])
        
        pol_card = next((c for c in items if c.get("category") == "politics"), None)
        nat_card = next((c for c in items if c.get("category") == "national" and not c.get("state")), None)
        tech_card = next((c for c in items if c.get("category") == "technology"), None)

        print(f"Politics card (Rank 1): rel={pol_card.get('personal_relevance_score') if pol_card else None}")
        print(f"Technology card (Rank 3): rel={tech_card.get('personal_relevance_score') if tech_card else None}")
        
        # Rank 1 interest component = 50.0 (loc neutral 25 + 50 = 75.0)
        # Rank 3 interest component = 40.0 (loc neutral 25 + 40 = 65.0)
        assert pol_card is not None and pol_card.get("personal_relevance_score") == 75.0, f"Rank 1 politics should have relevance 75.0, got {pol_card.get('personal_relevance_score') if pol_card else None}"
        assert tech_card is not None and tech_card.get("personal_relevance_score") == 65.0, f"Rank 3 tech should have relevance 65.0, got {tech_card.get('personal_relevance_score') if tech_card else None}"

        print("--- TEST 9: CHANGE PRIORITY ORDER (PROMOTE TECH TO RANK 1) ---")
        # Open interests modal from header
        page.click("#btn-open-interests-modal")
        page.wait_for_timeout(300)
        # Click Continue to go to Priority modal
        page.click("#btn-save-interests")
        page.wait_for_timeout(300)
        # Current order: Politics, National, Technology, Business
        # Move Technology up twice to make it Rank 1:
        page.click("#btn-priority-up-technology")
        page.wait_for_timeout(200)
        page.click("#btn-priority-up-technology")
        page.wait_for_timeout(200)

        # Verify Technology is now index 0
        new_priority_items = page.query_selector_all("#priority-list-container .priority-item")
        new_cats = [item.get_attribute("data-category") for item in new_priority_items]
        print(f"New priority order before save: {new_cats}")
        assert new_cats[0] == "Technology", f"Technology should be rank 1, got {new_cats}"

        # Save new priorities
        page.click("#btn-save-priority")
        page.wait_for_timeout(800)

        # Check updated database category_order
        db = SessionLocal()
        db_pref = db.query(UserPreferences).filter(UserPreferences.device_id == device_id).first()
        print(f"Updated DB order: {db_pref.category_order}")
        assert db_pref.category_order[0] == "technology", f"DB order should have tech at 0, got {db_pref.category_order}"
        db.close()

        # Re-fetch feed data
        feed_data_new = page.evaluate(f"""async () => {{
            const res = await fetch('{BASE_URL}/feed?device_id={device_id}&limit=30');
            return await res.json();
        }}""")
        items_new = feed_data_new if isinstance(feed_data_new, list) else feed_data_new.get("items", [])
        tech_card_new = next((c for c in items_new if c.get("category") == "technology"), None)
        pol_card_new = next((c for c in items_new if c.get("category") == "politics"), None)

        print(f"Technology card (now Rank 1): rel={tech_card_new.get('personal_relevance_score') if tech_card_new else None}")
        print(f"Politics card (now Rank 2): rel={pol_card_new.get('personal_relevance_score') if pol_card_new else None}")
        assert tech_card_new.get("personal_relevance_score") == 75.0, f"Technology promoted to Rank 1 must have rel=75.0, got {tech_card_new.get('personal_relevance_score')}"
        assert pol_card_new.get("personal_relevance_score") == 70.0, f"Politics demoted to Rank 2 must have rel=70.0, got {pol_card_new.get('personal_relevance_score')}"

        print("--- TEST 10: RELOAD MID-PRIORITY ---")
        page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('newsreels_state', 'Karnataka');
            localStorage.setItem('newsreels_interests', JSON.stringify(['Technology', 'Politics']));
            localStorage.setItem('newsreels_priority_order', JSON.stringify(['Technology', 'Politics']));
            // Note: newsreels_onboarding_complete is absent!
        }""")
        page.reload()
        page.wait_for_load_state("networkidle")
        welcome_vis_t10 = page.is_visible("#modal-welcome")
        cards_t10 = page.query_selector_all("#feed-container .scroll-card")
        print(f"Mid-priority reload: welcome visible={welcome_vis_t10}, cards rendered={len(cards_t10)}")
        assert welcome_vis_t10, "Onboarding must not be considered complete"
        assert len(cards_t10) == 0, "Feed must not appear prematurely"

        print("--- TEST 11: EMPTY CATEGORIES / PRIORITY ---")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")
        page.click("#btn-welcome-start")
        page.wait_for_timeout(200)
        page.click("#btn-save-location")
        page.wait_for_timeout(200)
        # Deselect all categories
        page.evaluate("""() => {
            document.querySelectorAll('#interest-chips-container .interest-chip.selected').forEach(c => c.click());
        }""")
        page.wait_for_timeout(200)
        page.click("#btn-save-interests")
        page.wait_for_timeout(300)
        
        # In Priority modal, verify empty message
        empty_msg = page.is_visible(".priority-empty-msg")
        print(f"Empty priority message visible: {empty_msg}")
        assert empty_msg, "Empty message should display when 0 categories selected"

        # Save with empty priority
        page.click("#btn-save-priority")
        page.wait_for_timeout(800)
        storage_empty = page.evaluate("() => ({ ...localStorage })")
        dev_empty = storage_empty.get("newsreels_device_id")
        
        db = SessionLocal()
        db_pref_empty = db.query(UserPreferences).filter(UserPreferences.device_id == dev_empty).first()
        print(f"DB order for empty user: {db_pref_empty.category_order if db_pref_empty else None}")
        assert db_pref_empty is not None and db_pref_empty.category_order == [], "Empty priority handled gracefully in DB"
        db.close()

        print("--- REGRESSION CHECKS ---")
        report["district_in_dom"] = page.is_visible("#input-district")
        report["gps_in_dom"] = page.is_visible("#btn-detect-location")
        report["district_in_storage"] = "newsreels_district" in storage_empty
        assert not report["district_in_dom"], "District input must remain absent"
        assert not report["gps_in_dom"], "GPS button must remain absent"
        assert not report["district_in_storage"], "newsreels_district must remain absent"

        report["console_errors"] = [l for l in console_logs if "error" in l.lower()]
        report["page_errors"] = page_errors
        report["failed_requests"] = failed_requests
        print(f"Console errors: {report['console_errors']}")
        print(f"Page errors: {report['page_errors']}")
        print(f"Failed requests: {report['failed_requests']}")
        assert len(report["console_errors"]) == 0, f"Console errors found: {report['console_errors']}"
        assert len(report["page_errors"]) == 0, f"Page errors found: {report['page_errors']}"
        assert len(report["failed_requests"]) == 0, f"Failed requests found: {report['failed_requests']}"

        browser.close()

    print("\nALL B4 FIX VERIFICATIONS PASSED SUCCESSFULLY!")
    with open(r"d:\News\scratch\b4_fix_results.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_b4_verification()
