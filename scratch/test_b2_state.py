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

def run_b2_verification():
    report = {
        "test1_clean_user": {},
        "test2_reload": {},
        "test3_api_request": {},
        "test4_feed_distribution": {},
        "test5_change_state": {},
        "test6_gps_district_regression": {},
        "test7_consistency": {},
        "test8_empty_state": {},
        "diagnostics": {
            "console_errors": [],
            "page_errors": [],
            "failed_requests": [],
            "geolocation_requested": False
        }
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Listeners
        feed_requests = []
        feed_responses = []

        def handle_request(req):
            if "/feed" in req.url:
                feed_requests.append(req.url)

        def handle_response(resp):
            if "/feed" in resp.url and resp.status == 200:
                try:
                    feed_responses.append(resp.json())
                except:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)
        page.on("console", lambda msg: report["diagnostics"]["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: report["diagnostics"]["page_errors"].append(str(err)))
        page.on("requestfailed", lambda req: report["diagnostics"]["failed_requests"].append(f"{req.method} {req.url}: {req.failure}"))

        # --- TEST 1: CLEAN USER ---
        print("\n--- TEST 1: Clean User ---")
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.clear();")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Onboarding flow: Start Reading -> State (Karnataka) -> Save -> Interests -> Save
        page.click("#btn-welcome-start")
        time.sleep(0.5)
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        time.sleep(0.5)

        feed_requests.clear()
        feed_responses.clear()
        page.click("#btn-save-interests")
        time.sleep(1.5)  # Wait for feed request and render

        t1_storage = page.evaluate("() => ({ ...localStorage })")
        print(f"Test 1 Storage: {t1_storage}")
        report["test1_clean_user"] = {
            "stored_state": t1_storage.get("newsreels_state"),
            "has_district": "newsreels_district" in t1_storage,
            "onboarding_complete": t1_storage.get("newsreels_onboarding_complete") == "true"
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b2_01_clean_user_karnataka.png"))

        # --- TEST 2: RELOAD ---
        print("\n--- TEST 2: Reload ---")
        feed_requests.clear()
        feed_responses.clear()
        page.reload(wait_until="networkidle")
        time.sleep(1.5)

        t2_state = page.evaluate("""() => {
            const welcome = document.getElementById('modal-welcome');
            const location = document.getElementById('modal-location');
            const interests = document.getElementById('modal-interests');
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();
            const storage = { ...localStorage };

            return {
                storedState: storage['newsreels_state'],
                headerLocation: locationLabel,
                welcomeVisible: !welcome.classList.contains('hidden'),
                locationVisible: !location.classList.contains('hidden'),
                interestsVisible: !interests.classList.contains('hidden'),
                feedCardsCount: feedCards
            };
        }""")
        print(f"Test 2 State: {t2_state}")
        report["test2_reload"] = t2_state
        page.screenshot(path=str(SCREENSHOT_DIR / "b2_02_reload_karnataka.png"))

        # --- TEST 3: API REQUEST ---
        print("\n--- TEST 3: API Request ---")
        last_feed_url = feed_requests[-1] if feed_requests else ""
        print(f"Captured /feed request URL: {last_feed_url}")
        parsed_url = urlparse(last_feed_url)
        params = parse_qs(parsed_url.query)
        state_param = params.get("state", [None])[0]
        print(f"State query param: '{state_param}'")
        report["test3_api_request"] = {
            "url": last_feed_url,
            "has_state_param": "state" in params,
            "state_param_value": state_param,
            "params": {k: v[0] for k, v in params.items()}
        }

        # --- TEST 4: FEED STATE DISTRIBUTION ---
        print("\n--- TEST 4: Feed State Distribution ---")
        # Inspect cards returned in the feed response
        last_resp = feed_responses[-1] if feed_responses else {}
        items = last_resp if isinstance(last_resp, list) else last_resp.get("items", last_resp.get("cards", []))
        print(f"Total stories returned from API: {len(items)}")

        karnataka_count = 0
        other_state_count = 0
        national_neutral_count = 0
        unknown_state_count = 0
        state_breakdown = {}

        for it in items:
            st = it.get("state")
            cat = it.get("category", "")
            if st:
                st_clean = st.strip()
                state_breakdown[st_clean] = state_breakdown.get(st_clean, 0) + 1
                if st_clean.lower() == "karnataka":
                    karnataka_count += 1
                else:
                    other_state_count += 1
            else:
                if cat.lower() in ["national", "world", "technology", "business", "politics", "science", "sports", "entertainment"]:
                    national_neutral_count += 1
                else:
                    unknown_state_count += 1

        print(f"State breakdown: {state_breakdown}")
        print(f"Karnataka: {karnataka_count}, Other states: {other_state_count}, National/Neutral: {national_neutral_count}, Unknown: {unknown_state_count}")
        report["test4_feed_distribution"] = {
            "total_stories": len(items),
            "karnataka_stories": karnataka_count,
            "other_state_stories": other_state_count,
            "national_neutral_stories": national_neutral_count,
            "unknown_state_stories": unknown_state_count,
            "state_breakdown": state_breakdown
        }

        # --- TEST 5: CHANGE STATE ---
        print("\n--- TEST 5: Change State ---")
        # Click header location chip
        page.click("#btn-open-location-modal")
        time.sleep(0.5)

        # Check prefilled value
        prefilled = page.input_value("#input-state")
        print(f"Prefilled state before change: '{prefilled}'")

        # Fill Andhra Pradesh and save
        page.fill("#input-state", "Andhra Pradesh")
        feed_requests.clear()
        feed_responses.clear()
        page.click("#btn-save-location")
        time.sleep(1.5)

        t5_storage = page.evaluate("() => ({ ...localStorage })")
        t5_header = page.evaluate("() => document.getElementById('label-user-location')?.textContent?.trim()")
        last_feed_url_ap = feed_requests[-1] if feed_requests else ""
        params_ap = parse_qs(urlparse(last_feed_url_ap).query)
        state_param_ap = params_ap.get("state", [None])[0]

        print(f"After change storage state: '{t5_storage.get('newsreels_state')}'")
        print(f"After change header label: '{t5_header}'")
        print(f"After change feed URL: '{last_feed_url_ap}'")
        print(f"After change state param: '{state_param_ap}'")

        report["test5_change_state"] = {
            "old_state": "Karnataka",
            "new_state": "Andhra Pradesh",
            "stored_state": t5_storage.get("newsreels_state"),
            "header_label": t5_header,
            "feed_request_url": last_feed_url_ap,
            "feed_state_param": state_param_ap
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b2_03_change_state_ap.png"))

        # --- TEST 6: STATE CHANGE MUST NOT REQUIRE GPS ---
        print("\n--- TEST 6: State Change Must Not Require GPS ---")
        t6_check = page.evaluate("""() => {
            const districtInput = document.getElementById('input-district');
            const gpsBtn = document.getElementById('btn-detect-location');
            const storage = { ...localStorage };
            const hasGpsKeys = Object.keys(storage).some(k => k.includes('gps') || k.includes('lat') || k.includes('coord') || k.includes('district'));

            return {
                hasDistrictInput: !!districtInput,
                hasGpsBtn: !!gpsBtn,
                hasGpsStorageKeys: hasGpsKeys,
                storageKeys: Object.keys(storage)
            };
        }""")
        print(f"Test 6 Check: {t6_check}")
        report["test6_gps_district_regression"] = t6_check

        # --- TEST 7: STATE PREFERENCE CONSISTENCY ---
        print("\n--- TEST 7: State Preference Consistency ---")
        consistent = (
            t5_storage.get("newsreels_state") == "Andhra Pradesh" and
            t5_header == "Andhra Pradesh" and
            state_param_ap == "Andhra Pradesh"
        )
        print(f"Consistency check: storage='{t5_storage.get('newsreels_state')}', header='{t5_header}', api='{state_param_ap}' -> Match: {consistent}")
        report["test7_consistency"] = {
            "localStorage_state": t5_storage.get("newsreels_state"),
            "header_state": t5_header,
            "feed_param_state": state_param_ap,
            "is_consistent": consistent
        }

        # --- TEST 8: EMPTY / DEFAULT STATE ---
        print("\n--- TEST 8: Empty / Default State ---")
        page.evaluate("localStorage.clear();")
        feed_requests.clear()
        feed_responses.clear()
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Start Reading
        page.click("#btn-welcome-start")
        time.sleep(0.5)

        # Click Skip on Location Modal
        print("Clicking Skip on State selection modal...")
        page.click("#btn-skip-location")
        time.sleep(0.5)

        # Complete Interests
        page.click("#btn-save-interests")
        time.sleep(1.5)

        t8_state = page.evaluate("""() => {
            const feedCards = document.querySelectorAll('.scroll-card').length;
            const locationLabel = document.getElementById('label-user-location')?.textContent?.trim();
            const storage = { ...localStorage };
            const welcome = document.getElementById('modal-welcome');

            return {
                welcomeVisible: !welcome.classList.contains('hidden'),
                feedCardsCount: feedCards,
                locationLabel: locationLabel,
                storage: storage,
                hasStateKey: 'newsreels_state' in storage,
                storedState: storage['newsreels_state'] || null
            };
        }""")

        last_feed_url_empty = feed_requests[-1] if feed_requests else ""
        params_empty = parse_qs(urlparse(last_feed_url_empty).query)
        state_param_empty = params_empty.get("state", [None])[0]

        print(f"Test 8 State: {t8_state}")
        print(f"Empty state feed URL: '{last_feed_url_empty}' (state param: '{state_param_empty}')")
        report["test8_empty_state"] = {
            "state_behavior": "Neutral/default feed supported without mandatory state",
            "feedCardsCount": t8_state["feedCardsCount"],
            "headerLabel": t8_state["locationLabel"],
            "hasStateKey": t8_state["hasStateKey"],
            "storedState": t8_state["storedState"],
            "feedStateParam": state_param_empty,
            "storage": t8_state["storage"]
        }
        page.screenshot(path=str(SCREENSHOT_DIR / "b2_04_empty_state_feed.png"))

        context.close()
        browser.close()

    print("\n--- Summary of All B2 Tests ---")
    print(f"Console errors: {report['diagnostics']['console_errors']}")
    print(f"Page errors: {report['diagnostics']['page_errors']}")
    print(f"Failed requests: {report['diagnostics']['failed_requests']}")

    with open(SCREENSHOT_DIR / "b2_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_b2_verification()
