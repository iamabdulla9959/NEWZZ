import urllib.request
import json

res = urllib.request.urlopen("http://127.0.0.1:8000/feed?limit=8")
data = json.loads(res.read().decode())
print(f"Retrieved {len(data.get('items', []))} items from /feed:")
for item in data.get("items", [])[:6]:
    hd = item.get("headline", "")[:40]
    img = item.get("image_url")
    author = item.get("image_author")
    cat = item.get("category")
    print(f"[{cat.upper()}] \"{hd}\"")
    if img:
        print(f"   -> Image: {img[:55]}... (by {author})")
    else:
        print("   -> [Typography Card - Sensitive/Stat]")
