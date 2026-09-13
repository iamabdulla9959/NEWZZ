"""Insert example RSS sources across categories, including vernacular and official_local sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import Source, new_id

EXAMPLE_SOURCES = [
    {
        "name": "Reuters World",
        "category": "international",
        "region": None,
        "rss_url": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
        "trust_tier": "1",
    },
    {
        "name": "BBC World",
        "category": "international",
        "region": None,
        "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "trust_tier": "1",
    },
    {
        "name": "The Hindu National",
        "category": "national",
        "region": "IN",
        "rss_url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "trust_tier": "2",
    },
    {
        "name": "Hindustan Times India",
        "category": "national",
        "region": "IN",
        "rss_url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "trust_tier": "2",
    },
    {
        "name": "Times of India India",
        "category": "national",
        "region": "IN",
        "rss_url": "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
        "trust_tier": "2",
    },
    {
        "name": "The Hindu Tamil Nadu",
        "category": "state",
        "region": "Tamil Nadu",
        "rss_url": "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss",
        "trust_tier": "2",
    },
    {
        "name": "BBC Technology",
        "category": "tech",
        "region": None,
        "rss_url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "trust_tier": "2",
    },
    {
        "name": "TechCrunch",
        "category": "tech",
        "region": None,
        "rss_url": "https://techcrunch.com/feed/",
        "trust_tier": "2",
    },
    {
        "name": "The Verge",
        "category": "tech",
        "region": None,
        "rss_url": "https://www.theverge.com/rss/index.xml",
        "trust_tier": "2",
    },
    {
        "name": "ScienceDaily",
        "category": "science",
        "region": None,
        "rss_url": "https://www.sciencedaily.com/rss/top/science.xml",
        "trust_tier": "2",
    },
    {
        "name": "Nature News",
        "category": "science",
        "region": None,
        "rss_url": "https://www.nature.com/nature.rss",
        "trust_tier": "2",
    },
    # Vernacular network 1: Amar Ujala (Hindi district feed for Delhi)
    {
        "name": "Amar Ujala Delhi",
        "category": "district",
        "region": "Delhi",
        "district": "New Delhi",
        "rss_url": "https://www.amarujala.com/rss/delhi.xml",
        "trust_tier": "2",
    },
    # Vernacular network 2: OneIndia Tamil (Tamil regional feed)
    {
        "name": "OneIndia Tamil",
        "category": "state",
        "region": "Tamil Nadu",
        "rss_url": "https://tamil.oneindia.com/rss/tamil-news-fb.xml",
        "trust_tier": "2",
    },
    # Official local government press release source
    {
        "name": "District Administration Chennai - Official Press Releases",
        "category": "district",
        "region": "Chennai",
        "district": "Chennai",
        "rss_url": "https://chennai.nic.in/feed/",
        "trust_tier": "official_local",
        "source_type": "official_local",
    },
    # NewsData.io API-backed sources for non-local categories
    {
        "name": "NewsData.io India National",
        "category": "national",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "newsdata_api",
    },
    {
        "name": "NewsData.io Technology",
        "category": "tech",
        "region": None,
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "newsdata_api",
    },
    {
        "name": "NewsData.io Science",
        "category": "science",
        "region": None,
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "newsdata_api",
    },
    {
        "name": "Currents India Politics",
        "category": "politics",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "currents_api",
    },
    {
        "name": "Currents India Business",
        "category": "business",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "currents_api",
    },
    {
        "name": "Currents India Health",
        "category": "health",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "currents_api",
    },
    {
        "name": "Currents India Sports",
        "category": "sports",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "currents_api",
    },
    {
        "name": "Currents India Science",
        "category": "science",
        "region": "IN",
        "rss_url": None,
        "trust_tier": "2",
        "source_type": "currents_api",
    },
    {
        "name": "NPR News",
        "category": "international",
        "region": None,
        "rss_url": "https://feeds.npr.org/1001/rss.xml",
        "trust_tier": "1",
    },
    {
        "name": "Al Jazeera English",
        "category": "international",
        "region": None,
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "trust_tier": "1",
    },
    {
        "name": "LiveMint",
        "category": "business",
        "region": "IN",
        "rss_url": "https://www.livemint.com/rss/news",
        "trust_tier": "2",
    },
    {
        "name": "CNBC",
        "category": "business",
        "region": None,
        "rss_url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000&id=10000664",
        "trust_tier": "2",
    },
    {
        "name": "Financial Times",
        "category": "business",
        "region": None,
        "rss_url": "https://www.ft.com/?format=rss",
        "trust_tier": "1",
    },
    {
        "name": "Wired",
        "category": "tech",
        "region": None,
        "rss_url": "https://www.wired.com/feed/rss",
        "trust_tier": "2",
    },
    {
        "name": "Ars Technica",
        "category": "tech",
        "region": None,
        "rss_url": "https://feeds.arstechnica.com/arstechnica/index",
        "trust_tier": "2",
    },
    {
        "name": "ESPN",
        "category": "sports",
        "region": None,
        "rss_url": "https://www.espn.com/espn/rss/news",
        "trust_tier": "2",
    },
    {
        "name": "Sportskeeda",
        "category": "sports",
        "region": "IN",
        "rss_url": "https://www.sportskeeda.com/feed",
        "trust_tier": "2",
    },
    {
        "name": "The Guardian World",
        "category": "international",
        "region": None,
        "rss_url": "https://www.theguardian.com/world/rss",
        "trust_tier": "1",
    },
    {
        "name": "Washington Post",
        "category": "international",
        "region": "US",
        "rss_url": "https://feeds.washingtonpost.com/rss/world",
        "trust_tier": "1",
    },
    {
        "name": "NDTV Top Stories",
        "category": "national",
        "region": "IN",
        "rss_url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "trust_tier": "2",
    },
    {
        "name": "India Today",
        "category": "national",
        "region": "IN",
        "rss_url": "https://www.indiatoday.in/rss/home",
        "trust_tier": "2",
    },
    {
        "name": "NDTV Business",
        "category": "business",
        "region": "IN",
        "rss_url": "https://feeds.feedburner.com/ndtvprofit-latest",
        "trust_tier": "2",
    },
    {
        "name": "Economic Times",
        "category": "business",
        "region": "IN",
        "rss_url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        "trust_tier": "2",
    },
    {
        "name": "Gizmodo",
        "category": "tech",
        "region": None,
        "rss_url": "https://gizmodo.com/rss",
        "trust_tier": "2",
    },
    {
        "name": "Engadget",
        "category": "tech",
        "region": None,
        "rss_url": "https://www.engadget.com/rss.xml",
        "trust_tier": "2",
    },
    {
        "name": "Polygon",
        "category": "entertainment",
        "region": None,
        "rss_url": "https://www.polygon.com/rss/index.xml",
        "trust_tier": "2",
    },
    {
        "name": "IGN",
        "category": "entertainment",
        "region": None,
        "rss_url": "https://feeds.ign.com/ign/news",
        "trust_tier": "2",
    },
    {
        "name": "Variety",
        "category": "entertainment",
        "region": None,
        "rss_url": "https://variety.com/feed/",
        "trust_tier": "2",
    },
    {
        "name": "Google News India",
        "category": "national",
        "region": "IN",
        "rss_url": "India top news",
        "trust_tier": "1",
        "source_type": "serpapi",
    },
    {
        "name": "Google News World",
        "category": "international",
        "region": None,
        "rss_url": "World news",
        "trust_tier": "1",
        "source_type": "serpapi",
    },
    {
        "name": "Google News Technology",
        "category": "tech",
        "region": None,
        "rss_url": "Technology",
        "trust_tier": "1",
        "source_type": "serpapi",
    },
    {
        "name": "Google News Science",
        "category": "science",
        "region": None,
        "rss_url": "Science",
        "trust_tier": "1",
        "source_type": "serpapi",
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        for row in EXAMPLE_SOURCES:
            exists = db.query(Source).filter(Source.name == row["name"]).one_or_none()
            if exists:
                exists.trust_tier = str(row["trust_tier"])
                exists.category = row["category"]
                exists.region = row["region"]
                exists.rss_url = row["rss_url"]
                exists.source_type = row.get("source_type", "rss")
                continue
            db.add(Source(id=new_id(), is_active=True, **row))
        db.commit()
        count = db.query(Source).count()
        print(f"sources in db: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
