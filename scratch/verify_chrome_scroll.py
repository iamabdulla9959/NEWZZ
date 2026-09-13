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

def run_verification():
    results = {
        "chrome_path": CHROME_PATH,
        "chrome_exists": Path(CHROME_PATH).exists(),
        "console_messages": [],
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "tests": {}
    }

    print(f"Checking Chrome path: {CHROME_PATH} (exists: {results['chrome_exists']})")

    with sync_playwright() as p:
        print("Launching Chrome executable via Playwright...")
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True
        )

        # -------------------------------------------------------------
        # DESKTOP TEST (1440 x 900)
        # -------------------------------------------------------------
        print("\n--- Running Desktop Verification (1440x900) ---")
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()

        # Listeners
        page.on("console", lambda msg: results["console_messages"].append(f"[{msg.type}] {msg.text}") or (results["console_errors"].append(msg.text) if msg.type == "error" else None))
        page.on("pageerror", lambda err: results["page_errors"].append(str(err)))
        page.on("requestfailed", lambda req: results["failed_requests"].append(f"{req.method} {req.url}: {req.failure}"))

        # Step 4: Basic Connection
        resp = page.goto(BASE_URL, wait_until="networkidle")
        results["http_status"] = resp.status if resp else None
        results["page_title"] = page.title()
        print(f"Loaded {BASE_URL} -> Status: {results['http_status']}, Title: {results['page_title']}")

        # Clear localStorage to test onboarding
        print("Clearing localStorage to test fresh onboarding flow...")
        page.evaluate("localStorage.clear();")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Check welcome modal is displayed
        welcome_visible = page.evaluate("!document.getElementById('modal-welcome').classList.contains('hidden')")
        print(f"Welcome modal visible: {welcome_visible}")
        page.screenshot(path=str(SCREENSHOT_DIR / "chrome_01_welcome_desktop.png"))

        # Click Start Onboarding
        print("Clicking Start Onboarding...")
        page.click("#btn-welcome-start")
        time.sleep(0.5)

        # Check location modal
        location_visible = page.evaluate("!document.getElementById('modal-location').classList.contains('hidden')")
        print(f"Location modal visible: {location_visible}")

        # Save Location
        page.fill("#input-district", "Bengaluru")
        page.fill("#input-state", "Karnataka")
        page.click("#btn-save-location")
        time.sleep(0.5)

        # Check interests modal
        interests_visible = page.evaluate("!document.getElementById('modal-interests').classList.contains('hidden')")
        print(f"Interests modal visible: {interests_visible}")

        # Save Interests to complete onboarding
        page.click("#btn-save-interests")
        time.sleep(1.5)  # Wait for feed fetch

        # Verify reach News Reels feed
        cards_count = page.evaluate("document.querySelectorAll('.scroll-card').length")
        print(f"Loaded scroll feed with {cards_count} stories")
        results["feed_card_count"] = cards_count

        # Check Save button absence
        save_buttons = page.evaluate("document.querySelectorAll('[id*=\"save\"], [class*=\"save\"]').length")
        # Ensure specifically no Save in card actions or feed
        save_in_cards = page.evaluate("document.querySelectorAll('.scroll-card button:not([id^=\"btn-share\"]):not([id^=\"btn-detail\"])').length")
        save_btn_texts = page.evaluate("Array.from(document.querySelectorAll('.scroll-card button, .scroll-card a')).map(b => b.textContent.trim())")
        print(f"All action button texts in cards: {save_btn_texts[:10]}")
        has_save = any("save" in t.lower() for t in save_btn_texts)
        results["has_save_button"] = has_save
        print(f"Save button present in cards: {has_save}")

        # Get card data from DOM
        card_data = page.evaluate("""
            Array.from(document.querySelectorAll('.scroll-card')).map((c, i) => {
                const scoreText = c.querySelector('.scroll-score')?.textContent || '';
                const headline = c.querySelector('.scroll-headline')?.textContent || '';
                const summary = c.querySelector('.scroll-summary')?.textContent || '';
                const source = c.querySelector('.scroll-source')?.textContent || '';
                const category = c.querySelector('.badge-category')?.textContent || '';
                const readLink = c.querySelector('a.scroll-action-primary')?.href || '';
                const shareBtn = c.querySelector('button[id^="btn-share-"]')?.id || '';
                const detailBtn = c.querySelector('button[id^="btn-detail-"]')?.id || '';
                const rect = c.getBoundingClientRect();
                return {
                    index: i,
                    id: c.getAttribute('data-card-id'),
                    headline: headline.trim(),
                    scoreText: scoreText.trim(),
                    summary: summary.trim(),
                    source: source.trim(),
                    category: category.trim(),
                    readLink: readLink,
                    shareBtn: shareBtn,
                    detailBtn: detailBtn,
                    rect: { top: rect.top, height: rect.height, width: rect.width }
                };
            })
        """)
        results["card_data"] = card_data
        print(f"First story headline: '{card_data[0]['headline']}'")
        print(f"First story score: '{card_data[0]['scoreText']}'")
        print(f"First story readLink: '{card_data[0]['readLink']}'")

        page.screenshot(path=str(SCREENSHOT_DIR / "chrome_02_desktop_first_story.png"))

        # Step 6: Test Scrolling down card by card
        print("\nTesting scroll-down through stories...")
        scroll_indicator_history = []
        for i in range(min(5, len(card_data))):
            card_sel = f"#news-card-{card_data[i]['id']}"
            page.eval_on_selector(card_sel, "el => el.scrollIntoView({ behavior: 'smooth', block: 'start' })")
            time.sleep(0.8)
            current_ind = page.evaluate("document.querySelector('.scroll-current')?.textContent")
            scroll_indicator_history.append(current_ind)
            print(f"Scrolled to story {i+1} (ID: {card_data[i]['id']}) -> Indicator: {current_ind} / {cards_count}")
            page.screenshot(path=str(SCREENSHOT_DIR / f"chrome_03_story_{i+1}.png"))

        # Step 6: Test Scrolling back upward
        print("\nTesting scroll-back upward...")
        page.eval_on_selector(f"#news-card-{card_data[0]['id']}", "el => el.scrollIntoView({ behavior: 'smooth', block: 'start' })")
        time.sleep(1)
        indicator_back = page.evaluate("document.querySelector('.scroll-current')?.textContent")
        print(f"Scrolled back to top -> Indicator: {indicator_back}")
        results["scroll_back_indicator"] = indicator_back

        # Check ranking order preservation:
        # Extract numeric scores from scoreText like "Score 84.5"
        scores = []
        for c in card_data:
            txt = c['scoreText'].replace('Score', '').strip()
            try:
                scores.append(float(txt))
            except:
                pass
        is_sorted = scores == sorted(scores, reverse=True)
        print(f"Scores list: {scores} -> Preserved descending order: {is_sorted}")
        results["scores_descending"] = is_sorted

        # Check for duplicates & blanks
        headlines = [c['headline'] for c in card_data]
        has_duplicates = len(headlines) != len(set(headlines))
        has_blanks = any(len(c['headline']) == 0 for c in card_data)
        print(f"Has duplicate stories: {has_duplicates}, Has blank stories: {has_blanks}")
        results["has_duplicates"] = has_duplicates
        results["has_blanks"] = has_blanks

        # Step 7: Test Actions
        # 1. Share Button
        print("\nTesting Share button...")
        first_card = card_data[0]
        share_btn_id = f"#{first_card['shareBtn']}"
        page.click(share_btn_id)
        time.sleep(0.5)
        # Check button text after click (should be 'Link Copied!' on desktop where navigator.share is undefined)
        btn_text = page.evaluate(f"document.querySelector('{share_btn_id}').textContent")
        print(f"Share button text after click: '{btn_text.strip()}'")
        results["share_feedback"] = btn_text.strip()

        # 2. Analysis Button
        print("\nTesting Analysis button (Detail Modal)...")
        detail_btn_id = f"#{first_card['detailBtn']}"
        page.click(detail_btn_id)
        time.sleep(0.6)
        modal_detail_visible = page.evaluate("!document.getElementById('modal-story-detail').classList.contains('hidden')")
        modal_headline = page.evaluate("document.getElementById('detail-headline').textContent")
        print(f"Story detail modal visible: {modal_detail_visible}, headline: '{modal_headline.strip()}'")
        results["modal_detail_visible"] = modal_detail_visible
        page.screenshot(path=str(SCREENSHOT_DIR / "chrome_04_detail_modal.png"))

        # Close detail modal
        page.click("#btn-close-detail-modal")
        time.sleep(0.5)
        modal_detail_closed = page.evaluate("document.getElementById('modal-story-detail').classList.contains('hidden')")
        print(f"Story detail modal closed: {modal_detail_closed}")

        # 3. Read Full Story link
        print(f"\nChecking Read Full Story link for '{first_card['headline']}': {first_card['readLink']}")
        results["read_full_story_valid"] = first_card['readLink'].startswith("http")

        # Desktop layout metrics
        desktop_card_inner = page.evaluate("""() => {
            const inner = document.querySelector('.scroll-card-inner');
            const rect = inner.getBoundingClientRect();
            return {
                width: rect.width,
                height: rect.height,
                scrollWidth: inner.scrollWidth,
                scrollHeight: inner.scrollHeight
            };
        }""")
        results["desktop_card_inner"] = desktop_card_inner
        print(f"Desktop card inner: {desktop_card_inner}")

        context.close()

        # -------------------------------------------------------------
        # MOBILE-SIZED WEB VIEWPORT TEST (390 x 844)
        # -------------------------------------------------------------
        print("\n--- Running Mobile-Sized Viewport Verification (390x844) ---")
        m_context = browser.new_context(
            viewport={"width": 390, "height": 844}
        )
        m_page = m_context.new_page()

        m_page.on("console", lambda msg: results["console_messages"].append(f"[Mobile {msg.type}] {msg.text}") or (results["console_errors"].append(f"[Mobile] {msg.text}") if msg.type == "error" else None))
        m_page.on("pageerror", lambda err: results["page_errors"].append(f"[Mobile] {str(err)}"))

        m_page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(1)

        # Check if onboarding shows or feed shows (welcome was marked seen in previous step if localstorage persisted, but fresh context has separate storage)
        m_welcome = m_page.evaluate("!document.getElementById('modal-welcome').classList.contains('hidden')")
        if m_welcome:
            print("Completing onboarding on mobile context...")
            m_page.click("#btn-welcome-start")
            time.sleep(0.5)
            m_page.click("#btn-skip-location")
            time.sleep(0.5)
            m_page.click("#btn-save-interests")
            time.sleep(1.5)

        m_cards_count = m_page.evaluate("document.querySelectorAll('.scroll-card').length")
        print(f"Mobile feed loaded with {m_cards_count} cards")

        # Mobile horizontal overflow check
        m_overflow = m_page.evaluate("""
            () => {
                const doc = document.documentElement;
                const body = document.body;
                const container = document.getElementById('feed-container');
                return {
                    docScrollWidth: doc.scrollWidth,
                    docClientWidth: doc.clientWidth,
                    hasDocOverflow: doc.scrollWidth > doc.clientWidth,
                    containerScrollWidth: container.scrollWidth,
                    containerClientWidth: container.clientWidth,
                    hasContainerOverflow: container.scrollWidth > container.clientWidth
                };
            }
        """)
        print(f"Mobile overflow check: {m_overflow}")
        results["mobile_overflow"] = m_overflow

        # Mobile card layout check
        m_card_metrics = m_page.evaluate("""
            () => {
                const card = document.querySelector('.scroll-card');
                const inner = document.querySelector('.scroll-card-inner');
                const cRect = card.getBoundingClientRect();
                const iRect = inner.getBoundingClientRect();
                return {
                    cardWidth: cRect.width,
                    cardHeight: cRect.height,
                    innerWidth: iRect.width,
                    innerHeight: iRect.height,
                    actionsStacked: window.getComputedStyle(document.querySelector('.scroll-card-actions')).flexDirection
                };
            }
        """)
        print(f"Mobile card metrics: {m_card_metrics}")
        results["mobile_card_metrics"] = m_card_metrics

        m_page.screenshot(path=str(SCREENSHOT_DIR / "chrome_05_mobile_first_story.png"))

        # Test mobile scroll down to story 2
        print("Testing mobile scroll-down...")
        m_page.eval_on_selector(".scroll-card:nth-of-type(2)", "el => el.scrollIntoView({ behavior: 'smooth', block: 'start' })")
        time.sleep(1)
        m_indicator = m_page.evaluate("document.querySelector('.scroll-current')?.textContent")
        print(f"Mobile scroll position indicator: {m_indicator}")
        m_page.screenshot(path=str(SCREENSHOT_DIR / "chrome_06_mobile_second_story.png"))

        # Test mobile scroll back up
        m_page.eval_on_selector(".scroll-card:first-of-type", "el => el.scrollIntoView({ behavior: 'smooth', block: 'start' })")
        time.sleep(1)
        m_indicator_back = m_page.evaluate("document.querySelector('.scroll-current')?.textContent")
        print(f"Mobile scroll back indicator: {m_indicator_back}")

        m_context.close()
        browser.close()

    print("\n--- Summary of Verification Results ---")
    print(f"HTTP Status: {results.get('http_status')}")
    print(f"Page Title: {results.get('page_title')}")
    print(f"Cards Count: {results.get('feed_card_count')}")
    print(f"Save Button in Cards: {results.get('has_save_button')}")
    print(f"Scores Descending Order Preserved: {results.get('scores_descending')}")
    print(f"Has Duplicates: {results.get('has_duplicates')}")
    print(f"Has Blanks: {results.get('has_blanks')}")
    print(f"Console Errors: {results.get('console_errors')}")
    print(f"Page Errors: {results.get('page_errors')}")
    print(f"Failed Requests: {results.get('failed_requests')}")
    print("FINISHED")

    # Write results to json
    with open(SCREENSHOT_DIR / "verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_verification()
