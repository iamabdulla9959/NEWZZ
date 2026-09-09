import urllib.request
import re
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

import sys
sys.stdout.reconfigure(encoding='utf-8')

import feedparser

for reg in [1, 3, 5, 6, 19, 20]:
    url = f"https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid={reg}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            feed = feedparser.parse(content)
            print(f"Regid={reg} (length={len(content)}): entries={len(feed.entries)}")
    except Exception as e:
        print(f"Regid={reg}: error={e}")
