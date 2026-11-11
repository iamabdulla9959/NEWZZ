from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from worker.ingest import ingest_rss_source
from app.models import Article, Source, new_id

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Gazette</title>
    <item>
      <title>Example Corp opens Exampleville plant</title>
      <link>https://example.invalid/example-corp-plant</link>
      <description>Example Corp opened a bicycle parts plant in Exampleville.</description>
    </item>
  </channel>
</rss>
"""


class FakeTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=RSS.encode("utf-8"))


def test_ingest_dedupes_on_url(db: Session):
    source = Source(
        id=new_id(),
        name="Example Gazette",
        category="national",
        region=None,
      district="Exampleville",
        rss_url="https://example.invalid/rss.xml",
        trust_tier=2,
        is_active=True,
    )
    db.add(source)
    db.commit()
    transport = FakeTransport()
    with httpx.Client(transport=transport) as client:
        first = ingest_rss_source(db, source, client=client)
        second = ingest_rss_source(db, source, client=client)
    assert first == 1
    assert second == 0
    article = db.query(Article).filter(Article.url == "https://example.invalid/example-corp-plant").one()
    assert article.district == "Exampleville"


def test_feed_failure_does_not_abort_batch_ingestion(db: Session):
    good_source = Source(
        id=new_id(),
        name="Good Feed",
        category="national",
        rss_url="https://good.example.invalid/rss.xml",
        trust_tier=2,
        is_active=True,
    )
    bad_source = Source(
        id=new_id(),
        name="Broken Feed",
        category="national",
        rss_url="https://bad.example.invalid/rss.xml",
        trust_tier=2,
        is_active=True,
    )
    db.add(good_source)
    db.add(bad_source)
    db.commit()


    GOOD_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Good Feed</title>
    <item>
      <title>Unique Story B38</title>
      <link>https://good.example.invalid/unique-story-b38</link>
      <description>Unique description for resilience test.</description>
    </item>
  </channel>
</rss>
"""
    class MixedTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            if "good.example.invalid" in str(request.url):
                return httpx.Response(200, content=GOOD_RSS.encode("utf-8"))
            return httpx.Response(500, content=b"Server Error")

    with httpx.Client(transport=MixedTransport()) as client:
        import pytest
        with pytest.raises(httpx.HTTPStatusError):
            ingest_rss_source(db, bad_source, client=client)

        good_created = ingest_rss_source(db, good_source, client=client)
        assert good_created == 1


def test_run_rss_once_records_worker_run(db: Session):
    from worker.main import run_rss_once
    from app.models import WorkerRun
    transport = FakeTransport()
    with httpx.Client(transport=transport) as client:
        run_rss_once(llm=None, http_client=client)
    latest = db.query(WorkerRun).filter(WorkerRun.provider == "rss_pipeline").order_by(WorkerRun.timestamp.desc()).first()
    assert latest is not None
    assert latest.duration_seconds is not None
