import threading
import pytest
from sqlalchemy.orm import Session
from app.models import Article, Source, new_id
from worker.ingest import normalize_article_url, ingest_rss_source
import httpx


def test_url_normalization_rules():
    # 1. Lowercase scheme and domain, strip fragment
    u1 = "HTTPS://WWW.TheHindu.COM/News/National/story1.html#comments"
    assert normalize_article_url(u1) == "https://www.thehindu.com/News/National/story1.html"

    # 2. Strips common marketing/analytics tracking query parameters
    u2 = "https://example.com/article?utm_source=twitter&utm_medium=social&utm_campaign=breaking&id=12345&fbclid=IwAR123"
    assert normalize_article_url(u2) == "https://example.com/article?id=12345"

    # 3. Preserves essential query parameters and sorts deterministically
    u3a = "https://example.com/news?page=2&story_id=987&category=politics"
    u3b = "https://example.com/news?category=politics&page=2&story_id=987"
    assert normalize_article_url(u3a) == "https://example.com/news?category=politics&page=2&story_id=987"
    assert normalize_article_url(u3a) == normalize_article_url(u3b)

    # 4. Strips trailing slash on non-root paths
    u4 = "https://example.com/news/india/"
    assert normalize_article_url(u4) == "https://example.com/news/india"

    # 5. Preserves root slash
    u5 = "https://example.com/"
    assert normalize_article_url(u5) == "https://example.com/"


def test_concurrent_duplicate_article_ingestion(db: Session, monkeypatch):
    """Concurrency test: two independent threads attempt to insert the same article URL simultaneously.
    
    Verifies:
    - Exactly 1 Article record stored.
    - No duplicate Article rows.
    - No partial transaction corruptions.
    - Graceful conflict-safe savepoint handling without crash.
    """
    src = Source(id=new_id(), name="PTI Wire", category="national", trust_tier="1", is_active=True, rss_url="https://mock.example/rss")
    db.add(src)
    db.commit()

    test_url = "https://example.com/exclusive-report-2026?utm_source=feed"
    normalized_url = normalize_article_url(test_url)

    mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>PTI News</title>
        <item>
          <title>Exclusive National Report</title>
          <link>{test_url}</link>
          <description>Significant news event reported exclusively by the national wire.</description>
          <pubDate>Wed, 31 Oct 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    class MockTransport(httpx.BaseTransport):
        def handle_request(self, request):
            return httpx.Response(200, content=mock_xml.encode("utf-8"), request=request)

    errors = []
    inserted_counts = []

    src_id = src.id

    def worker_insert():
        from app.db import SessionLocal
        local_db = SessionLocal()
        try:
            local_src = local_db.query(Source).filter(Source.id == src_id).first()
            client = httpx.Client(transport=MockTransport())
            created = ingest_rss_source(local_db, local_src, client=client)
            inserted_counts.append(created)
        except Exception as exc:
            errors.append(exc)
        finally:
            local_db.close()

    t1 = threading.Thread(target=worker_insert)
    t2 = threading.Thread(target=worker_insert)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Zero unhandled exceptions
    assert len(errors) == 0

    # Total articles in database with this URL must be strictly 1
    articles = db.query(Article).filter(Article.url == normalized_url).all()
    assert len(articles) == 1
    assert articles[0].title == "Exclusive National Report"

    # Exactly one thread succeeded in inserting; the other was skipped or caught via conflict savepoint
    assert sum(inserted_counts) == 1
