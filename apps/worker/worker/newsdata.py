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

logger = logging.getLogger("newsreels.newsdata")

# Named constants for tuneable polling schedule and credit limits
NEWSDATA_API_URL: str = "https://newsdata.io/api/1/latest"
NEWSDATA_POLL_INTERVAL_MINUTES: int = 75  # 60-90 minutes schedule
DAILY_CREDIT_CEILING: int = 200
USER_AGENT: str = "NewsReelsBot/0.1 (+https://newsreels.local)"

# Internal category to NewsData server-side category mapping
CATEGORY_MAPPING: dict[str, str] = {
    "tech": "technology",
    "science": "science",
    "national": "politics,top",
    "international": "world",
}

# Two focused requests per API-backed category keep the feed varied while
# remaining below the 200-credit daily free-tier ceiling.
QUERY_TERMS: dict[str, tuple[str, str]] = {
    "national": ("India politics", "India national news"),
    "tech": ("technology", "AI startups"),
    "science": ("science", "space research"),
}


def get_daily_credits_used(db: Session) -> int:
    """Calculates total credits consumed by newsdata_api today in UTC."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    runs = (
        db.query(WorkerRun)
        .filter(
            WorkerRun.provider == "newsdata_api",
            WorkerRun.timestamp >= today_start,
        )
        .all()
    )
    return sum(r.credits_used for r in runs)


class NewsDataClient:
    """Client for NewsData.io /latest endpoint with credit tracking,
    server-side filtering, and graceful 429 backoff handling.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = NEWSDATA_API_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("NEWSDATA_API_KEY", "")
        self.base_url = base_url
        self._client = http_client

    def __repr__(self) -> str:
        return f"<NewsDataClient base_url={self.base_url} key_set={bool(self._api_key)}>"

    def __str__(self) -> str:
        return self.__repr__()


    def fetch_latest(
        self,
        category: str | None = None,
        country: str | None = None,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        """Queries NewsData.io /latest endpoint with server-side filters.
        NEVER logs or exposes the API key.
        Returns: (results_list, credits_used, errors_list)
        """
        if not self._api_key:
            return [], 0, ["NewsData.io API key not configured"]

        mapped_cat = CATEGORY_MAPPING.get(category.lower()) if category else None

        params: dict[str, str] = {
            "apikey": self._api_key,
            "language": "en",  # Server-side language filter
        }
        if mapped_cat:
            params["category"] = mapped_cat
        if country:
            params["country"] = country.lower()
        if query:
            params["q"] = query

        credits_used = 1  # 1 credit per HTTP request
        errors: list[str] = []
        items: list[dict[str, Any]] = []

        close_http = self._client is None
        http = self._client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})

        try:
            logger.info("Querying NewsData.io (category=%s, country=%s)", mapped_cat, country)
            response = http.get(self.base_url, params=params)

            # Handle rate limit (429) or credit exhaustion gracefully
            if response.status_code == 429:
                err = "NewsData.io request limit exceeded (HTTP 429). Backing off until next cycle."
                logger.error(err)
                errors.append(err)
                return [], credits_used, errors

            if not response.is_success:
                err = f"NewsData.io HTTP {response.status_code}: {response.reason_phrase}"
                logger.error(err)
                errors.append(err)
                return [], credits_used, errors

            data = response.json()

            # Check if API returned an error status in JSON
            if data.get("status") == "error":
                results_obj = data.get("results") or {}
                msg = results_obj.get("message") if isinstance(results_obj, dict) else str(results_obj)
                code = results_obj.get("code") if isinstance(results_obj, dict) else ""
                err = f"NewsData.io API error ({code}): {msg}"
                logger.error(err)
                errors.append(err)
                return [], credits_used, errors

            raw_results = data.get("results") or []
            if isinstance(raw_results, list):
                items = raw_results

        except Exception as exc:
            err = f"NewsData.io network/parse error: {type(exc).__name__}"
            logger.error(err)
            errors.append(err)
        finally:
            if close_http:
                http.close()

        return items, credits_used, errors


def ingest_newsdata_source(
    db: Session,
    source: Source,
    client: NewsDataClient,
    llm: LLMClient | None = None,
    query: str | None = None,
) -> tuple[int, int, list[str]]:
    """Ingests a single NewsData-backed Source row.
    Maps response fields directly into existing Article model.
    Routes through translation step if non-English content is encountered.

    Returns: (articles_created, credits_used, errors)
    """
    country = "in" if source.region == "IN" else None
    items, credits_used, errors = client.fetch_latest(
        category=source.category,
        country=country,
        query=query,
    )

    created = 0
    for item in items:
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue

        # De-duplicate by URL
        if db.query(Article).filter(Article.url == url).one_or_none():
            continue

        desc = str(item.get("description") or "").strip()
        content = str(item.get("content") or "").strip()
        if desc and content and desc != content:
            raw_content = f"{desc}\n\n{content}"
        else:
            raw_content = content or desc

        published = parse_datetime(item.get("pubDate"))

        # Verify language server-side filter didn't leak non-English; translate if so
        item_lang = item.get("language")
        raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
            title=title,
            raw_text=raw_content,
            llm=llm,
        )
        translated_text = raw_for_clustering if orig_lang != "en" else None

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
                published_at=published,
            )
        )
        created += 1

    if created > 0:
        db.commit()

    return created, credits_used, errors


def poll_newsdata_sources(
    db: Session,
    api_key: str | None = None,
    client: NewsDataClient | None = None,
    llm: LLMClient | None = None,
) -> tuple[int, int, int, list[str]]:
    """Polls all active sources with source_type == 'newsdata_api'.
    Checks daily credit ceiling before making requests.

    Returns: (sources_polled, articles_created, credits_used, errors)
    """
    total_created = 0
    total_credits = 0
    errors: list[str] = []

    # Check daily credit usage ceiling
    used_today = get_daily_credits_used(db)
    if used_today >= DAILY_CREDIT_CEILING:
        err = f"Daily credit ceiling reached ({used_today}/{DAILY_CREDIT_CEILING} credits used). Skipping NewsData poll."
        logger.warning(err)
        errors.append(err)
        return 0, 0, 0, errors

    nd_client = client or NewsDataClient(api_key=api_key)
    sources = (
        db.query(Source)
        .filter(Source.is_active.is_(True), Source.source_type == "newsdata_api")
        .all()
    )

    polled = 0
    for source in sources:
        queries = QUERY_TERMS.get(source.category, (None,))
        # Check credit ceiling between requests as well
        for query in queries:
            if (used_today + total_credits) >= DAILY_CREDIT_CEILING:
                err = f"Daily credit ceiling reached during run ({used_today + total_credits}/{DAILY_CREDIT_CEILING})."
                logger.warning(err)
                errors.append(err)
                return polled, total_created, total_credits, errors

            polled += 1
            try:
                created, credits, src_errors = ingest_newsdata_source(
                    db, source, client=nd_client, llm=llm, query=query
                )
                total_created += created
                total_credits += credits
                errors.extend(src_errors)

                # If rate limit encountered, back off immediately
                if any("429" in e or "limit" in e.lower() for e in src_errors):
                    logger.warning("Rate limit encountered; stopping remaining NewsData polls for this cycle.")
                    return polled, total_created, total_credits, errors

            except Exception as exc:
                err_msg = f"NewsData source '{source.name}' ({source.id}) failed: {exc}"
                logger.error(err_msg)
                errors.append(err_msg)

    return polled, total_created, total_credits, errors
