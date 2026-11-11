from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ref",
    "ocid",
    "ncid",
    "igshid",
    "msclkid",
}


def normalize_article_url(url: str) -> str:
    """Conservatively normalizes article URLs for deduplication.

    Rules:
    - Trims whitespace.
    - Lowercases scheme and netloc (domain).
    - Removes fragments (#...).
    - Removes common analytics/marketing tracking parameters while preserving
      content/pagination identifiers (id, article_id, story, p, etc.).
    - Sorts query parameters deterministically.
    - Strips trailing slash on non-root paths.
    """
    if not url:
        return ""
    try:
        parts = urlparse(url.strip())
        if not parts.scheme or not parts.netloc:
            return url.strip()

        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()

        path = parts.path
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        filtered_pairs = [
            (k, v) for k, v in query_pairs
            if k.lower() not in TRACKING_QUERY_PARAMS
        ]
        filtered_pairs.sort(key=lambda item: item[0])
        clean_query = urlencode(filtered_pairs)

        return urlunparse((scheme, netloc, path, parts.params, clean_query, ""))
    except Exception:
        return url.strip()

import feedparser
import httpx
from langdetect import detect_langs
from sqlalchemy.orm import Session

from worker import paths  # noqa: F401 — puts apps/api on sys.path

from app.models import Article, Source, new_id
from worker.llm import LLMClient, TRANSLATION_SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger("newsreels.ingest")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

NEWSDATA_URL = "https://newsdata.io/api/1/latest"

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None


def sanitize_article_text(text: str) -> str:
    cleaned = re.sub(r"ONLY\s+AVAILABLE\s+IN\s+PAID\s+PLANS.*", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"Subscribe\s+now\s+to\s+read.*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"You\s+don['’]t\s+have\s+any\s+Active\s+Subscription.*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()


def process_and_translate_text(
    title: str,
    raw_text: str,
    llm: LLMClient | None = None,
) -> tuple[str, str, str | None, float | None]:
    raw_text = sanitize_article_text(raw_text)
    """Detects language of scraped text.
    If not English, translates to English using the exact prompt:
    'Translate the following news article text from {source_language} to English. Preserve every fact, number, name, date, and quote exactly. Do not summarize, do not omit anything, do not add interpretation. If a term has no exact English equivalent, translate literally and add a short bracketed clarification. Output only the translated text, nothing else.'

    Returns:
    (raw_text_for_clustering, original_text, original_language, translation_confidence)
    """
    combined = f"{title}\n{raw_text}".strip()
    detected_lang = "en"
    confidence = 1.0

    try:
        if combined:
            predictions = detect_langs(combined)
            if predictions:
                detected_lang = predictions[0].lang
                confidence = float(predictions[0].prob)
    except Exception as exc:
        logger.debug("Language detection fallback to 'en': %s", exc)
        detected_lang = "en"
        confidence = 1.0

    original_text = raw_text

    if detected_lang == "en" or not raw_text.strip():
        return raw_text, original_text, "en", confidence

    # Non-English: translate via LLM
    if llm is not None:
        system_prompt = TRANSLATION_SYSTEM_PROMPT_TEMPLATE.format(source_language=detected_lang)
        user_prompt = f"TITLE: {title}\n\nTEXT:\n{raw_text}"
        try:
            translated = llm.complete_text(system_prompt, user_prompt)
            if translated.strip():
                return translated.strip(), original_text, detected_lang, confidence
        except Exception as exc:
            logger.warning("Translation failed for lang '%s', falling back to original: %s", detected_lang, exc)

    return raw_text, original_text, detected_lang, confidence


def ingest_rss_source(
    db: Session,
    source: Source,
    client: httpx.Client | None = None,
    llm: LLMClient | None = None,
    expected_lease_holder: str | None = None,
    expected_lease_generation: int | None = None,
    lease_name: str = "canonical_ingestion",
) -> int:
    if not source.rss_url:
        return 0
    http = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    close = client is None
    created = 0
    try:
        response = http.get(source.rss_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        for entry in parsed.entries:
            raw_url = str(entry.get("link") or "").strip()
            url = normalize_article_url(raw_url)
            title = str(entry.get("title") or "").strip()
            if not url or not title:
                continue
            if db.query(Article).filter(Article.url == url).one_or_none():
                continue
            summary = entry.get("summary") or entry.get("description") or ""
            text = _strip_html(str(summary)).strip()
            if not text and url:
                try:
                    art_resp = http.get(url, timeout=10.0)
                    if art_resp.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(art_resp.content, "html.parser")
                        content_node = (
                            soup.find("div", id="PdfDiv")
                            or soup.find("div", class_="innner-page-main-about-us-content-right-part")
                            or soup.find("div", class_="ReleaseContent")
                            or soup.find("div", id="ReleaseContent")
                            or soup.find("article")
                        )
                        if content_node:
                            text = re.sub(r"\s+", " ", content_node.get_text(separator=" ", strip=True)).strip()[:10000]
                        elif soup.body:
                            text = re.sub(r"\s+", " ", soup.body.get_text(separator=" ", strip=True)).strip()[:10000]
                except Exception as exc:
                    logger.debug("Could not fetch fallback article text for %s: %s", url, exc)
            # Strict publication date extraction: NEVER replace missing publication time with update time
            raw_pub = entry.get("published")
            published = parse_datetime(str(raw_pub) if raw_pub else None)
            if not published:
                parsed_pub_struct = entry.get("published_parsed")
                if parsed_pub_struct:
                    try:
                        import calendar
                        published = datetime.fromtimestamp(calendar.timegm(parsed_pub_struct), tz=timezone.utc)
                    except Exception:
                        published = None

            # Update date extraction: tracked separately and never conflated with publication time
            raw_upd = entry.get("updated")
            source_updated = parse_datetime(str(raw_upd) if raw_upd else None)
            if not source_updated:
                parsed_upd_struct = entry.get("updated_parsed")
                if parsed_upd_struct:
                    try:
                        import calendar
                        source_updated = datetime.fromtimestamp(calendar.timegm(parsed_upd_struct), tz=timezone.utc)
                    except Exception:
                        source_updated = None

            # Step 2 translation layer
            raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
                title=title,
                raw_text=text,
                llm=llm,
            )

            translated_text = raw_for_clustering if orig_lang != "en" else None

            if expected_lease_holder is not None and expected_lease_generation is not None:
                from worker.coordination import validate_lease_fencing, StaleLeaseError
                if not validate_lease_fencing(
                    db,
                    lease_name=lease_name,
                    holder_id=expected_lease_holder,
                    expected_generation=expected_lease_generation,
                ):
                    db.rollback()
                    raise StaleLeaseError(
                        f"Lease superseded for worker '{expected_lease_holder}' at gen {expected_lease_generation} before article insert"
                    )

            from worker.verify import extract_wire_attribution
            wire = extract_wire_attribution(f"{title} {text}")

            try:
                with db.begin_nested():
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
                            district=source.district,
                            published_at=published,
                            wire_attribution=wire,
                        )
                    )
                    db.flush()
                created += 1
            except Exception as insert_exc:
                logger.debug("Duplicate or conflict during article insert for %s: %s", url, insert_exc)
                continue
        if expected_lease_holder is not None and expected_lease_generation is not None:
            from worker.coordination import validate_lease_fencing, StaleLeaseError
            if not validate_lease_fencing(
                db,
                lease_name=lease_name,
                holder_id=expected_lease_holder,
                expected_generation=expected_lease_generation,
            ):
                db.rollback()
                raise StaleLeaseError(
                    f"Lease superseded for worker '{expected_lease_holder}' at gen {expected_lease_generation} before article commit"
                )
        db.commit()
    finally:
        if close:
            http.close()
    return created


