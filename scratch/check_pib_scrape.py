import urllib.request
import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

url = 'https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2307324'
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read()
    soup = BeautifulSoup(html, 'html.parser')
    c1 = soup.find("div", class_="ReleaseContent")
    c2 = soup.find("div", id="ReleaseContent")
    c3 = soup.find("article")
    print(f"c1: {c1 is not None}")
    print(f"c2: {c2 is not None}")
    print(f"c3: {c3 is not None}")
    print(f"soup.body: {soup.body is not None}")
    pdf_div = soup.find("div", id="PdfDiv")
    if pdf_div:
        txt = re.sub(r"\s+", " ", pdf_div.get_text(separator=" ", strip=True)).strip()
        print(f"PdfDiv text length: {len(txt)}")
        print("First 300 chars:")
        print(txt[:300])
        print("Last 300 chars:")
        print(txt[-300:])
