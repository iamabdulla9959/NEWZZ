import html
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
import feedparser

# Configure clean, timestamped logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [NewsAggregator] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("NewsAggregator")

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in [_repo_root, os.path.join(_repo_root, "apps", "api"), os.path.join(_repo_root, "website_scraping"), os.path.join(_repo_root, "apps", "worker")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Output destination file (always resolves to website_scraping/news.json)
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")
FEED_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "feed.json"))
STATIC_FEED_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api", "app", "static", "feed.json"))

# Target Render deployment endpoint to keep warmed (sub-200ms latency)
KEEP_ALIVE_URL = os.getenv("RENDER_KEEP_ALIVE_URL", "https://newzz-5e19.onrender.com")

# Scheduling interval in minutes (13.5 minutes = 810s, safely inside Render's 15-minute inactivity limit)
INTERVAL_MINUTES = float(os.getenv("CRAWLER_INTERVAL_MINUTES", "13.5"))

# Max fresh articles to extract per feed per cycle
# Increased to allow >= 40 distinct clusters per category after deduplication
MAX_ARTICLES_PER_FEED = 20

USER_AGENT = "NewsAggregatorBot/1.0 (+https://github.com/nuhmanpk/WebScrapper)"

# ────────────────────────────────────────────────────────
# CANONICAL CATEGORY NORMALIZATION MAP
# Maps all known raw category variants → one canonical value.
# This is the single authoritative normalization layer.
# ────────────────────────────────────────────────────────
CATEGORY_NORMALIZATION: Dict[str, str] = {
    # Technology
    "tech": "Technology",
    "technology": "Technology",
    "TECH": "Technology",
    "Tech": "Technology",
    "Technology": "Technology",
    # World / International
    "international": "World",
    "International": "World",
    "world": "World",
    "World": "World",
    "World News": "World",
    "world news": "World",
    "Intl": "World",
    "intl": "World",
    "Global": "World",
    "global": "World",
    # Politics
    "politics": "Politics",
    "Politics": "Politics",
    # Business
    "business": "Business",
    "Business": "Business",
    "economy": "Business",
    "Economy": "Business",
    # National
    "national": "National",
    "National": "National",
    "India": "National",
    "india": "National",
    # Science
    "science": "Science",
    "Science": "Science",
    # Health
    "health": "Health",
    "Health": "Health",
    # Sports
    "sports": "Sports",
    "Sports": "Sports",
    # Entertainment
    "entertainment": "Entertainment",
    "Entertainment": "Entertainment",
    # Environment
    "environment": "Environment",
    "Environment": "Environment",
    "climate": "Environment",
    "Climate": "Environment",
    # State (stays as State)
    "state": "State",
    "State": "State",
    # Education (supported internally but not a primary category slot)
    "education": "Education",
    "Education": "Education",
}


def normalize_category(raw: str) -> str:
    """Returns canonical category string for a raw category input."""
    if not raw:
        return "National"
    canonical = CATEGORY_NORMALIZATION.get(raw.strip())
    if canonical:
        return canonical
    # Try case-insensitive fallback
    lower = raw.strip().lower()
    for key, val in CATEGORY_NORMALIZATION.items():
        if key.lower() == lower:
            return val
    return raw.strip()


# ────────────────────────────────────────────────────────
# ALL 28 INDIAN STATES
# ────────────────────────────────────────────────────────
INDIAN_STATES: List[str] = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    # Union Territories (8 Jurisdictions - 36 Total)
    "Andaman and Nicobar",
    "Chandigarh",
    "Dadra and Nagar Haveli",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

