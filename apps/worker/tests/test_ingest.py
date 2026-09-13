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
