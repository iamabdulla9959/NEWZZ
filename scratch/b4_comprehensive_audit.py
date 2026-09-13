import os
import json
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = r"d:\News\scratch\b4_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def audit_b4():
    results = {}
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

        # ----------------------------------------------------
        # TEST 1 — FIND PRIORITY RANKING
        # ----------------------------------------------------
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        # Step 1: Welcome
        w_visible = page.is_visible("#modal-welcome")
        results["test1_welcome_visible"] = w_visible
        page.click("#btn-welcome-start")
        page.wait_for_timeout(300)

        # Step 2: State
        s_visible = page.is_visible("#modal-location")
        results["test1_state_visible"] = s_visible
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        page.wait_for_timeout(300)

        # Step 3: Categories / Interests
        c_visible = page.is_visible("#modal-interests")
        results["test1_categories_modal_visible"] = c_visible
        results["test1_modal_selector"] = "#modal-interests"
        results["test1_heading_text"] = page.inner_text("#interests-modal-title")
        results["test1_desc_text"] = page.inner_text("#modal-interests .modal-text")

        chips = page.query_selector_all("#interest-chips-container .interest-chip")
        avail_cats = [c.inner_text().replace("+", "").replace("✓", "").strip() for c in chips]
        results["test1_available_categories"] = avail_cats

        init_selected = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('#interest-chips-container .interest-chip.selected'))
                .map(el => el.getAttribute('data-category'));
        }""")
        results["test1_initial_selected"] = init_selected

        # Check if there is any separate step after Categories for Priority Ranking
        # Let's inspect all modals in the DOM
        all_modals = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.modal-backdrop')).map(el => ({
                id: el.id,
                title: el.querySelector('.modal-title')?.textContent?.trim() || ''
            }));
        }""")
        results["test1_all_modals_in_dom"] = all_modals

        # Check for any reordering UI controls
        reorder_ui = page.evaluate("""() => {
            const container = document.getElementById('interest-chips-container');
            const chips = Array.from(container.querySelectorAll('.interest-chip'));
            return {
                chipsCount: chips.length,
                chipsDraggable: chips.some(c => c.getAttribute('draggable') === 'true'),
                hasMoveButtons: chips.some(c => c.querySelector('.btn-up, .btn-down, .move-btn, .order-arrow') !== null),
                hasRankInputs: chips.some(c => c.querySelector('input[type="number"], select') !== null),
                hasOrderNumbers: chips.some(c => c.querySelector('.rank-badge, .order-num') !== null)
            };
        }""")
        results["test1_reorder_ui"] = reorder_ui

        # ----------------------------------------------------
        # TEST 2 — INITIAL ORDER
        # ----------------------------------------------------
        # Selected categories in Categories step:
        # Let's deselect all, then select 4 in order: Technology, Business, Politics, National
        page.evaluate("""() => {
            const desired = ['Technology', 'Business', 'Politics', 'National'];
            // Click all currently selected to deselect
            document.querySelectorAll('#interest-chips-container .interest-chip.selected').forEach(c => c.click());
            // Now click desired in order
            desired.forEach(cat => {
                const btn = document.querySelector(`#chip-interest-${cat.toLowerCase()}`);
                if (btn) btn.click();
            });
        }""")
        page.wait_for_timeout(300)

        displayed_chips_after_selection = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('#interest-chips-container .interest-chip')).map(c => ({
                category: c.getAttribute('data-category'),
                selected: c.classList.contains('selected'),
                text: c.innerText.trim()
            }));
        }""")
        results["test2_displayed_chips"] = displayed_chips_after_selection
        results["test2_internal_state_interests"] = page.evaluate("() => window.state ? window.state.interests : 'not global'")

        # ----------------------------------------------------
        # TEST 3 — REORDER MECHANISM
        # ----------------------------------------------------
        # Can the user reorder chips in the UI?
        # Is there any drag and drop or reorder buttons?
        # Let's record the UI capability
        results["test3_can_reorder_ui"] = (
            reorder_ui["chipsDraggable"] or 
            reorder_ui["hasMoveButtons"] or 
            reorder_ui["hasRankInputs"]
        )

        # ----------------------------------------------------
        # TEST 4 — STORAGE
        # ----------------------------------------------------
        # Click Save Preferences
        page.click("#btn-save-interests")
        page.wait_for_timeout(500)

        storage_after_save = page.evaluate("() => ({ ...localStorage })")
        results["test4_storage"] = storage_after_save
        results["test4_interests_storage_key"] = "newsreels_interests"
        results["test4_stored_value"] = storage_after_save.get("newsreels_interests")

        # ----------------------------------------------------
        # TEST 5 — RELOAD DURING ONBOARDING
        # ----------------------------------------------------
        page.evaluate("""() => {
            localStorage.clear();
            localStorage.setItem('newsreels_state', 'Karnataka');
            localStorage.setItem('newsreels_interests', JSON.stringify(['Politics', 'National', 'Technology', 'Business']));
            // Note: onboarding_complete is NOT set
        }""")
        page.reload()
        page.wait_for_load_state("networkidle")
        
        t5_welcome_vis = page.is_visible("#modal-welcome")
        t5_feed_has_cards = page.evaluate("""() => document.querySelectorAll('#feed-container .scroll-card').length""")
        results["test5_welcome_visible_after_reload"] = t5_welcome_vis
        results["test5_feed_card_count_mid_onboarding"] = t5_feed_has_cards
        results["test5_storage_mid_onboarding"] = page.evaluate("() => ({ ...localStorage })")

        # ----------------------------------------------------
        # TEST 6 — COMPLETE ONBOARDING
        # ----------------------------------------------------
        # Go through to complete
        page.click("#btn-welcome-start")
        page.wait_for_timeout(300)
        page.click("#btn-save-location")
        page.wait_for_timeout(300)
        page.click("#btn-save-interests")
        page.wait_for_timeout(500)

        t6_complete = page.evaluate("() => localStorage.getItem('newsreels_onboarding_complete')")
        t6_feed_visible = page.is_visible("#feed-container")
        t6_cards_rendered = page.evaluate("""() => document.querySelectorAll('#feed-container .scroll-card').length""")
        results["test6_onboarding_complete_value"] = t6_complete
        results["test6_feed_visible"] = t6_feed_visible
        results["test6_cards_rendered"] = t6_cards_rendered

        # ----------------------------------------------------
        # TEST 7 — RELOAD AFTER COMPLETION
        # ----------------------------------------------------
        page.reload()
        page.wait_for_load_state("networkidle")
        t7_storage = page.evaluate("() => ({ ...localStorage })")
        t7_welcome_vis = page.is_visible("#modal-welcome")
        t7_cards = page.evaluate("""() => document.querySelectorAll('#feed-container .scroll-card').length""")
        results["test7_storage"] = t7_storage
        results["test7_welcome_vis"] = t7_welcome_vis
        results["test7_cards_count"] = t7_cards

        # ----------------------------------------------------
        # TEST 8, 9, 10 — PERSONAL RELEVANCE & OBJECTIVE SEPARATION
        # ----------------------------------------------------
        # Let's test how category order affects Personal Relevance:
        # Case A: Order A = ["technology", "business", "politics", "national"]
        # Case B: Order B = ["politics", "technology", "business", "national"]
        # Using FastAPI TestClient / Backend RelevanceEngine
        device_id_test = t7_storage.get("newsreels_device_id", "test-dev-b4")
        
        # Check regression & errors
        results["console_errors"] = [l for l in console_logs if "error" in l.lower()]
        results["page_errors"] = page_errors
        results["failed_requests"] = failed_requests
        results["district_in_dom"] = page.is_visible("#input-district")
        results["gps_in_dom"] = page.is_visible("#btn-detect-location")
        results["district_key_in_storage"] = "newsreels_district" in t7_storage

        browser.close()

    print(json.dumps(results, indent=2))
    with open(r"d:\News\scratch\b4_audit_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    audit_b4()
