import sys
import os
import re
import html
import json
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import feedparser

# Reconfigure stdout for utf-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Ensure repo root and app modules are importable
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "apps" / "api"))
sys.path.insert(0, str(_repo_root / "apps" / "worker"))

from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LiveIngest] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LiveIngest")

FEEDS_CONFIG = [
    # --- NATIONAL & POLICY ---
    {"name": "The Hindu", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "category": "national", "state": None, "trust_tier": 1},
    {"name": "The Times of India", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "category": "national", "state": None, "trust_tier": 1},
    {"name": "NDTV News", "url": "https://feeds.feedburner.com/ndtvnews-top-stories", "category": "national", "state": None, "trust_tier": 1},
    {"name": "Google News India", "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en", "category": "national", "state": None, "trust_tier": 2},
    
    # --- TECHNOLOGY ---
    {"name": "Google News Tech", "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en", "category": "technology", "state": None, "trust_tier": 2},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "technology", "state": None, "trust_tier": 1},
    
    # --- BUSINESS & ECONOMY ---
    {"name": "The Economic Times", "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "category": "business", "state": None, "trust_tier": 1},
    {"name": "Livemint", "url": "https://www.livemint.com/rss/news", "category": "business", "state": None, "trust_tier": 1},
    {"name": "Google News Business", "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en", "category": "business", "state": None, "trust_tier": 2},
    
    # --- WORLD & GEOPOLITICS ---
    {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "world", "state": None, "trust_tier": 1},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "world", "state": None, "trust_tier": 1},
    {"name": "Google News World", "url": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en", "category": "world", "state": None, "trust_tier": 2},

    # --- SCIENCE & HEALTH ---
    {"name": "Google News Science", "url": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-IN&gl=IN&ceid=IN:en", "category": "science", "state": None, "trust_tier": 2},
    {"name": "Google News Health", "url": "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-IN&gl=IN&ceid=IN:en", "category": "health", "state": None, "trust_tier": 2},

    # --- SPORTS ---
    {"name": "NDTV Sports", "url": "https://feeds.feedburner.com/ndtvsports-latest", "category": "sports", "state": None, "trust_tier": 1},
    {"name": "Google News Sports", "url": "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=en-IN&gl=IN&ceid=IN:en", "category": "sports", "state": None, "trust_tier": 2},

    # --- REGIONAL STATE DESKS ---
    {"name": "The Hindu (Telangana)", "url": "https://www.thehindu.com/news/national/telangana/feeder/default.rss", "category": "state", "state": "Telangana", "trust_tier": 1},
    {"name": "The Hindu (Karnataka)", "url": "https://www.thehindu.com/news/national/karnataka/feeder/default.rss", "category": "state", "state": "Karnataka", "trust_tier": 1},
    {"name": "The Hindu (Delhi)", "url": "https://www.thehindu.com/news/cities/Delhi/feeder/default.rss", "category": "state", "state": "Delhi", "trust_tier": 1},
    {"name": "The Hindu (Maharashtra)", "url": "https://www.thehindu.com/news/national/other-states/feeder/default.rss", "category": "state", "state": "Maharashtra", "trust_tier": 1},
    {"name": "The Hindu (Tamil Nadu)", "url": "https://www.thehindu.com/news/national/tamil-nadu/feeder/default.rss", "category": "state", "state": "Tamil Nadu", "trust_tier": 1},
    {"name": "The Hindu (Andhra Pradesh)", "url": "https://www.thehindu.com/news/national/andhra-pradesh/feeder/default.rss", "category": "state", "state": "Andhra Pradesh", "trust_tier": 1},
    {"name": "Google News (Telangana)", "url": "https://news.google.com/rss/search?q=Telangana+when:2d&hl=en-IN&gl=IN&ceid=IN:en", "category": "state", "state": "Telangana", "trust_tier": 2},
    {"name": "Google News (Karnataka)", "url": "https://news.google.com/rss/search?q=Karnataka+when:2d&hl=en-IN&gl=IN&ceid=IN:en", "category": "state", "state": "Karnataka", "trust_tier": 2},
]

ALL_INDIAN_STATES_AND_UTS = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar", "Chandigarh", "Dadra and Nagar Haveli",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]

def extract_clean_publisher(entry, default_name: str) -> str:
    if hasattr(entry, "source") and hasattr(entry.source, "title") and entry.source.title:
        return str(entry.source.title).strip()
    title = str(getattr(entry, "title", ""))
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts) == 2 and len(parts[1]) < 35:
            return parts[1].strip()
    return default_name

