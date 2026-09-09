"""End-to-end smoke: ingest → cluster → verify → summarize → validate → publish → feed."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))
load_dotenv(ROOT / ".env")

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Article, Source, StoryCluster, new_id  # noqa: E402
from worker.pipeline import (  # noqa: E402
    cluster_unassigned_articles,
    evaluate_cluster,
    process_eligible_clusters,
)


PASSING_SUMMARY = (
    "Example Corp opened a bicycle parts plant in Exampleville on Monday. "
    "The company said it will hire four hundred local workers this year. "
    "City officials said the first shift will start in June. "
    "Training for new hires begins next week at the site. "
    "The plant will make bicycle frames and wheels for regional shops."
)


class RecordedLLM:
    def complete_text(self, system: str, user: str) -> str:
        return PASSING_SUMMARY

    def complete_json(self, system: str, user: str):
        if "fact-consistency judge" in system.lower() or "consistent" in system.lower():
            hallucinated = "moon base" in user.lower()
            return {"consistent": not hallucinated, "issues": []}
        if "judge" in system.lower():
            return {"consistent": True, "issues": []}
        return {
            "headline": "Example Corp opens Exampleville plant",
            "summary": PASSING_SUMMARY,
            "category": "national",
            "key_facts": ["Example Corp opened a plant", "400 workers planned"],
            "conflicts": [],
        }


def seed_recorded_articles(db) -> None:
    urls = [
        "https://example.invalid/gazette/example-corp-plant",
        "https://example.invalid/herald/example-corp-factory",
    ]
    for a in db.query(Article).filter(Article.url.in_(urls)).all():
        db.delete(a)
    db.commit()
    gazette = Source(
        id=new_id(),
        name="Example Gazette",
        category="national",
        region="Example State",
        rss_url="https://example.invalid/gazette.xml",
        trust_tier="2",
        is_active=True,
    )
    herald = Source(
        id=new_id(),
        name="Example Herald",
        category="national",
        region="Example State",
        rss_url="https://example.invalid/herald.xml",
        trust_tier="2",
        is_active=True,
    )
    db.add_all([gazette, herald])
    db.flush()
    db.add_all(
        [
            Article(
                id=new_id(),
                source_id=gazette.id,
                url="https://example.invalid/gazette/example-corp-plant",
                title="Example Corp to open bicycle parts plant in Exampleville",
                raw_text=(
                    "Example Corp opened a bicycle parts plant in Exampleville on Monday. "
                    "The company said it will hire four hundred local workers this year. "
                    "City officials said the first shift will start in June."
                ),
                category="national",
                state="Example State",
                published_at=datetime.now(timezone.utc),
            ),
            Article(
                id=new_id(),
                source_id=herald.id,
                url="https://example.invalid/herald/example-corp-factory",
                title="New Example Corp factory coming to Exampleville",
                raw_text=(
                    "A new Example Corp factory in Exampleville will make bicycle parts. "
                    "Officials said hiring of 400 local workers begins with training next week. "
                    "The first shift starts in June."
                ),
                category="national",
                state="Example State",
                published_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_recorded_articles(db)
        cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)
        process_eligible_clusters(db, RecordedLLM())
    finally:
        db.close()

    client = TestClient(app)
    response = client.get("/feed", params={"categories": "national"})
    response.raise_for_status()
    body = response.json()
    published = [i for i in body["items"] if i["verified_status"] == "published"]
    if not published:
        raise SystemExit(f"e2e failed: no published cards in feed: {body}")
    print(f"e2e ok: published={len(published)} headline={published[0]['headline']}")


if __name__ == "__main__":
    main()
