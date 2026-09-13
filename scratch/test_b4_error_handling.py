import sys
sys.path.insert(0, r"d:\News")
sys.path.insert(0, r"d:\News\apps\api")
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"

def test_api_failure_handling():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        page = browser.new_page()

        page.goto(BASE_URL)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        # Step through onboarding to Priority modal
        page.click("#btn-welcome-start")
        page.wait_for_timeout(200)
        page.fill("#input-state", "Telangana")
        page.click("#btn-save-location")
        page.wait_for_timeout(200)
        page.click("#btn-save-interests")
        page.wait_for_timeout(200)

        # Mock API failure for PUT /user/*/preferences
        page.route("**/user/*/preferences", lambda route: route.abort("failed"))

        # Click save priority
        page.click("#btn-save-priority")
        page.wait_for_timeout(500)

        # Check that error banner is visible
        error_banner_vis = page.is_visible("#priority-error-banner")
        error_text = page.inner_text("#priority-error-msg")
        onboarding_done = page.evaluate("() => localStorage.getItem('newsreels_onboarding_complete')")
        priority_modal_vis = page.is_visible("#modal-priority")

        print(f"Error banner visible: {error_banner_vis}")
        print(f"Error message: {error_text}")
        print(f"Priority modal still visible: {priority_modal_vis}")
        print(f"Onboarding complete in localStorage: {onboarding_done}")

        assert error_banner_vis, "Error banner must be shown on backend sync failure"
        assert priority_modal_vis, "Priority modal must remain open so user can retry"
        assert onboarding_done is None, "Onboarding must NOT be marked complete when backend sync fails"

        browser.close()
        print("API FAILURE HANDLING TEST PASSED!")

if __name__ == "__main__":
    test_api_failure_handling()