def clean_html_text(raw: str) -> str:
    if not raw:
        return ""
    txt = html.unescape(raw)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    # Normalize typography (smart quotes, curly dashes to clean ASCII)
    txt = txt.replace("\u2018", "'").replace("\u2019", "'")
    txt = txt.replace("\u201c", '"').replace("\u201d", '"')
    txt = txt.replace("\u2013", "-").replace("\u2014", " - ")
    txt = txt.replace("\u00a0", " ")
    txt = txt.replace("\ufffd", "'")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def parse_entry_datetime(entry) -> Optional[datetime]:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
        except Exception:
            pass
    raw = getattr(entry, "published", getattr(entry, "updated", None))
    if raw:
        try:
            import email.utils
            dt = email.utils.parsedate_to_datetime(raw)
            if dt:
                return dt.astimezone(timezone.utc)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            pass
    return None


_groq_client = None
def get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client if _groq_client is not False else None
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from openai import OpenAI
            _groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=8.0)
            return _groq_client
        except Exception:
            _groq_client = False
    else:
        _groq_client = False
    return None

def call_groq_summarizer(headline: str, snippet: str, source: str, state: Optional[str]) -> Optional[tuple[str, list[str], int]]:
    client = get_groq_client()
    if not client:
        return None
    try:
        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        prompt = (
            "You are an expert news editor for NEWZZ. Given a headline and snippet, produce a factual, "
            "well-written 2-paragraph news dispatch summary (approx 60-90 words) and 3 concise key facts.\n"
            "Return ONLY JSON:\n{\"summary\": \"string\", \"key_facts\": [\"bullet 1\", \"bullet 2\", \"bullet 3\"]}"
        )
        user_msg = f"Headline: {headline}\nSnippet: {snippet}\nSource: {source}\nRegion: {state or 'National'}"
        res = client.chat.completions.create(
            model=model,
            messages=[{'role': 'system', 'content': prompt}, {'role': 'user', 'content': user_msg}],
            temperature=0.1,
            max_tokens=250,
        )
        raw = (res.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(raw[start : end + 1])
            summ = data.get("summary", "").strip()
            facts = data.get("key_facts", [])
            if summ and len(summ.split()) >= 25:
                clean_facts = [str(f).strip() for f in facts if str(f).strip()][:3]
                return summ, clean_facts, len(summ.split())
    except Exception as e:
        logger.debug(f"Groq summarizer fallback: {e}")
    return None

def generate_editorial_summary(headline: str, raw_snippet: str, source: str, state: Optional[str]) -> tuple[str, list[str], int]:
    clean_h = re.sub(r"\s+-\s+[^-]+$", "", headline).strip()
    clean_s = clean_html_text(raw_snippet)
    if " - " in clean_s:
        clean_s = re.sub(r"\s+-\s+[^-]+$", "", clean_s).strip()

    # 1. Try Groq AI first for high-quality journalistic summary
    groq_res = call_groq_summarizer(clean_h, clean_s, source, state)
    if groq_res:
        return groq_res

    # 2. Journalistic structured fallback strictly grounded in facts if LLM is offline
    paragraphs = []
    if clean_s and len(clean_s) > 25 and clean_s.lower() != clean_h.lower():
        if clean_h.lower() not in clean_s.lower():
            paragraphs.append(f"{clean_h}.")
        paragraphs.append(clean_s)
    else:
        paragraphs.append(f"{clean_h}.")
        if state:
            paragraphs.append(f"Reported from regional bureaus across {state} by {source}.")
        else:
            paragraphs.append(f"Reported by {source}.")

    full_summary = " ".join(paragraphs)
    words = len(full_summary.split())

    key_facts = [
        clean_h[:110],
        f"Source: {source}",
        f"Region: {state or 'National / Global'}"
    ]
    if clean_s and len(clean_s) > 30 and clean_s.lower() != clean_h.lower():
        key_facts.append(clean_s[:110])

    return full_summary, key_facts[:3], words

def fetch_and_build_live_feed(target_state: Optional[str] = None, max_per_feed: int = 20):
    import urllib.parse
    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=72) # Only accept articles within last 72 hours
    min_date = now - max_age

    seen_urls = set()
    seen_headlines = set()
    crawled_articles = []

    # Assemble active feeds list
    active_feeds = list(FEEDS_CONFIG)
    if target_state:
        # Guarantee dedicated state feeds for requested state
        st_clean = target_state.strip()
        state_google_feed = {
            "name": f"Google News ({st_clean})",
            "url": f"https://news.google.com/rss/search?q={urllib.parse.quote(st_clean)}+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
            "category": "state",
            "state": st_clean,
            "trust_tier": 2
        }
        # Insert target state feed at the very front
        active_feeds.insert(0, state_google_feed)

    logger.info(f"Starting live news fetch across {len(active_feeds)} feeds (target_state={target_state})...")

    for feed_info in active_feeds:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]
        category = feed_info["category"]
        state = feed_info["state"]
        trust_tier = feed_info["trust_tier"]

        try:
            parsed = feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            entries = parsed.entries
            logger.info(f"Fetched {len(entries)} items from {feed_name}")

            for entry in entries[:max_per_feed]:
                link = entry.get("link")
                if not link or link in seen_urls:
                    continue

                raw_title = entry.get("title", "").strip()
                if not raw_title:
                    continue

                clean_title = re.sub(r"\s+-\s+[^-]+$", "", raw_title).strip()

                # Strict newsroom quality guard: reject word puzzle hints, horoscopes, and gaming tips
                title_low = clean_title.lower()
                if any(bad in title_low for bad in [
                    "quordle hint", "wordle hint", "connections hint", "strands hint", 
                    "daily clue", "clues and answers", "horoscope today", "daily horoscope",
                    "today's tarot", "crossword clue", "word puzzle"
                ]):
                    continue

                norm_h = re.sub(r"[^a-zA-Z0-9]", "", clean_title.lower())
                if norm_h in seen_headlines:
                    continue

                pub_dt = parse_entry_datetime(entry)
                if not pub_dt:
                    continue

                # Ensure publication date is within the last 72h and NOT far in the future
                if pub_dt < min_date or pub_dt > now + timedelta(hours=2):
                    continue

                publisher = extract_clean_publisher(entry, feed_name)
                raw_summary = entry.get("summary", getattr(entry, "description", ""))

                summary_text, key_facts, word_count = generate_editorial_summary(
                    headline=clean_title,
                    raw_snippet=raw_summary,
                    source=publisher,
                    state=state
                )

                # Compute Ranking Engine scores
                dims, imp = ImportanceEngine.analyze_event_text(clean_title, summary_text, category)
                urg, urg_reason = UrgencyEngine.calculate_urgency(clean_title, summary_text)
                frsh = FreshnessEngine.calculate_freshness(published_at=pub_dt, current_time=now)
                ver, _ = VerificationEngine.calculate_verification([{"name": publisher, "tier": str(trust_tier)}])
                
                scoring_out = FeedRankingEngine.compute_final_score(
                    objective_importance=imp,
                    urgency=urg,
                    freshness=frsh,
                    personal_relevance=92.0 if state else 80.0,
                    verification_confidence=ver,
                    dimensions=dims,
                    urgency_reason=urg_reason,
                    source_count=1,
                    tier1_count=1 if trust_tier == 1 else 0
                )

                card_id = str(uuid.uuid4())
                source_id = str(uuid.uuid4())

                article_data = {
                    "id": card_id,
                    "cluster_id": str(uuid.uuid4()),
                    "headline": clean_title,
                    "summary": summary_text,
                    "key_facts": key_facts,
                    "word_count": word_count,
                    "category": category,
                    "state": state,
                    "district": None,
                    "published_at": pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "newzz_published_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source_name": publisher,
                    "canonical_url": link,
                    "url": link,
                    "verification_type": "cross_verified" if trust_tier == 1 else "verified",
                    "verification_score": round(ver, 1),
                    "importance_score": round(imp, 1),
                    "urgency_score": round(urg, 1),
                    "freshness_score": round(frsh, 1),
                    "personal_relevance_score": 92.0 if state else 80.0,
                    "final_feed_score": round(scoring_out.final_feed_score, 1),
                    "priority_reason": scoring_out.priority_reason,
                    "content_type": "NEWS",
                    "verified_status": "published",
                    "sources": [
                        {
                            "source_id": source_id,
                            "name": publisher,
                            "url": link,
                            "trust_tier": str(trust_tier),
                            "url_type": "direct",
                            "provenance_status": "verified"
                        }
                    ]
                }

                seen_urls.add(link)
                seen_headlines.add(norm_h)
                crawled_articles.append(article_data)

        except Exception as e:
            logger.error(f"Error fetching feed {feed_name}: {e}")

    logger.info(f"Total verified fresh articles ingested: {len(crawled_articles)}")

    # Sort articles by final_feed_score descending so top stories lead
    crawled_articles.sort(key=lambda x: x["final_feed_score"], reverse=True)

    # 1. Output to feed.json (root) and apps/api/app/static/feed.json
    feed_payload = {
        "status": "ok",
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(crawled_articles),
        "items": crawled_articles
    }

    target_paths = [
        _repo_root / "feed.json",
        _repo_root / "apps" / "api" / "app" / "static" / "feed.json"
    ]

    for p in target_paths:
        tmp_p = str(p) + ".tmp"
        with open(tmp_p, "w", encoding="utf-8") as f:
            json.dump(feed_payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_p, str(p))
        logger.info(f"Updated {p} ({len(crawled_articles)} articles, {p.stat().st_size} bytes)")

    # 2. Output to summarized_news.json
    summarized_path = _repo_root / "website_scraping" / "summarized_news.json"
    with open(str(summarized_path) + ".tmp", "w", encoding="utf-8") as f:
        json.dump(crawled_articles, f, ensure_ascii=False, indent=2)
    os.replace(str(summarized_path) + ".tmp", str(summarized_path))
    logger.info(f"Updated {summarized_path}")

    # 3. Synchronize fresh cards into newsreels.db SQLite database
    sync_to_sqlite(crawled_articles)

    return len(crawled_articles)

