import urllib.request
import json

BASE_URL = "http://localhost:8000"
DEVICE_ID = "test-device-qa-01"

def request(method, path, data=None):
    url = BASE_URL + path
    req = urllib.request.Request(url, method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode(), json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def test_flow():
    print("--- Phase 3, 4: GPS and Interests Persistence ---")
    prefs = {
        "category_order": ["national", "district", "politics", "tech"],
        "district": "TestDistrict",
        "state": "TestState",
        "is_gps": True
    }
    status, data = request("PUT", f"/user/{DEVICE_ID}/preferences", prefs)
    print("PUT /preferences status:", status)
    
    status, data = request("GET", f"/user/{DEVICE_ID}/preferences")
    print("GET /preferences:", data)
    assert data["category_order"] == prefs["category_order"]

    print("\n--- Phase 5, 6: Feed Ranking and Fallback ---")
    status, feed_data = request("GET", f"/feed?device_id={DEVICE_ID}")
    print("GET /feed status:", status)
    print("Total items:", len(feed_data.get("items", [])))
    if feed_data.get("items"):
        print("First 3 items categories:", [i["category"] for i in feed_data["items"][:3]])
    print("Fallback used:", feed_data.get("fallback_used"))
    print("Fallback level:", feed_data.get("fallback_level"))

    print("\n--- Test Fallback ---")
    request("PUT", f"/user/{DEVICE_ID}/preferences", {"category_order": ["district"]})
    status, f_data = request("GET", f"/feed?device_id={DEVICE_ID}&categories=district&district=EmptyDistrict&state=EmptyState")
    print("Fallback used:", f_data.get("fallback_used"))
    print("Fallback level:", f_data.get("fallback_level"))
    if f_data.get("items"):
        print("Items returned despite EmptyDistrict:", len(f_data["items"]))

if __name__ == "__main__":
    test_flow()
