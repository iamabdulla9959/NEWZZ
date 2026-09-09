import os
import sys
import re
import urllib.request
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "D:/News/apps/api")
sys.path.insert(0, "D:/News/apps/worker")

from app.db import SessionLocal
from app.models import Source, Article, StoryCluster, Card, CardSource
from worker.ingest import ingest_rss_source
from worker.llm import MultiProviderClient

db = SessionLocal()

# 1. Update PIB source classification
pib_src = db.query(Source).filter(Source.rss_url.like('%pib.gov.in%')).first()
if not pib_src:
    print("PIB source not found!")
    sys.exit(1)

print(f"Old PIB Source: name={pib_src.name}, cat={pib_src.category}, reg={pib_src.region}, tier={pib_src.trust_tier}, type={pib_src.source_type}")

pib_src.name = "Press Information Bureau - National Press Releases"
pib_src.category = "national"
pib_src.region = None
pib_src.trust_tier = "1"
pib_src.source_type = "rss"
db.commit()
print(f"Updated PIB Source: name={pib_src.name}, cat={pib_src.category}, reg={pib_src.region}, tier={pib_src.trust_tier}, type={pib_src.source_type}")

# 2. Delete existing PIB articles so they can be freshly re-ingested with full 10k scraping
pib_articles = db.query(Article).filter(Article.source_id == pib_src.id).all()
print(f"Found {len(pib_articles)} existing PIB articles to refresh.")
for art in pib_articles:
    # remove any card sources referencing this article
    db.query(CardSource).filter(CardSource.article_id == art.id).delete()
    db.delete(art)
db.commit()

# 3. Re-ingest PIB source
print("Re-ingesting PIB source...")
created = ingest_rss_source(db, pib_src, llm=None)
print(f"Re-ingested: {created} new articles")

# 4. Verify re-ingested articles
new_articles = db.query(Article).filter(Article.source_id == pib_src.id).all()
print(f"\nTotal re-ingested PIB articles in DB: {len(new_articles)}")
for i, art in enumerate(new_articles[:5], 1):
    print(f"\n=== ARTICLE {i} ===")
    print(f"TITLE: {art.title}")
    print(f"URL: {art.url}")
    print(f"LENGTH: {len(art.raw_text)} chars")
    print(f"FIRST 150 CHARS:\n{art.raw_text[:150]}")
    print(f"LAST 150 CHARS:\n{art.raw_text[-150:]}")

db.close()
