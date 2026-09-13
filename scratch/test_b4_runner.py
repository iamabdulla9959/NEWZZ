import os
import json
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = r"d:\News\scratch\b4_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run_test():
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
            if "/feed" in res.url or "/preferences" in res.url or "/user" in res.url:
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

        print("=== TEST 1: FIND PRIORITY RANKING ===")
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        # Step 1: Welcome
        welcome_visible = page.is_visible("#modal-welcome")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_welcome.png"))
        print(f"Welcome modal visible: {welcome_visible}")
        page.click("#btn-welcome-start")
        page.wait_for_timeout(500)

        # Step 2: State
        state_visible = page.is_visible("#modal-location")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_state.png"))
        print(f"State modal visible: {state_visible}")
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        page.wait_for_timeout(500)

        # Step 3: Categories / Interests
        interests_visible = page.is_visible("#modal-interests")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_categories.png"))
        modal_title = page.inner_text("#interests-modal-title")
        modal_desc = page.inner_text("#modal-interests .modal-text")
        chips = page.query_selector_all("#interest-chips-container .interest-chip")
        chip_names = [c.inner_text().replace("+", "").replace("✓", "").strip() for c in chips]
        print(f"Interests modal visible: {interests_visible}")
        print(f"Title: {modal_title}")
        print(f"Description: {modal_desc}")
        print(f"Categories displayed ({len(chip_names)}): {chip_names}")

        # Check if there is another step after this or if saving immediately finishes onboarding
        # In Categories step, let's select 4 categories: Technology, Business, Politics, National
        # Currently Technology, National, Business, Politics are default selected (or let's check which are selected)
        selected_before = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('#interest-chips-container .interest-chip.selected'))
                .map(el => el.getAttribute('data-category'));
        }""")
        print(f"Initially selected chips: {selected_before}")

        # Check for any reordering UI controls (drag handles, move up/down buttons, order numbers)
        reorder_controls = page.evaluate("""() => {
            const container = document.getElementById('interest-chips-container');
            const handles = container.querySelectorAll('.drag-handle, .btn-move-up, .btn-move-down, .reorder-btn, [draggable="true"]');
            return {
                handleCount: handles.length,
                draggableElements: Array.from(container.querySelectorAll('*')).filter(el => el.getAttribute('draggable') === 'true').length
            };
        }""")
        print(f"Reorder controls inside modal: {reorder_controls}")

        # Check if there is another modal in DOM for Priority Ranking
        modals_in_dom = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.modal-backdrop')).map(el => ({
                id: el.id,
                title: el.querySelector('.modal-title')?.textContent?.trim() || ''
            }));
        }""")
        print(f"Modals in DOM: {modals_in_dom}")

        # Save preferences
        page.click("#btn-save-interests")
        page.wait_for_timeout(1000)

        # Check if another modal opened or if feed loaded
        feed_visible = page.is_visible("#feed-container")
        modals_visible = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.modal-backdrop:not(.hidden)')).map(el => el.id);
        }""")
        print(f"Modals visible after saving interests: {modals_visible}")
        print(f"Feed visible: {feed_visible}")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_after_saving_interests.png"))

        # Check localStorage
        local_storage_data = page.evaluate("() => ({ ...localStorage })")
        print(f"LocalStorage data: {json.dumps(local_storage_data, indent=2)}")

        # Check network calls made
        print(f"Network calls: {json.dumps(network_calls, indent=2)}")

        # Fetch feed response data directly to inspect personal relevance scores of cards
        device_id = local_storage_data.get("newsreels_device_id", "")
        feed_url = f"{BASE_URL}/feed?device_id={device_id}&limit=30&state=Karnataka"
        feed_res = page.evaluate(f"""async () => {{
            const res = await fetch('{feed_url}');
            return await res.json();
        }}""")

        cards_preview = []
        for c in (feed_res.get("items", []) if isinstance(feed_res, dict) else feed_res)[:5]:
            cards_preview.append({
                "headline": c.get("headline"),
                "category": c.get("category"),
                "state": c.get("state"),
                "personal_relevance_score": c.get("personal_relevance_score"),
                "importance_score": c.get("importance_score"),
                "urgency_score": c.get("urgency_score"),
                "freshness_score": c.get("freshness_score"),
                "verification_score": c.get("verification_score"),
                "final_feed_score": c.get("final_feed_score"),
            })
        print(f"Sample cards from feed with device_id={device_id}:")
        print(json.dumps(cards_preview, indent=2))

        # Check console / page errors
        print(f"Console errors: {[l for l in console_logs if 'error' in l.lower()]}")
        print(f"Page errors: {page_errors}")
        print(f"Failed requests: {failed_requests}")

        browser.close()

if __name__ == "__main__":
    run_test()
