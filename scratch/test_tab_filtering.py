from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8000')
    
    # Ensure onboarding is completed
    is_done = page.evaluate("() => localStorage.getItem('newsreels_onboarding_complete') === 'true'")
    if not is_done:
        page.evaluate("() => localStorage.setItem('newsreels_onboarding_complete', 'true')")
        page.reload()

    # Click tech tab with expect_response
    with page.expect_response(lambda r: '/feed' in r.url and 'category=technology' in r.url) as resp_info:
        page.click(".category-tab[data-category='technology']")
    data = resp_info.value.json()
    items = data.get('items', [])
    print('Tech click returned items:', len(items))
    print('Categories in response:', [i['category'] for i in items])
    page.wait_for_timeout(500)
    dom_cards = page.evaluate("() => document.querySelectorAll('.scroll-card').length")
    print('DOM cards rendered for Tech:', dom_cards)

    # Click All News tab with expect_response
    with page.expect_response(lambda r: '/feed' in r.url and 'category=' not in r.url) as resp_info:
        page.click(".category-tab[data-category='all']")
    data_all = resp_info.value.json()
    items_all = data_all.get('items', [])
    print('All News click returned items:', len(items_all))
    page.wait_for_timeout(500)
    dom_cards_all = page.evaluate("() => document.querySelectorAll('.scroll-card').length")
    print('DOM cards rendered for All News:', dom_cards_all)

    # Also test Politics tab (which has multiple stories)
    with page.expect_response(lambda r: '/feed' in r.url and 'category=politics' in r.url) as resp_info:
        page.click(".category-tab[data-category='politics']")
    data_pol = resp_info.value.json()
    items_pol = data_pol.get('items', [])
    print('Politics click returned items:', len(items_pol))
    print('Categories in response for Politics:', set(i['category'] for i in items_pol))
    page.wait_for_timeout(500)
    dom_cards_pol = page.evaluate("() => document.querySelectorAll('.scroll-card').length")
    print('DOM cards rendered for Politics:', dom_cards_pol)

    browser.close()