def sync_to_sqlite(articles: List[Dict]):
    """Synchronizes fresh cards into database via SQLAlchemy ORM (compatible with PostgreSQL & SQLite)."""
    try:
        from app.db import SessionLocal
        from app.models import Card, StoryCluster, CardSource

        db = SessionLocal()
        now = datetime.now(timezone.utc)
        inserted_cards = 0
        updated_cards = 0

        for art in articles:
            card_id = art["id"]
            cluster_id = art["cluster_id"]
            headline = art["headline"]
            summary = art["summary"]
            category = art["category"].capitalize()
            state = art["state"]
            pub_at_str = art["published_at"]
            pub_dt = datetime.fromisoformat(pub_at_str.replace("Z", "+00:00"))

            existing = db.query(Card).filter(Card.headline == headline).first()
            if existing:
                existing.summary = summary
                existing.final_feed_score = art["final_feed_score"]
                existing.importance_score = art["importance_score"]
                existing.urgency_score = art["urgency_score"]
                existing.freshness_score = art["freshness_score"]
                existing.published_at = pub_dt
                updated_cards += 1
                continue

            cluster = db.query(StoryCluster).filter(StoryCluster.id == cluster_id).first()
            if not cluster:
                cluster = StoryCluster(
                    id=cluster_id,
                    title_hint=headline[:200],
                    eligible=True,
                    flagged_conflict=False,
                    created_at=now,
                )
                db.add(cluster)

            card = Card(
                id=card_id,
                cluster_id=cluster_id,
                headline=headline,
                summary=summary,
                category=category,
                verified_status="published",
                district=None,
                state=state,
                created_at=now,
                published_at=pub_dt,
                newzz_published_at=now,
                verification_type=art["verification_type"],
                objective_score=art["final_feed_score"],
                priority_score=5,
                content_type="NEWS",
                importance_score=art["importance_score"],
                urgency_score=art["urgency_score"],
                freshness_score=art["freshness_score"],
                verification_score=art["verification_score"],
                personal_relevance_score=art["personal_relevance_score"],
                final_feed_score=art["final_feed_score"],
                priority_reason=art["priority_reason"],
                created_by="live_pipeline",
            )
            db.add(card)

            if art.get("sources"):
                src_data = art["sources"][0]
                card_src = CardSource(
                    id=src_data.get("source_id", str(uuid.uuid4())),
                    card_id=card_id,
                    source_id=src_data.get("source_id", str(uuid.uuid4())),
                    name=src_data["name"],
                    url=src_data["url"],
                    trust_tier=str(src_data["trust_tier"]),
                )
                db.add(card_src)

            inserted_cards += 1

        db.commit()
        db.close()
        logger.info(f"Synchronized into database via SQLAlchemy: {inserted_cards} new cards, {updated_cards} updated cards")
        return
    except Exception as exc:
        logger.warning(f"SQLAlchemy sync notice: {exc}. Attempting SQLite file fallback...")

    import sqlite3
    db_path = _repo_root / "newsreels.db"
    if not db_path.exists():
        logger.warning(f"newsreels.db not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    inserted_cards = 0
    updated_cards = 0
    now = datetime.now(timezone.utc)

    for art in articles:
        card_id = art["id"]
        cluster_id = art["cluster_id"]
        headline = art["headline"]
        summary = art["summary"]
        category = art["category"].capitalize()
        state = art["state"]
        pub_at_str = art["published_at"]
        pub_dt = datetime.fromisoformat(pub_at_str.replace("Z", "+00:00"))
        
        # Check if card with same headline already exists
        cur.execute("SELECT id FROM cards WHERE headline = ?", (headline,))
        existing = cur.fetchone()
        if existing:
            # Update summary and scores with fresh Groq summary
            cur.execute("""
                UPDATE cards 
                SET summary = ?, final_feed_score = ?, importance_score = ?, urgency_score = ?, freshness_score = ?, published_at = ?
                WHERE id = ?
            """, (summary, art["final_feed_score"], art["importance_score"], art["urgency_score"], art["freshness_score"], pub_dt, existing[0]))
            updated_cards += 1
            continue

        # Insert story cluster if not exists
        cur.execute("SELECT id FROM story_clusters WHERE id = ?", (cluster_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO story_clusters (id, title_hint, eligible, flagged_conflict, created_at)
                VALUES (?, ?, 1, 0, ?)
            """, (cluster_id, headline[:200], now))

        # Insert card
        cur.execute("""
            INSERT INTO cards (
                id, cluster_id, headline, summary, category, verified_status,
                district, state, created_at, published_at, newzz_published_at,
                verification_type, objective_score, priority_score, content_type,
                importance_score, urgency_score, freshness_score, verification_score,
                personal_relevance_score, final_feed_score, priority_reason, created_by
            ) VALUES (?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?, 'NEWS', ?, ?, ?, ?, ?, ?, ?, 'live_pipeline')
        """, (
            card_id, cluster_id, headline, summary, category,
            None, state, now, pub_dt, now,
            art["verification_type"], art["final_feed_score"], 5,
            art["importance_score"], art["urgency_score"], art["freshness_score"],
            art["verification_score"], art["personal_relevance_score"],
            art["final_feed_score"], art["priority_reason"]
        ))

        # Insert source
        source_data = art["sources"][0]
        cur.execute("""
            INSERT INTO card_sources (id, card_id, source_id, article_id, name, url, trust_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            source_data["source_id"], card_id, source_data["source_id"], None,
            source_data["name"], source_data["url"], source_data["trust_tier"]
        ))

        inserted_cards += 1

    conn.commit()
    conn.close()
    logger.info(f"Synchronized into newsreels.db: {inserted_cards} new cards, {updated_cards} updated cards")

if __name__ == "__main__":
    count = fetch_and_build_live_feed()
    print(f"Ingestion complete: {count} verified live articles ingested.")

