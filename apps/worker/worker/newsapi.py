"""NewsAPI.org Integration — FOR DEV / TESTING USE ONLY.

================================================================================
TERMS OF SERVICE NOTICE — STRICTLY FORBIDDEN IN PRODUCTION / COMMERCIAL USE
================================================================================
NewsAPI.org's Developer (free) tier explicitly forbids production and commercial
usage per its developer terms:
"You may not use the API for any commercial purpose or in any production application
on the free tier." (https://newsapi.org/pricing)

This integration exists exclusively for offline development, integration testing,
and evaluating clustering/verification performance against wider source variety.
It must NEVER be scheduled or enabled in any deployed, staging, or production
environment.
================================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Source, WorkerRun, new_id
from worker.ingest import parse_datetime, process_and_translate_text
from worker.llm import LLMClient

logger = logging.getLogger("newsreels.newsapi")

NEWSAPI_TOP_HEADLINES_URL: str = "https://newsapi.org/v2/top-headlines"
USER_AGENT: str = "NewsReelsDevBot/0.1 (+https://newsreels.local; dev-testing-only)"

# Server-side category mapping for NewsAPI.org
NEWSAPI_CATEGORY_MAPPING: dict[str, str] = {
    "tech": "technology",
    "technology": "technology",
    "science": "science",
    "national": "general",
    "international": "general",
    "business": "business",
    "entertainment": "entertainment",
    "sports": "sports",
    "health": "health",
}


def is_newsapi_dev_enabled() -> bool:
    """Returns True only when explicitly enabled via environment variable."""
    return os.getenv("ENABLE_NEWSAPI_DEV_SOURCE", "").strip().lower() in ("true", "1", "yes")


class NewsApiClient:
    """Client for NewsAPI.org /v2/top-headlines endpoint.
    Strictly gated to local development testing.
    Tracks credits/requests, applies server-side filters, and never logs the API key.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = NEWSAPI_TOP_HEADLINES_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("NEWSAPI_API_KEY", "")
        self.base_url = base_url
        self._client = http_client

    def __repr__(self) -> str:
        # Never expose or log the API key
        return f"<NewsApiClient base_url={self.base_url} key_set={bool(self._api_key)} dev_only=True>"

    def __str__(self) -> str:
        return self.__repr__()

    def fetch_top_headlines(
        self,
        category: str | None = None,
        country: str | None = None,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        """Queries NewsAPI.org top-headlines with server-side filters.
        Passes key via 'X-Api-Key' HTTP header so it is never exposed in request URLs or query logs.
        Returns: (articles_list, requests_used, errors_list)
        """
        if not is_newsapi_dev_enabled():
            return [], 0, ["NewsAPI dev source is disabled (ENABLE_NEWSAPI_DEV_SOURCE != true)"]

        if not self._api_key:
            return [], 0, ["NewsAPI.org API key not configured"]

        mapped_cat = NEWSAPI_CATEGORY_MAPPING.get(category.lower()) if category else None

        params: dict[str, Any] = {
            "pageSize": min(page_size, 100),
        }
        if mapped_cat:
            params["category"] = mapped_cat
        if country:
            params["country"] = country.lower()

        headers = {
            "User-Agent": USER_AGENT,
            "X-Api-Key": self._api_key,
        }

        requests_used = 1
        errors: list[str] = []
        items: list[dict[str, Any]] = []

        close_http = self._client is None
        http = self._client or httpx.Client(timeout=30.0, headers=headers)

        try:
            logger.info("[DEV ONLY] Querying NewsAPI.org (category=%s, country=%s)", mapped_cat, country)
            response = http.get(self.base_url, params=params, headers=headers)
            if response.status_code == 200:
                payload = response.json()
                if payload.get("status") == "ok":
                    items = payload.get("articles") or []
                else:
                    msg = f"NewsAPI returned non-ok status: {payload.get('message')}"
                    logger.warning(msg)
                    errors.append(msg)
            elif response.status_code == 429:
                msg = "NewsAPI rate limited (429): daily or minute request quota exceeded"
                logger.warning(msg)
                errors.append(msg)
            elif response.status_code in (401, 403):
                msg = f"NewsAPI authentication error HTTP {response.status_code}: invalid key or unauthorized"
                logger.error(msg)
                errors.append(msg)
            else:
                msg = f"NewsAPI HTTP error {response.status_code}: {response.text[:200]}"
                logger.warning(msg)
                errors.append(msg)
        except Exception as exc:
            msg = f"NewsAPI request exception: {exc}"
            logger.error(msg)
            errors.append(msg)
        finally:
            if close_http:
                http.close()

        return items, requests_used, errors


def poll_newsapi_dev_sources(
    db: Session,
    api_key: str | None = None,
    client: NewsApiClient | None = None,
    llm: LLMClient | None = None,
) -> tuple[int, int, int, list[str]]:
    """Polls all active sources with source_type='newsapi_dev_only'.
    Hard-gated behind ENABLE_NEWSAPI_DEV_SOURCE=true.
    Returns: (sources_polled, articles_created, requests_used, errors)
    """
    if not is_newsapi_dev_enabled():
        logger.info("NewsAPI dev source polling skipped: ENABLE_NEWSAPI_DEV_SOURCE is not enabled.")
        return 0, 0, 0, []

    effective_key = api_key or os.getenv("NEWSAPI_API_KEY", "")
    if not effective_key:
        msg = "NEWSAPI_API_KEY not configured; skipping NewsAPI poll."
        logger.warning(msg)
        return 0, 0, 0, [msg]

    sources = (
        db.query(Source)
        .filter(
            Source.is_active.is_(True),
            Source.source_type == "newsapi_dev_only",
        )
        .all()
    )
    if not sources:
        return 0, 0, 0, []

    api_client = client or NewsApiClient(api_key=effective_key)
    polled = 0
    created = 0
    total_requests = 0
    errors: list[str] = []

    for source in sources:
        polled += 1
        raw_items, reqs, req_errors = api_client.fetch_top_headlines(
            category=source.category,
            country=source.region if (source.region and len(source.region) == 2) else None,
        )
        total_requests += reqs
        errors.extend(req_errors)

        for item in raw_items:
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue

            # Deduplication
            if db.query(Article).filter(Article.url == url).first():
                continue

            desc = item.get("description") or ""
            content = item.get("content") or ""
            combined_text = f"{desc}\n\n{content}".strip()

            raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
                title=title,
                raw_text=combined_text,
                llm=llm,
            )
            translated_text = raw_for_clustering if orig_lang != "en" else None
            published = parse_datetime(item.get("publishedAt"))

            from worker.verify import extract_wire_attribution
            wire = extract_wire_attribution(f"{title} {combined_text}")

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
                    state=None,
                    district=None,
                    published_at=published,
                    wire_attribution=wire,
                )
            )
            created += 1

        db.commit()

    return polled, created, total_requests, errors
