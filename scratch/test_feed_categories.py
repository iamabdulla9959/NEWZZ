import urllib.request
import json

base_url = "http://127.0.0.1:8000"

# 1. Check all categories
categories = [
    "all", "state", "national", "politics", "business",
    "technology", "world", "science", "health", "sports",
    "entertainment", "environment"
]

print("=== CATEGORY QUERY TESTS ===")
for cat in categories:
    url = f"{base_url}/feed?limit=50" if cat == "all" else f"{base_url}/feed?category={cat}&limit=50"
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode("utf-8"))
    print(f"Category: {cat:15} -> Returned: {len(data['items']):2} | Total: {data['total']:3}")

# 2. Check state queries
print("\n=== STATE QUERY TESTS ===")
states = ["Assam", "Bihar", "Karnataka", "Kerala", "Maharashtra", "Tamil Nadu", "Delhi", "Goa"]
for st in states:
    # Query state tab with user state
    url = f"{base_url}/feed?category=state&state={urllib.parse.quote(st)}&limit=50"
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode("utf-8"))
    print(f"State: {st:15} (tab=state) -> Returned: {len(data['items']):2} | Total: {data['total']:3}")
