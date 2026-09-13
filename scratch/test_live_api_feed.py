import sys
sys.path.insert(0, r"d:\News")
import json
import urllib.request
import urllib.parse

BASE_URL = "http://127.0.0.1:8000"

def put_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())

def get_json(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())

def test_api_feed():
    dev_a = "test-device-audit-order-a"
    dev_b = "test-device-audit-order-b"

    # Order A: technology > politics > business > national
    order_a = ["technology", "business", "politics", "national"]
    s_a, r_a = put_json(f"{BASE_URL}/user/{dev_a}/preferences", {"category_order": order_a})
    print(f"Put dev_a preferences status: {s_a}, response: {r_a}")

    # Order B: politics > technology > business > national
    order_b = ["politics", "technology", "business", "national"]
    s_b, r_b = put_json(f"{BASE_URL}/user/{dev_b}/preferences", {"category_order": order_b})
    print(f"Put dev_b preferences status: {s_b}, response: {r_b}")

    # Fetch feed for dev_a and dev_b
    feed_a = get_json(f"{BASE_URL}/feed?device_id={dev_a}&limit=30")
    feed_b = get_json(f"{BASE_URL}/feed?device_id={dev_b}&limit=30")

    cards_a = feed_a if isinstance(feed_a, list) else feed_a.get("items", [])
    cards_b = feed_b if isinstance(feed_b, list) else feed_b.get("items", [])

    print(f"Feed A total items: {len(cards_a)}")
    print(f"Feed B total items: {len(cards_b)}")

    # Compare cards for politics and technology stories
    pol_story_a = next((c for c in cards_a if c.get("category") == "politics"), None)
    pol_story_b = next((c for c in cards_b if c.get("category") == "politics"), None)

    if pol_story_a and pol_story_b:
        print(f"Politics story headline: {pol_story_a.get('headline')}")
        print(f"Order A (Rank 3) relevance: {pol_story_a.get('personal_relevance_score')}, final score: {pol_story_a.get('final_feed_score')}")
        print(f"Order B (Rank 1) relevance: {pol_story_b.get('personal_relevance_score')}, final score: {pol_story_b.get('final_feed_score')}")
        print(f"Importance Order A: {pol_story_a.get('importance_score')}, Order B: {pol_story_b.get('importance_score')}")
        print(f"Urgency Order A: {pol_story_a.get('urgency_score')}, Order B: {pol_story_b.get('urgency_score')}")
        print(f"Freshness Order A: {pol_story_a.get('freshness_score')}, Order B: {pol_story_b.get('freshness_score')}")
        print(f"Verification Order A: {pol_story_a.get('verification_score')}, Order B: {pol_story_b.get('verification_score')}")

    # Now compare with what the browser user gets!
    dev_browser = "dev_epiyobjfp_1789287387405"
    feed_browser = get_json(f"{BASE_URL}/feed?device_id={dev_browser}&limit=30")
    cards_browser = feed_browser if isinstance(feed_browser, list) else feed_browser.get("items", [])
    pol_browser = next((c for c in cards_browser if c.get("category") == "politics"), None)
    if pol_browser:
        print(f"Browser User (who configured priority in web UI) relevance: {pol_browser.get('personal_relevance_score')}")

if __name__ == "__main__":
    test_api_feed()
