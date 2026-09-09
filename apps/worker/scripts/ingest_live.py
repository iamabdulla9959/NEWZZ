"""Poll three live RSS feeds into Article rows (deduped by URL)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))
load_dotenv(ROOT / ".env")

from app.db import SessionLocal  # noqa: E402
from app.models import Article, Source, new_id  # noqa: E402
from worker.ingest import ingest_rss_source  # noqa: E402

LIVE_FEEDS = [
    ("BBC World", "international", "https://feeds.bbci.co.uk/news/world/rss.xml", 1),
    ("BBC Technology", "tech", "https://feeds.bbci.co.uk/news/technology/rss.xml", 2),
    ("The Hindu National", "national", "https://www.thehindu.com/news/national/feeder/default.rss", 2),
]


def ensure_sources(db) -> list[Source]:
    rows: list[Source] = []
    for name, category, url, tier in LIVE_FEEDS:
        source = db.query(Source).filter(Source.name == name).one_or_none()
        if source is None:
            source = Source(
                id=new_id(),
                name=name,
                category=category,
                region="IN" if "Hindu" in name else None,
                rss_url=url,
                trust_tier=tier,
                is_active=True,
            )
            db.add(source)
            db.commit()
        rows.append(source)
    return rows


def main() -> None:
    db = SessionLocal()
    try:
        sources = ensure_sources(db)
        created = 0
        for source in sources:
            created += ingest_rss_source(db, source)
        before_second = db.query(Article).count()
        for source in sources:
            ingest_rss_source(db, source)
        after_second = db.query(Article).count()
        print(f"created={created} total={after_second} second_pass_delta={after_second - before_second}")
        if after_second == 0:
            raise SystemExit("ingest produced 0 rows")
        if after_second != before_second:
            raise SystemExit("dedupe failed: second pass created extra rows")
    finally:
        db.close()


if __name__ == "__main__":
    main()
