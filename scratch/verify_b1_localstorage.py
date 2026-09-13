import sys
import json
import time
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

def run_b1_verification():
    report = {
        "initial_storage_before_launch": {},
        "first_launch": {},
        "after_state_selection": {},
        "reload_test": {},
        "clean_reset": {},
        "browser_diagnostics": {
            "console_errors": [],
            "page_errors": [],
            "failed_requests": []
        }
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: report["browser_diagnostics"]["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: report["browser_diagnostics"]["page_errors"].append(str(err)))
        page.on("requestfailed", lambda req: report["browser_diagnostics"]["failed_requests"].append(f"{req.method} {req.url}: {req.failure}"))

        # Step 2: Clean browser state
        print("Opening page to initialize origin...")
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.clear();")
        
        # Verify localStorage is empty before launch
        storage_before = page.evaluate("() => ({ ...localStorage })")
        report["initial_storage_before_launch"] = storage_before
        print(f"Storage before launch: {storage_before}")

        # Step 3: First launch with empty localStorage
        print("Reloading page with completely empty localStorage...")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Inspect localStorage right after load
        storage_on_load = page.evaluate("() => ({ ...localStorage })")
        print(f"Storage immediately on first load: {storage_on_load}")
        report["storage_on_first_load"] = storage_on_load

        # Inspect first screen visible
        first_screen_info = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const feed = document.getElementById('feed-container');

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                welcomeTitle: welcome.querySelector('.modal-title')?.textContent?.trim(),
                welcomeBadge: welcome.querySelector('.modal-badge')?.textContent?.trim(),
                welcomeBtnText: welcome.querySelector('#btn-welcome-start')?.textContent?.trim(),
                locationVisible: !location.classList.contains('hidden'),
                hasDistrictInput: !!document.getElementById('input-district'),
                hasDistrictLabel: !!document.querySelector('label[for="input-district"]'),
                hasStateInput: !!document.getElementById('input-state'),
                hasGpsBtn: !!document.getElementById('btn-detect-location'),
                hasSaveBtn: !!document.getElementById('btn-save-location'),
                feedCardsCount: document.querySelectorAll('.scroll-card').length
            };
        }""")
        print(f"First screen info: {first_screen_info}")
        report["first_launch"] = first_screen_info
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_01_first_launch.png"))

        # Advance through Welcome modal
        print("Clicking Start Reading on Welcome modal...")
        page.click("#btn-welcome-start")
        time.sleep(0.5)

        # Inspect screen after Welcome
        second_screen_info = page.evaluate("""() => {
            const location = document.getElementById('modal-location');
            const title = location.querySelector('.modal-title')?.textContent?.trim();
            const bodyText = location.querySelector('.modal-text')?.textContent?.trim();
            const districtInput = document.getElementById('input-district');
            const stateInput = document.getElementById('input-state');
            const gpsBtn = document.getElementById('btn-detect-location');
            const saveBtn = document.getElementById('btn-save-location');
            const skipBtn = document.getElementById('btn-skip-location');

            return {
                locationModalVisible: !location.classList.contains('hidden'),
                title: title,
                bodyText: bodyText,
                hasDistrictInput: !!districtInput,
                districtPlaceholder: districtInput?.placeholder,
                hasStateInput: !!stateInput,
                statePlaceholder: stateInput?.placeholder,
                hasGpsBtn: !!gpsBtn,
                gpsBtnText: gpsBtn?.textContent?.trim(),
                hasSaveBtn: !!saveBtn,
                saveBtnText: saveBtn?.textContent?.trim(),
                hasSkipBtn: !!skipBtn,
                skipBtnText: skipBtn?.textContent?.trim()
            };
        }""")
        print(f"Location screen info: {second_screen_info}")
        report["location_screen_info"] = second_screen_info
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_02_location_modal.png"))

        # Step 4: Verify localStorage after state
        print("Entering state 'Karnataka' without district...")
        page.fill("#input-state", "Karnataka")
        # Do not fill district
        page.click("#btn-save-location")
        time.sleep(0.5)

        storage_after_state = page.evaluate("() => ({ ...localStorage })")
        print(f"Storage after state selection: {storage_after_state}")
        report["after_state_selection"] = {
            "storage": storage_after_state,
            "has_district": "newsreels_district" in storage_after_state,
            "district_val": storage_after_state.get("newsreels_district"),
            "has_state": "newsreels_state" in storage_after_state,
            "state_val": storage_after_state.get("newsreels_state"),
            "has_gps": any("gps" in k.lower() or "lat" in k.lower() or "coord" in k.lower() for k in storage_after_state)
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_03_after_state_interests.png"))

        # Step 5: Clean-state reload (reload after state selection before completing interests)
        print("Reloading page before completing interests...")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        reload_screen_info = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                headerLocationLabel: locationLabel,
                feedCardsCount: document.querySelectorAll('.scroll-card').length,
                storage: { ...localStorage }
            };
        }""")
        print(f"Screen after reload: {reload_screen_info}")
        report["reload_test"] = reload_screen_info
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_04_after_reload.png"))

        # Step 6: Full clean reset
        print("Testing full clean reset...")
        page.evaluate("localStorage.clear();")
        storage_cleared = page.evaluate("() => ({ ...localStorage })")
        print(f"Storage after clear: {storage_cleared}")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        reset_screen_info = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                headerLocationLabel: locationLabel,
                storage: { ...localStorage }
            };
        }""")
        print(f"Screen after clean reset: {reset_screen_info}")
        report["clean_reset"] = reset_screen_info
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_05_clean_reset.png"))

        context.close()
        browser.close()

    print("\n--- B1 Verification JSON Summary ---")
    print(json.dumps(report, indent=2))
    with open(SCREENSHOT_DIR / "b1_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_b1_verification()