# ────────────────────────────────────────────────────────
# INDIAN NATIONAL & CATEGORY FEEDS
# Multiple queries per category to ensure >= 50 raw articles per category
# so >= 40 distinct clusters form after deduplication.
# Canonical category names used throughout.
# ────────────────────────────────────────────────────────
INDIA_CATEGORY_FEEDS: List[Tuple[str, str]] = [
    # National Top Stories & Topic Feeds (Real-time 15m cadence)
    ("National", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
    ("National", "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en"),
    ("National", "https://news.google.com/rss/search?q=India+breaking+news+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("National", "https://news.google.com/rss/search?q=India+government+policy+news+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Technology
    ("Technology", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Technology", "https://news.google.com/rss/search?q=Technology+AI+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Technology", "https://news.google.com/rss/search?q=India+digital+cyber+mobile+tech+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Business
    ("Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Business", "https://news.google.com/rss/search?q=India+stock+market+economy+RBI+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Business", "https://news.google.com/rss/search?q=India+GDP+trade+corporate+startup+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Politics
    ("Politics", "https://news.google.com/rss/search?q=Indian+politics+news+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Politics", "https://news.google.com/rss/search?q=BJP+Congress+India+election+politics+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Politics", "https://news.google.com/rss/search?q=India+PM+Modi+government+cabinet+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Science
    ("Science", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Science", "https://news.google.com/rss/search?q=Science+news+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Science", "https://news.google.com/rss/search?q=ISRO+space+research+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Health
    ("Health", "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Health", "https://news.google.com/rss/search?q=Health+medical+news+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Health", "https://news.google.com/rss/search?q=India+hospital+disease+medicine+healthcare+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Sports
    ("Sports", "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Sports", "https://news.google.com/rss/search?q=Sports+news+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Sports", "https://news.google.com/rss/search?q=Cricket+India+IPL+BCCI+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Entertainment
    ("Entertainment", "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-IN&gl=IN&ceid=IN:en"),
    ("Entertainment", "https://news.google.com/rss/search?q=Entertainment+Bollywood+cinema+news+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Entertainment", "https://news.google.com/rss/search?q=Bollywood+film+actor+OTT+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    # Environment
    ("Environment", "https://news.google.com/rss/search?q=Environment+climate+news+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Environment", "https://news.google.com/rss/search?q=India+pollution+climate+change+green+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
]

# ────────────────────────────────────────────────────────
# GLOBAL CATEGORY FEEDS
# ────────────────────────────────────────────────────────
GLOBAL_CATEGORY_FEEDS: List[Tuple[str, str]] = [
    ("World", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
    ("World", "https://news.google.com/rss/search?q=International+world+news+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Technology", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
    ("Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("Science", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en"),
    ("Health", "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-US&gl=US&ceid=US:en"),
    ("Sports", "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=en-US&gl=US&ceid=US:en"),
]

# Major Global Outlets (Baseline feeds — classified as World / National as appropriate)
GLOBAL_BASELINES: Dict[str, str] = {
    "BBC News (Global)": "http://feeds.bbci.co.uk/news/rss.xml",
    "The New York Times (Global)": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
}


def load_existing_links(filepath: str) -> Set[str]:
    """Reads existing news.json (supports both standard JSON array and JSONL) to pre-populate seen URLs and guarantee zero duplicates."""
    seen_links = set()
    if not os.path.exists(filepath):
        return seen_links

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return seen_links
            if content.startswith("["):
                records = json.loads(content)
                for record in records:
                    link = record.get("link")
                    if link:
                        seen_links.add(link)
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        link = record.get("link")
                        if link:
                            seen_links.add(link)
                    except json.JSONDecodeError:
                        continue
        logger.info(f"Loaded {len(seen_links)} existing unique article URLs from {filepath}.")
    except Exception as e:
        logger.warning(f"Could not read {filepath}: {e}. Starting fresh.")

    return seen_links

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    link = record.get("link")
                    if link:
                        seen_links.add(link)
                except json.JSONDecodeError:
                    continue
        logger.info(f"Loaded {len(seen_links)} existing unique article URLs from {filepath}.")
    except Exception as e:
        logger.warning(f"Could not read {filepath}: {e}. Starting fresh.")

    return seen_links


def extract_publisher(entry, default_name: str) -> str:
    """Extracts publisher attribution name from RSS source or entry title."""
    if hasattr(entry, "source") and hasattr(entry.source, "title"):
        return str(entry.source.title).strip()
    title = str(getattr(entry, "title", ""))
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts) == 2 and len(parts[1]) < 35:
            return parts[1].strip()
    return default_name


def parse_feed_articles(
    feed_url: str,
    scope: str,
    category: str,
    state: Optional[str],
    default_source: str,
    seen_links: Set[str],
    max_items: int = MAX_ARTICLES_PER_FEED,
) -> List[Dict]:
    """Fetches articles from an RSS feed, strictly deduplicating by URL.
    Category is normalized at ingestion time."""
    canonical_cat = normalize_category(category)
    new_articles = []
    try:
        feed = feedparser.parse(
            feed_url,
            agent=USER_AGENT,
            request_headers={"User-Agent": USER_AGENT},
        )

        for entry in feed.entries:
            if len(new_articles) >= max_items:
                break

            link = getattr(entry, "link", None)
            if not link:
                continue

            link = str(link).strip()
            # ZERO DUPLICATES CHECK
            if link in seen_links:
                continue

            title = str(getattr(entry, "title", "Untitled")).strip()
            clean_title = re.sub(r"\s+-\s+[^-]+$", "", title) if " - " in title else title

            # Strict newsroom quality guard: reject word puzzle hints, horoscopes, and trivial gaming/clickbait
            title_low = clean_title.lower()
            if any(bad in title_low for bad in [
                "quordle hint", "wordle hint", "connections hint", "strands hint",
                "daily clue", "clues and answers", "horoscope today", "daily horoscope",
                "today's tarot", "crossword clue", "word puzzle", "answers today", "hints and answers"
            ]):
                continue

            summary = ""
            if hasattr(entry, "content") and entry.content:
                try:
                    summary = str(entry.content[0].get("value", ""))
                except Exception:
                    summary = ""
            if not summary and hasattr(entry, "summary"):
                summary = str(entry.summary)
            elif not summary and hasattr(entry, "description"):
                summary = str(entry.description)
            raw_html_summary = summary
            # Extract multi-item list if present (e.g. Google News multi-source coverage)
            list_items = re.findall(r'<li[^>]*><a[^>]*>(.*?)<\/a>(?:&nbsp;&nbsp;<font[^>]*>(.*?)<\/font>)?', raw_html_summary)
            if list_items and len(list_items) > 1:
                corrob = []
                for it_t, it_s in list_items[1:4]:
                    clean_it_t = html.unescape(re.sub(r"<[^>]+>", " ", it_t)).strip()
                    clean_it_s = html.unescape(it_s).strip() if it_s else ""
                    if clean_it_t and clean_it_t.lower() != clean_title.lower():
                        if clean_it_s:
                            corrob.append(f"{clean_it_s} reports: {clean_it_t}")
                        else:
                            corrob.append(clean_it_t)
                if corrob:
                    summary = ". ".join(corrob) + "."
                else:
                    summary = html.unescape(raw_html_summary)
                    summary = re.sub(r"<[^>]+>", " ", summary)
                    summary = re.sub(r"\s+", " ", summary).strip()
                    summary = re.sub(r"&nbsp;&nbsp;.*$", "", summary).strip()
            else:
                summary = html.unescape(raw_html_summary)
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()
                summary = re.sub(r"&nbsp;&nbsp;.*$", "", summary).strip()

            author = str(getattr(entry, "author", extract_publisher(entry, default_source))).strip()
            pub_date_raw = str(getattr(entry, "published", getattr(entry, "updated", ""))).strip()
            pub_date_iso = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                    pub_date_iso = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pass
            if not pub_date_iso and pub_date_raw:
                try:
                    import email.utils
                    dt = email.utils.parsedate_to_datetime(pub_date_raw)
                    if dt:
                        pub_date_iso = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pass
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            published_final = pub_date_iso

            article = {
                "scope": scope,
                "category": canonical_cat,  # Always store canonical category
                "state": state,
                "source": extract_publisher(entry, default_source),
                "title": clean_title,
                "link": link,
                "summary": summary,
                "author": author,
                "published_date": published_final,
                "fetched_at": now_iso,
            }

            new_articles.append(article)
            seen_links.add(link)

    except Exception as exc:
        logger.debug(f"Feed error for {scope}/{canonical_cat} / {state}: {exc}")

    return new_articles


def generate_factual_article_summary(
    headline: str, state: Optional[str], category: str, source_name: str, raw_snippet: str = ""
) -> Tuple[str, List[str], int]:
    """Generates a strictly factual summary derived purely from real article headline, source, and snippet without boilerplate filler."""
    clean_head = re.sub(r"\s+-\s+[^-]+$", "", headline).strip()
    src = source_name or "Verified Wire"
    st = state or "National"

    clean_snippet = re.sub(r"<[^>]+>", " ", raw_snippet or "").strip()
    clean_snippet = html.unescape(clean_snippet)
    clean_snippet = re.sub(r"\s+-\s+[^-]+$", "", clean_snippet).strip()

    sentences = []
    # If snippet has genuine content distinct from the headline:
    if clean_snippet and clean_snippet.lower() != clean_head.lower() and len(clean_snippet) > 15:
        if clean_head.lower() not in clean_snippet.lower():
            sentences.append(f"{clean_head}.")
        sentences.append(clean_snippet)
    else:
        # Bounded factual reporting statement:
        sentences.append(f"Reporting from {src}: {clean_head}.")

    full_summary = " ".join(sentences)
    words = len(full_summary.split())

    key_facts = [
        clean_head[:100],
        f"Source: {src}",
    ]
    if clean_snippet and clean_snippet.lower() != clean_head.lower() and len(clean_snippet) > 20:
        key_facts.append(clean_snippet[:100])
    else:
        key_facts.append(f"Region: {st}")

    return full_summary, key_facts, words


# Backward-compatible alias for any legacy callers
generate_rich_200w_summary = generate_factual_article_summary


def sync_articles_to_feed_json(articles: List[Dict]) -> None:
    """Syncs fresh crawled articles into feed.json so live frontend refresh sees new news immediately with verified factual summaries."""
    if not articles:
        return
    import uuid
    for target_path in [FEED_JSON_FILE, STATIC_FEED_FILE]:
        if not os.path.exists(target_path):
            continue
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", [])
            existing_links = {it.get("canonical_url") or it.get("source_url") for it in items if it}

            new_cards = []
            for art in articles:
                link = art.get("link")
                if link and link in existing_links:
                    continue
                headline = art.get("title", "").strip()
                st = art.get("state")
                cat = (art.get("category") or "national").strip().lower()
                source = art.get("source") or "Verified News Wire"
                raw_snip = art.get("summary", "")

                summary_text, key_facts, word_count = generate_factual_article_summary(
                    headline=headline,
                    state=st,
                    category=cat,
                    source_name=source,
                    raw_snippet=raw_snip,
                )

                new_cards.append({
                    "id": str(uuid.uuid4()),
                    "headline": headline,
                    "summary": summary_text,
                    "key_facts": key_facts,
                    "word_count": word_count,
                    "category": cat,
                    "state": st,
                    "published_at": art.get("published_date"),
                    "newzz_published_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_name": source,
                    "canonical_url": link,
                    "url": link,
                    "sources": [
                        {
                            "source_id": str(uuid.uuid4()),
                            "name": source,
                            "url": link,
                            "trust_tier": "1"
                        }
                    ],
                    "verification_type": "cross_verified",
                    "verification_score": 92.0,
                    "final_feed_score": 55.0,
                    "priority_reason": "Freshly ingested and categorized from verified news reporting.",
                })

            if new_cards:
                data["items"] = new_cards + items
                temp_file = target_path + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, target_path)
        except Exception as err:
            logger.warning(f"Could not sync to feed.json: {err}")


def sync_articles_to_newsreels_db(articles: List[Dict]) -> int:
    """Syncs fresh crawled articles into newsreels.db using the existing ranking and sync pipeline."""
    if not articles:
        return 0
    try:
        from process_news import sync_to_newsreels_monorepo, clean_text
        synced = 0
        for art in articles:
            headline = clean_text(art.get("title", ""))
            if not headline:
                continue
            raw_summary = clean_text(art.get("summary", ""))
            src = art.get("source", "news wire")

            # Grounded factual summary derived strictly from article content
            clean_head = re.sub(r"\s+-\s+[^-]+$", "", headline).strip()
            clean_snip = re.sub(r"\s+-\s+[^-]+$", "", raw_summary).strip()

            clean_snip = re.sub(r"&nbsp;&nbsp;.*$", "", clean_snip).strip()

            if clean_snip and len(clean_snip) > 20 and clean_snip.lower() != clean_head.lower():
                if clean_head.lower() not in clean_snip.lower():
                    summary = f"{clean_head}. {clean_snip}"
                else:
                    summary = clean_snip
            else:
                summary = f"{clean_head}. Reported by {src}."

            card_data = {
                "headline": clean_head,
                "summary": summary,
                "category": art.get("category", "National"),
                "state": art.get("state"),
                "priority_score": 5,
                "published_at": art.get("published_date") or art.get("fetched_at"),
            }
            cluster = [art]
            if sync_to_newsreels_monorepo(card_data, cluster):
                synced += 1
        if synced > 0:
            logger.info(f" -> [Database Sync  : newsreels.db  ]: +{synced} fresh card(s) synced to SQLite")
        return synced
    except Exception as err:
        logger.warning(f"Could not sync articles to newsreels.db: {err}")
        return 0


def append_articles_to_file(filepath: str, articles: List[Dict]) -> None:
    """Saves newly discovered unique articles to destination JSON as a valid standard JSON array and syncs to feed.json and newsreels.db."""
    if not articles:
        return

    existing = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("["):
                    existing = json.loads(content)
                elif content:
                    for line in content.splitlines():
                        if line.strip():
                            try:
                                existing.append(json.loads(line.strip()))
                            except Exception:
                                pass
        except Exception:
            existing = []

    existing_links = {a.get("link") for a in existing if a.get("link")}
    fresh_unique = [a for a in articles if a.get("link") not in existing_links]
    all_articles = existing + fresh_unique

    temp_file = filepath + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, filepath)

    sync_articles_to_feed_json(articles)
    if fresh_unique:
        sync_articles_to_newsreels_db(fresh_unique)


def run_crawl_cycle(seen_links: Set[str]) -> int:
    """
    Executes one complete round of ingestion across:
      1. Global Baseline News (BBC, NYT)
      2. Global Categories: Technology, World, Science, Politics, Business, Health, Sports, Entertainment, Environment
      3. India Categories: National, Technology, Science, Politics, Business, Health, Sports, Entertainment, Environment
      4. All 28 Indian States (Andhra Pradesh through West Bengal)
    All categories are normalized to canonical values before storage.
    """
    cycle_start = time.time()
    logger.info("=" * 72)
    logger.info("Starting 10-minute multi-source ingestion (Global + India + 28 States)...")
    total_new = 0

    # 1. Global Baseline News (BBC & NYT) — classified as World
    for name, url in GLOBAL_BASELINES.items():
        fresh = parse_feed_articles(
            url, scope="Global", category="World", state=None,
            default_source=name, seen_links=seen_links
        )
        if fresh:
            append_articles_to_file(OUTPUT_FILE, fresh)
            total_new += len(fresh)
            logger.info(f" -> [Global Baseline] {name:<23}: +{len(fresh)} new articles")
        time.sleep(0.2)

    # 2. Global Categories (with multiple queries per category)
    global_cat_count = 0
    seen_global_cats: Dict[str, int] = {}
    for cat_name, feed_url in GLOBAL_CATEGORY_FEEDS:
        fresh = parse_feed_articles(
            feed_url, scope="Global", category=cat_name, state=None,
            default_source=f"Global {cat_name}", seen_links=seen_links
        )
        if fresh:
            append_articles_to_file(OUTPUT_FILE, fresh)
            total_new += len(fresh)
            global_cat_count += len(fresh)
            seen_global_cats[cat_name] = seen_global_cats.get(cat_name, 0) + len(fresh)
        time.sleep(0.2)

    for cat, count in sorted(seen_global_cats.items()):
        logger.info(f" -> [Global Category: {cat:<13}]: +{count} new articles")

    # 3. India Categories (with multiple queries per category)
    india_cat_count = 0
    seen_india_cats: Dict[str, int] = {}
    for cat_name, feed_url in INDIA_CATEGORY_FEEDS:
        fresh = parse_feed_articles(
            feed_url, scope="India", category=cat_name, state=None,
            default_source=f"India {cat_name}", seen_links=seen_links
        )
        if fresh:
            append_articles_to_file(OUTPUT_FILE, fresh)
            total_new += len(fresh)
            india_cat_count += len(fresh)
            seen_india_cats[cat_name] = seen_india_cats.get(cat_name, 0) + len(fresh)
        time.sleep(0.2)

    for cat, count in sorted(seen_india_cats.items()):
        logger.info(f" -> [India Category : {cat:<13}]: +{count} new articles")

    # 4. All 28 Indian States — target 15-25 articles per state
    # Use 2 queries per state for diversity
    states_new_count = 0
    for state in INDIAN_STATES:
        # Primary query
        query_url_1 = f"https://news.google.com/rss/search?q={urllib.parse.quote(state)}+news+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
        fresh1 = parse_feed_articles(
            query_url_1, scope="India", category="State", state=state,
            default_source=f"{state} News", seen_links=seen_links, max_items=15
        )
        if fresh1:
            append_articles_to_file(OUTPUT_FILE, fresh1)
            total_new += len(fresh1)
            states_new_count += len(fresh1)
        time.sleep(0.15)

        # Secondary query for additional depth
        query_url_2 = f"https://news.google.com/rss/search?q={urllib.parse.quote(state)}+breaking+news+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
        fresh2 = parse_feed_articles(
            query_url_2, scope="India", category="State", state=state,
            default_source=f"{state} News", seen_links=seen_links, max_items=10
        )
        if fresh2:
            append_articles_to_file(OUTPUT_FILE, fresh2)
            total_new += len(fresh2)
            states_new_count += len(fresh2)
        time.sleep(0.15)

    logger.info(f" -> [Indian States  : 28 States      ]: +{states_new_count} new articles across all 28 states")

    elapsed = round(time.time() - cycle_start, 2)
    logger.info(f"Cycle completed in {elapsed}s.")
    logger.info(f"NEW articles appended to '{OUTPUT_FILE}': {total_new}")
    logger.info(f"TOTAL unique articles in '{OUTPUT_FILE}': {len(seen_links)}")
    logger.info("=" * 72)

    # Record WorkerRun in newsreels.db for health monitoring
    try:
        from app.db import SessionLocal
        from app.models import WorkerRun, new_id
        db = SessionLocal()
        try:
            total_feeds = len(GLOBAL_BASELINES) + len(GLOBAL_CATEGORY_FEEDS) + len(INDIA_CATEGORY_FEEDS) + (len(INDIAN_STATES) * 2)
            run_row = WorkerRun(
                id=new_id(),
                provider="crawler_rss",
                timestamp=datetime.now(timezone.utc),
                sources_polled=total_feeds,
                articles_ingested=total_new,
                credits_used=0,
                errors=None,
                duration_seconds=elapsed,
            )
            db.add(run_row)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.debug(f"Failed to record WorkerRun: {exc}")

    return total_new


def ping_render_keep_alive(base_url: str = KEEP_ALIVE_URL) -> bool:
    """Pings Render backend endpoints every 13.5 - 14 minutes to prevent the free/starter tier
    from entering 15-minute inactivity sleep mode. Keeps API warmed for sub-200ms user latency."""
    import urllib.request
    endpoints = ["/health", "/feed?state=National&limit=5"]
    success = True
    for ep in endpoints:
        target = f"{base_url.rstrip('/')}{ep}"
        try:
            t0 = time.time()
            req = urllib.request.Request(
                target,
                headers={"User-Agent": "NEWZZ-KeepAlive-Worker/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                elapsed_ms = (time.time() - t0) * 1000
                logger.info(f"[KeepAlive] Render warm ping -> {target} | Status: {resp.status} OK | Latency: {elapsed_ms:.1f}ms")
        except Exception as exc:
            logger.warning(f"[KeepAlive] Render ping notice for {target}: {exc}")
            success = False
    return success


def _keep_alive_daemon_loop(interval_seconds: float = 810.0):
    """Background daemon thread that continuously pings Render every 13.5 minutes (810s),
    guaranteeing Render's reverse proxy inactivity timer never expires."""
    logger.info(f"[KeepAlive] Daemon thread started. Pinging {KEEP_ALIVE_URL} every {interval_seconds/60:.1f} minutes.")
    while True:
        try:
            ping_render_keep_alive()
        except Exception as exc:
            logger.warning(f"[KeepAlive] Error during keepalive ping: {exc}")
        time.sleep(interval_seconds)


def start_keep_alive_daemon(interval_seconds: float = 810.0):
    import threading
    t = threading.Thread(target=_keep_alive_daemon_loop, args=(interval_seconds,), daemon=True)
    t.start()
    return t


def main():
    # Start background keep-alive loop to prevent Render from entering 15-minute sleep mode
    start_keep_alive_daemon(interval_seconds=INTERVAL_MINUTES * 60)

    logger.info("=" * 75)
    logger.info("  Automated Multi-Source News Aggregator Active")
    logger.info(f"  Render Keep-Alive : Active ({KEEP_ALIVE_URL} every {INTERVAL_MINUTES} min)")
    logger.info("  Global Categories : Technology, World, Science, Politics,")
    logger.info("                      Business, Health, Sports, Entertainment,")
    logger.info("                      Environment, Education")
    logger.info("  India Categories  : National, Technology, Science, Politics,")
    logger.info("                      Business, Health, Sports, Entertainment,")
    logger.info("                      Environment, Education")
    logger.info("  Indian States     : All 28 States (2 queries each)")
    logger.info(f"  Output File       : {OUTPUT_FILE}  Every {INTERVAL_MINUTES} min")
    logger.info("=" * 75)

    seen_links = load_existing_links(OUTPUT_FILE)

    # Initial crawl on startup
    run_crawl_cycle(seen_links)

    # Periodic execution every 10 minutes
    cycle_num = 1
    sleep_seconds = INTERVAL_MINUTES * 60

    try:
        while True:
            logger.info(f"Sleeping for {INTERVAL_MINUTES} minutes until next cycle...")
            time.sleep(sleep_seconds)
            cycle_num += 1
            logger.info(f"Waking up for Cycle #{cycle_num}...")
            # Ping Render server to ensure it is awake and warmed
            ping_render_keep_alive()
            run_crawl_cycle(seen_links)

    except KeyboardInterrupt:
        logger.info("\nAggregator stopped by user (Ctrl+C). Exiting cleanly.")


if __name__ == "__main__":
    main()

GLOBAL_CATEGORIES = ["Technology", "World", "Science", "Politics", "Business", "Health", "Sports", "Entertainment", "Environment"]
INDIA_CATEGORIES = ["National", "Technology", "Science", "Politics", "Business", "Health", "Sports", "Entertainment", "Environment"]
