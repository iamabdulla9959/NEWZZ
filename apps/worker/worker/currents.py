from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Article, Source, new_id
from worker.ingest import parse_datetime, process_and_translate_text
from worker.llm import LLMClient
from worker.credit_budget import CURRENT_DAILY_CREDIT_BUDGET, get_daily_provider_credits

logger = logging.getLogger("newsreels.currents")

CURRENTS_API_URL = "https://api.currentsapi.services/v1/latest-news"
CURRENTS_POLL_INTERVAL_MINUTES = 30
USER_AGENT = "NewsReelsBot/0.1"

CATEGORY_MAPPING: dict[str, str] = {
    "business": "business",
    "entertainment": "entertainment",
    "health": "health",
    "politics": "politics",
    "science": "science",
    "sports": "sports",
    "technology": "technology",
    "tech": "technology",
    "national": "politics",
    "international": "world",
}


class CurrentsClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = CURRENTS_API_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("CURRENTS_API_KEY", "")
        self.base_url = base_url
        self._client = http_client

    def __repr__(self) -> str:
        return f"<CurrentsClient base_url={self.base_url} key_set={bool(self._api_key)}>"

    def fetch_latest(
        self,
        category: str | None = None,
        country: str | None = None,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        if not self._api_key:
            return [], 0, ["Currents API key not configured"]

        params: dict[str, str] = {
            "language": "en",
            "page_size": str(min(max(page_size, 1), 100)),
        }
        mapped_category = CATEGORY_MAPPING.get((category or "").lower())
        if mapped_category:
            params["category"] = mapped_category
        if country:
            params["country"] = country.lower()

        headers = {"Authorization": self._api_key, "User-Agent": USER_AGENT}
        http = self._client or httpx.Client(timeout=30.0, headers=headers)
        close_http = self._client is None
        errors: list[str] = []
        try:
            response = http.get(self.base_url, params=params, headers=headers)
            if response.status_code == 429:
                return [], 1, ["Currents API rate limit reached"]
            if response.status_code in (401, 403):
                return [], 1, [f"Currents API authentication error HTTP {response.status_code}"]
            if not response.is_success:
                return [], 1, [f"Currents API HTTP {response.status_code}"]
            payload = response.json()
            if payload.get("status") not in (None, "ok"):
                return [], 1, [f"Currents API returned status {payload.get('status')}"]
            news = payload.get("news") or []
            return news if isinstance(news, list) else [], 1, []
        except Exception as exc:
            logger.error("Currents API request failed: %s", type(exc).__name__)
            errors.append(f"Currents API network/parse error: {type(exc).__name__}")
            return [], 1, errors
        finally:
            if close_http:
                http.close()


def ingest_currents_source(
    db: Session,
    source: Source,
    client: CurrentsClient,
    llm: LLMClient | None = None,
) -> tuple[int, int, list[str]]:
    items, requests_used, errors = client.fetch_latest(
        category=source.category,
        country="in" if source.region == "IN" else None,
    )
    created = 0
    for item in items:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        if db.query(Article).filter(Article.url == url).one_or_none():
            continue

        raw_content = str(item.get("description") or item.get("content") or "").strip()
        raw_for_clustering, original_text, original_language, confidence = process_and_translate_text(
            title=title,
            raw_text=raw_content,
            llm=llm,
        )
        db.add(
            Article(
                id=new_id(),
                source_id=source.id,
                url=url,
                title=title[:1024],
                raw_text=raw_for_clustering,
                original_text=original_text,
                translated_text=raw_for_clustering if original_language != "en" else None,
                original_language=original_language,
                translation_confidence=confidence,
                category=source.category,
                state=source.region,
                district=source.district,
                published_at=parse_datetime(item.get("published")),
            )
        )
        created += 1
    if created:
        db.commit()
    return created, requests_used, errors


def poll_currents_sources(
    db: Session,
    api_key: str | None = None,
    client: CurrentsClient | None = None,
    llm: LLMClient | None = None,
) -> tuple[int, int, int, list[str]]:
    effective_key = api_key or os.getenv("CURRENTS_API_KEY", "")
    if not effective_key and client is None:
        return 0, 0, 0, ["CURRENTS_API_KEY not configured; skipping Currents poll"]

    api_client = client or CurrentsClient(api_key=effective_key)
    used_today = get_daily_provider_credits(db, "currents_api")
    remaining = max(0, CURRENT_DAILY_CREDIT_BUDGET - used_today)
    if remaining == 0:
        return 0, 0, 0, [f"Currents daily budget reached ({CURRENT_DAILY_CREDIT_BUDGET}/250)"]
    sources = (
        db.query(Source)
        .filter(Source.is_active.is_(True), Source.source_type == "currents_api")
        .all()
    )
    total_created = 0
    total_requests = 0
    errors: list[str] = []
    for source in sources:
        if total_requests >= remaining:
            errors.append(f"Currents daily budget reached ({CURRENT_DAILY_CREDIT_BUDGET}/250)")
            break
        try:
            created, requests_used, source_errors = ingest_currents_source(db, source, api_client, llm)
            total_created += created
            total_requests += requests_used
            errors.extend(source_errors)
        except Exception as exc:
            errors.append(f"Currents source '{source.name}' failed: {type(exc).__name__}")
    return len(sources), total_created, total_requests, errors
