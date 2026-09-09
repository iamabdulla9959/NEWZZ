from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session

from app.models import Article, Source, new_id
from worker.ingest import process_and_translate_text
from worker.llm import LLMClient

logger = logging.getLogger("newsreels.serpapi")

SERPAPI_URL = "https://serpapi.com/search"

# SerpApi allows 100 queries a month on the free plan.
# We limit to 8 queries per day = 240/month.
# A file-based lock/state or DB state could be used, but since we are scheduling
# exactly twice a day with 4 queries each, it inherently respects the limit.

def ingest_serpapi_source(
    db: Session,
    source: Source,
    api_key: str,
    query: str,
    llm: LLMClient | None = None,
) -> tuple[int, list[str]]:
    """
    Queries SerpApi Google News engine for a given query and ingests articles.
    Returns: (articles_created, errors)
    """
    errors: list[str] = []
    created = 0

    if not api_key:
        return 0, ["SERPAPI_KEY not provided."]

    params = {
        "engine": "google_news",
        "q": query,
        "api_key": api_key,
        "gl": "in",
        "hl": "en",
    }

    try:
        # Give it a higher timeout because SerpApi can be slow (default httpx is 5s)
        response = httpx.get(SERPAPI_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        err_msg = f"SerpApi request failed for query '{query}': {exc}"
        logger.error(err_msg)
        errors.append(err_msg)
        return 0, errors

    news_results = data.get("news_results", [])
    
    now = datetime.now(timezone.utc)

    for item in news_results:
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        
        if not url or not title:
            continue

        # De-duplicate by URL
        if db.query(Article).filter(Article.url == url).one_or_none():
            continue

        # Google News snippets can act as description/content
        snippet = (item.get("snippet") or "").strip()
        raw_content = snippet or title

        # Process text
        raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
            title=title,
            raw_text=raw_content,
            llm=llm,
        )
        translated_text = raw_for_clustering if orig_lang != "en" else None
        
        from worker.verify import extract_wire_attribution
        wire = extract_wire_attribution(f"{title} {raw_content}")

        db.add(
            Article(
                id=new_id(),
                source_id=source.id,
                url=url,
                title=title[:1024],
                raw_text=raw_for_clustering,
                original_text=original_text,
                translated_text=translated_text,
                original_language=orig_lang,
                translation_confidence=conf,
                category=source.category,
                state=source.region,
                district=None,
                published_at=now,  # Fallback to now for scraped news to keep it fresh
                wire_attribution=wire,
            )
        )
        created += 1

    if created > 0:
        db.commit()

    return created, errors


def poll_serpapi_sources(
    db: Session,
    api_key: str | None = None,
    llm: LLMClient | None = None,
) -> tuple[int, int, list[str]]:
    """
    Polls SerpApi for the defined active SerpApi sources.
    Returns: (sources_polled, articles_created, errors)
    """
    errors: list[str] = []
    total_created = 0

    key = api_key or os.getenv("SERPAPI_KEY", "").strip()
    if not key:
        return 0, 0, ["SERPAPI_KEY not configured."]

    sources = (
        db.query(Source)
        .filter(Source.is_active.is_(True), Source.source_type == "serpapi")
        .all()
    )

    polled = 0
    for source in sources:
        # We assume the `rss_url` field holds the query (e.g. "India top news")
        query = source.rss_url
        if not query:
            continue

        polled += 1
        created, src_errors = ingest_serpapi_source(
            db=db,
            source=source,
            api_key=key,
            query=query,
            llm=llm
        )
        total_created += created
        errors.extend(src_errors)
        
        # Rate limit compliance: SerpApi doesn't strictly need spacing, but it's polite
        time.sleep(1)

    return polled, total_created, errors
