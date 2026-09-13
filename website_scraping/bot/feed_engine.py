import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import feedparser

from bot.config import FeedSource

logger = logging.getLogger("feed_engine")


class FeedEngine:
    """
    Handles robust RSS/Atom feed fetching, robots.txt compliance, error handling,
    and schema normalization.
    """

    def __init__(self, user_agent: str, timeout_seconds: int = 15):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        # In-memory cache for RobotFileParser instances to avoid spamming /robots.txt
        self._robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}

    def is_allowed_by_robots(self, feed_url: str, correlation_id: str) -> bool:
        """
        Checks if the feed URL is permitted by the host's /robots.txt.
        Defaults to True if robots.txt is missing, unreachable, or returns 404/5xx.
        """
        try:
            parsed = urllib.parse.urlparse(feed_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = f"{origin}/robots.txt"

            if origin not in self._robots_cache:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(robots_url)
                # Fetch robots.txt with short timeout and custom User-Agent
                req = urllib.request.Request(
                    robots_url,
                    headers={"User-Agent": self.user_agent}
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        lines = [line.decode("utf-8", errors="ignore") for line in response.readlines()]
                        rp.parse(lines)
                except Exception as e:
                    # Missing or unreachable robots.txt means unrestricted access under standard crawler rules
                    logger.debug(f"[{correlation_id}] robots.txt for {origin} unreachable ({e}); allowing by default.")
                    rp.parse(["User-agent: *", "Allow: /"])

                self._robots_cache[origin] = rp

            allowed = self._robots_cache[origin].can_fetch(self.user_agent, feed_url)
            if not allowed:
                logger.warning(f"[{correlation_id}] Disallowed by robots.txt: {feed_url}")
            return allowed

        except Exception as e:
            logger.debug(f"[{correlation_id}] robots.txt evaluation exception: {e}; proceeding politely.")
            return True

    def fetch_source(
        self,
        source: FeedSource,
        correlation_id: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetches and normalizes a single RSS/Atom feed.
        Returns (normalized_articles, error_message).
        Guaranteed to never raise or crash the polling loop.
        """
        logger.info(f"[{correlation_id}] Processing feed '{source.name}' ({source.url})")

        # 1. Respect robots.txt policy
        if not self.is_allowed_by_robots(source.url, correlation_id):
            return [], "Disallowed by robots.txt"

        # 2. Fetch feed content via feedparser with custom User-Agent
        try:
            feed = feedparser.parse(
                source.url,
                agent=self.user_agent,
                request_headers={"User-Agent": self.user_agent},
            )

            # Check HTTP status if provided by feedparser transport
            status = getattr(feed, "status", None)
            if status is not None:
                if status == 429:
                    msg = f"HTTP 429: Rate limited by {source.name}"
                    logger.warning(f"[{correlation_id}] {msg}")
                    return [], msg
                elif status in (404, 410):
                    msg = f"HTTP {status}: Feed URL not found for {source.name}"
                    logger.error(f"[{correlation_id}] {msg}")
                    return [], msg
                elif status >= 500:
                    msg = f"HTTP {status}: Upstream server error for {source.name}"
                    logger.warning(f"[{correlation_id}] {msg}")
                    return [], msg
                elif status not in (200, 301, 302, 304):
                    msg = f"HTTP {status}: Unexpected response for {source.name}"
                    logger.warning(f"[{correlation_id}] {msg}")
                    return [], msg

            # Inspect bozo exceptions (malformed XML, parse warnings)
            if feed.bozo and not feed.entries:
                bozo_exc = getattr(feed, "bozo_exception", "Unknown XML parse error")
                msg = f"Malformed feed XML from {source.name}: {bozo_exc}"
                logger.warning(f"[{correlation_id}] {msg}")
                return [], msg

            # 3. Normalize entries strictly according to required schema
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            normalized_articles: List[Dict[str, Any]] = []

            for entry in feed.entries:
                link = getattr(entry, "link", None)
                if not link:
                    # Skip entries without a valid target link
                    continue

                title = str(getattr(entry, "title", "Untitled")).strip()

                # Extract summary, checking fallback fields commonly used in Atom / RSS 2.0
                summary = ""
                if hasattr(entry, "summary"):
                    summary = str(entry.summary)
                elif hasattr(entry, "description"):
                    summary = str(entry.description)
                elif hasattr(entry, "content") and entry.content:
                    summary = str(entry.content[0].value)

                # Author extraction
                author = "Unknown"
                if hasattr(entry, "author") and entry.author:
                    author = str(entry.author)
                elif hasattr(entry, "authors") and entry.authors:
                    author_names = [str(a.get("name", "")) for a in entry.authors if isinstance(a, dict) and "name" in a]
                    if author_names:
                        author = ", ".join(author_names)

                # Published date extraction
                published_date = ""
                if hasattr(entry, "published"):
                    published_date = str(entry.published)
                elif hasattr(entry, "updated"):
                    published_date = str(entry.updated)
                elif hasattr(entry, "pubDate"):
                    published_date = str(entry.pubDate)
                else:
                    published_date = now_iso

                normalized = {
                    "source": source.name,
                    "title": title,
                    "link": str(link).strip(),
                    "summary": summary.strip(),
                    "author": author.strip(),
                    "published_date": published_date.strip(),
                    "fetched_at": now_iso,
                }
                normalized_articles.append(normalized)

            logger.info(
                f"[{correlation_id}] Successfully extracted {len(normalized_articles)} articles from {source.name}"
            )
            return normalized_articles, None

        except (urllib.error.URLError, socket.timeout, TimeoutError) as net_err:
            msg = f"Network timeout/error fetching {source.name}: {net_err}"
            logger.error(f"[{correlation_id}] {msg}")
            return [], msg
        except Exception as exc:
            msg = f"Unexpected failure fetching {source.name}: {exc}"
            logger.error(f"[{correlation_id}] {msg}", exc_info=False)
            return [], msg
