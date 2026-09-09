import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.db import SessionLocal
from app.models import Source, new_id

new_sources = [
    # Politics
    ("NPR Politics", "politics", "https://feeds.npr.org/1014/rss.xml", "rss", 2),
    ("BBC Politics", "politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "rss", 2),
    # Health
    ("NPR Health", "health", "https://feeds.npr.org/1128/rss.xml", "rss", 2),
    ("ScienceDaily Health", "health", "https://www.sciencedaily.com/rss/health_medicine.xml", "rss", 2),
    # Education
    ("NPR Education", "education", "https://feeds.npr.org/1013/rss.xml", "rss", 2),
    ("BBC Education", "education", "https://feeds.bbci.co.uk/news/education/rss.xml", "rss", 2),
    # Business
    ("BBC Business", "business", "https://feeds.bbci.co.uk/news/business/rss.xml", "rss", 2),
]

def seed_categories():
    db = SessionLocal()
    for name, category, url, stype, trust in new_sources:
        exists = db.query(Source).filter(Source.rss_url == url).first()
        if not exists:
            s = Source(
                id=new_id(),
                name=name,
                category=category,
                rss_url=url,
                source_type=stype,
                trust_tier=trust,
                is_active=True
            )
            db.add(s)
            print(f"Added {name} for {category}")
    db.commit()
    db.close()
    print("Done seeding new sources.")

if __name__ == "__main__":
    seed_categories()
