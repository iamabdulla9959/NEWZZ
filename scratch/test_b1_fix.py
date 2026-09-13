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

def run_tests():
    report = {
        "test1_clean_launch": {},
        "test2_start_only": {},
        "test3_state": {},
        "test4_reload_mid_onboarding": {},
        "test5_complete_onboarding": {},
        "test6_reload_after_completion": {},
        "test7_clean_reset": {},
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

        # --- TEST 1: CLEAN FIRST LAUNCH ---
        print("\n--- TEST 1: Clean First Launch ---")
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.clear();")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        t1_state = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const districtInput = document.getElementById('input-district');
            const gpsBtn = document.getElementById('btn-detect-location');
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const storage = { ...localStorage };

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                hasDistrictInput: !!districtInput,
                hasGpsBtn: !!gpsBtn,
                feedCardsCount: feedCards,
                storage: storage,
                hasDistrictKey: 'newsreels_district' in storage
            };
        }""")
        print(f"Test 1 State: {t1_state}")
        report["test1_clean_launch"] = t1_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_01_clean_launch.png"))

        # --- TEST 2: START ONLY ---
        print("\n--- TEST 2: Start Only ---")
        page.click("#btn-welcome-start")
        time.sleep(0.5)

        t2_state = page.evaluate("""() => {
            const location = document.getElementById('modal-location');
            const storage = { ...localStorage };
            return {
                locationModalVisible: !location.classList.contains('hidden'),
                onboardingComplete: storage['newsreels_onboarding_complete'] === 'true',
                hasWelcomeSeen: 'newsreels_welcome_seen' in storage,
                storage: storage
            };
        }""")
        print(f"Test 2 State: {t2_state}")
        report["test2_start_only"] = t2_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_02_start_only.png"))

        # --- TEST 3: STATE SELECTION ---
        print("\n--- TEST 3: State Selection ---")
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        time.sleep(0.5)

        t3_state = page.evaluate("""() => {
            const interests = document.getElementById('modal-interests');
            const storage = { ...localStorage };
            return {
                interestsModalVisible: !interests.classList.contains('hidden'),
                storedState: storage['newsreels_state'],
                hasDistrictKey: 'newsreels_district' in storage,
                onboardingComplete: storage['newsreels_onboarding_complete'] === 'true',
                storage: storage
            };
        }""")
        print(f"Test 3 State: {t3_state}")
        report["test3_state"] = t3_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_03_state_selected.png"))

        # --- TEST 4: RELOAD MID-ONBOARDING ---
        print("\n--- TEST 4: Reload Mid-Onboarding ---")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        t4_state = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const storage = { ...localStorage };

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                feedCardsCount: feedCards,
                onboardingComplete: storage['newsreels_onboarding_complete'] === 'true',
                storedState: storage['newsreels_state']
            };
        }""")
        print(f"Test 4 State: {t4_state}")
        report["test4_reload_mid_onboarding"] = t4_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_04_mid_onboarding_reload.png"))

        # --- TEST 5: COMPLETE ONBOARDING ---
        print("\n--- TEST 5: Complete Onboarding ---")
        # Proceed from welcome to state to interests
        page.click("#btn-welcome-start")
        time.sleep(0.5)
        # Verify state is prefilled
        prefilled_state = page.input_value("#input-state")
        print(f"Prefilled state on resume: '{prefilled_state}'")
        page.click("#btn-save-location")
        time.sleep(0.5)
        # On interests modal, click Save Preferences (complete onboarding)
        page.click("#btn-save-interests")
        time.sleep(1.5)  # wait for feed fetch

        t5_state = page.evaluate("""() => {
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const storage = { ...localStorage };
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');

            return {
                feedCardsCount: feedCards,
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                onboardingComplete: storage['newsreels_onboarding_complete'] === 'true',
                storedState: storage['newsreels_state'],
                hasInterests: 'newsreels_interests' in storage,
                storage: storage
            };
        }""")
        print(f"Test 5 State: {t5_state}")
        report["test5_complete_onboarding"] = t5_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_05_completed_feed.png"))

        # Check ranking order
        card_scores = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.scroll-card .scroll-score')).map(s => {
                const txt = s.textContent.replace('Score', '').trim();
                return parseFloat(txt);
            });
        }""")
        scores_descending = card_scores == sorted(card_scores, reverse=True)
        print(f"Feed card scores ({len(card_scores)}): {card_scores[:5]}... Descending: {scores_descending}")
        report["test5_complete_onboarding"]["scores_descending"] = scores_descending

        # --- TEST 6: RELOAD AFTER COMPLETION ---
        print("\n--- TEST 6: Reload After Completion ---")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        t6_state = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();
            const storage = { ...localStorage };

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                feedCardsCount: feedCards,
                locationLabel: locationLabel,
                onboardingComplete: storage['newsreels_onboarding_complete'] === 'true',
                storage: storage
            };
        }""")
        print(f"Test 6 State: {t6_state}")
        report["test6_reload_after_completion"] = t6_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_06_post_completion_reload.png"))

        # --- TEST 7: CLEAN RESET ---
        print("\n--- TEST 7: Clean Reset ---")
        page.evaluate("localStorage.clear();")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        t7_state = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();
            const storage = { ...localStorage };

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                feedCardsCount: feedCards,
                locationLabel: locationLabel,
                storage: storage,
                hasDistrictKey: 'newsreels_district' in storage,
                hasStateKey: 'newsreels_state' in storage,
                hasInterestsKey: 'newsreels_interests' in storage,
                hasCompletionKey: 'newsreels_onboarding_complete' in storage
            };
        }""")
        print(f"Test 7 State: {t7_state}")
        report["test7_clean_reset"] = t7_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b1_fix_07_clean_reset.png"))

        context.close()
        browser.close()

    print("\n--- Summary of All Tests ---")
    print(f"Console errors: {report['diagnostics']['console_errors']}")
    print(f"Page errors: {report['diagnostics']['page_errors']}")
    print(f"Failed requests: {report['diagnostics']['failed_requests']}")

    with open(SCREENSHOT_DIR / "b1_fix_verification.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_tests()