def ingest_newsdata(
    db: Session,
    api_key: str,
    source: Source,
    client: httpx.Client | None = None,
    llm: LLMClient | None = None,
) -> int:
    if not api_key:
        return 0
    http = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})
    close = client is None
    created = 0
    try:
        params = {"apikey": api_key, "language": "en", "q": source.name}
        response = http.get(NEWSDATA_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results") or []:
            url = (item.get("link") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue
            if db.query(Article).filter(Article.url == url).one_or_none():
                continue
            text = str(item.get("description") or item.get("content") or "")

            raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
                title=title,
                raw_text=text,
                llm=llm,
            )
            translated_text = raw_for_clustering if orig_lang != "en" else None

            from worker.verify import extract_wire_attribution
            wire = extract_wire_attribution(f"{title} {text}")

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
                    district=source.district,
                    published_at=parse_datetime(item.get("pubDate")),
                    wire_attribution=wire,
                )
            )
            created += 1
        db.commit()
    finally:
        if close:
            http.close()
    return created


def ingest_gdelt(
    db: Session,
    source: Source,
    client: httpx.Client | None = None,
    llm: LLMClient | None = None,
) -> int:
    domain = ""
    if source.rss_url:
        domain = urlparse(source.rss_url).netloc.replace("feeds.", "")
    if not domain:
        return 0
    http = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})
    close = client is None
    created = 0
    try:
        params = {
            "query": f"domain:{domain}",
            "mode": "ArtList",
            "maxrecords": "20",
            "format": "json",
        }
        response = http.get(GDELT_URL, params=params)
        if response.status_code != 200:
            return 0
        payload = response.json()
        for item in payload.get("articles") or []:
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue
            if db.query(Article).filter(Article.url == url).one_or_none():
                continue

            text = item.get("seendate") or ""
            raw_for_clustering, original_text, orig_lang, conf = process_and_translate_text(
                title=title,
                raw_text=text,
                llm=llm,
            )
            translated_text = raw_for_clustering if orig_lang != "en" else None

            from worker.verify import extract_wire_attribution
            wire = extract_wire_attribution(f"{title} {text}")

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
                    district=source.district,
                    published_at=None,
                    wire_attribution=wire,
                )
            )
            created += 1
        db.commit()
    finally:
        if close:
            http.close()
    return created


def ingest_all_active(
    db: Session,
    newsdata_key: str = "",
    llm: LLMClient | None = None,
) -> tuple[int, int, list[str]]:
    """Ingests all active sources.
    Returns: (sources_polled, total_articles_created, list_of_errors)
    """
    total = 0
    polled = 0
    errors: list[str] = []
    # Hard guard: exclude dedicated API streams (newsdata_api) and dev-only sources (newsapi_dev_only)
    sources = (
        db.query(Source)
        .filter(
            Source.is_active.is_(True),
            Source.source_type.notin_(["newsdata_api", "newsapi_dev_only"]),
        )
        .all()
    )
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for source in sources:
            polled += 1
            try:
                total += ingest_rss_source(db, source, client=client, llm=llm)
            except Exception as exc:
                err_msg = f"Source '{source.name}' ({source.id}) ingest failed: {exc}"
                logger.error(err_msg)
                errors.append(err_msg)
    return polled, total, errors


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()
