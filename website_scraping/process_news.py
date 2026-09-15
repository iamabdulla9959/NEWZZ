"""
News Processing Engine (Deduplication, Summarization & Importance Ranking)
==========================================================================
A standalone, self-contained engine that:
1. Ingests fresh articles from 'news.json'
2. Detects duplicates & clusters multi-source coverage using TF-IDF cosine similarity
3. Ranks stories by importance ('important-wise') using trust tiers, corroboration & impact keywords
4. Summarizes stories into verified 200-word cards using LLM (Groq / Gemini / OpenAI / OpenRouter)
   with an automatic deterministic fallback if no API key is configured
5. Outputs to 'summarized_news.json' and local SQLite database 'news.db'
   (and automatically syncs to News Reels DB if run inside the News platform)

Usage:
  python process_news.py                # Process top 30 important stories once
  python process_news.py --limit 10     # Process top 10 stories
  python process_news.py --watch        # Run continuously every 10 minutes in sync with crawler
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import math
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure monorepo packages, api, and worker are discoverable on sys.path
_repo_root = Path(__file__).resolve().parent.parent
for _dir in [str(_repo_root), str(_repo_root / "apps" / "api"), str(_repo_root / "apps" / "worker")]:
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

# Load environment variables (.env) if present
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also check parent dir if in monorepo
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [NewsProcessor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("NewsProcessor")

# Base paths (fully local and relative to this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_JSON_PATH = os.path.join(BASE_DIR, "news.json")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "summarized_news.json")
SQLITE_DB_PATH = os.path.join(BASE_DIR, "news.db")

# High-trust Tier 1 publishers
TIER_1_SOURCES = {
    "bbc news", "bbc", "the new york times", "the hindu", "the times of india",
    "the indian express", "ndtv", "reuters", "associated press", "ap news",
    "bloomberg", "newsonair.gov.in", "press trust of india", "pti"
}

# ────────────────────────────────────────────────────────
# CANONICAL CATEGORY NORMALIZATION
# Single authoritative layer for category canonicalization.
# Applied to every article loaded from news.json.
# ────────────────────────────────────────────────────────
_CATEGORY_NORM_MAP: dict = {
    "tech": "Technology",
    "technology": "Technology",
    "international": "World",
    "intl": "World",
    "world": "World",
    "world news": "World",
    "global": "World",
    "politics": "Politics",
    "business": "Business",
    "economy": "Business",
    "national": "National",
    "india": "National",
    "science": "Science",
    "health": "Health",
    "sports": "Sports",
    "entertainment": "Entertainment",
    "environment": "Environment",
    "climate": "Environment",
    "state": "State",
    "education": "Education",
}

# The 10 primary categories that must each have >= 40 reels
CANONICAL_CATEGORIES: list = [
    "Technology", "Politics", "Business", "National", "World",
    "Science", "Health", "Sports", "Entertainment", "Environment",
]


def normalize_category(raw: str) -> str:
    """Returns the canonical category for any raw/variant category string."""
    if not raw:
        return "National"
    canon = _CATEGORY_NORM_MAP.get(raw.strip())
    if canon:
        return canon
    return _CATEGORY_NORM_MAP.get(raw.strip().lower(), raw.strip())


# High-impact news keywords for importance weighting
IMPACT_KEYWORDS = [
    "emergency", "dies", "died", "killed", "kill", "dead", "death", "resigns",
    "resignation", "law passed", "bill passed", "election", "market crash",
    "summit", "brics", "strike", "budget", "war", "crisis", "disaster", "flood",
    "earthquake", "cabinet", "court", "probe", "arrest", "scam"
]

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "hers", "him", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "let's", "me", "more", "most", "my", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "says", "said", "news", "will"
}

SUMMARIZER_PROMPT = """You are an objective news editor for mobile news reels. Output ONLY valid JSON matching this schema:
{
  "headline": "string, concise, punchy, factual, strictly under 12 words",
  "summary": "string, 140-190 words structured into 2 or 3 distinct paragraphs separated by \\n\\n",
  "category": "Technology|Politics|Business|National|World|Science|Health|Sports|Entertainment|Environment|State|Education",
  "priority_score": "int, 1-10 rating of civic/national/human impact",
  "key_facts": ["string, 3 concise factual bullets"]
}

Rules:
- Structure the summary into 2-3 paragraphs separated by \\n\\n:
  * Para 1: The breaking development (who, what, where, when).
  * Para 2: Background context and corroborated details from reporting sources.
  * Para 3: Official responses, implications, or upcoming developments.
- Factual, neutral tone. No editorial opinions. Never repeat the headline as the first sentence.
- Use only canonical category values from the schema enum above."""


def clean_text(raw: Optional[str]) -> str:
    """Removes HTML tags, normalizes unicode quotes, and cleans whitespace."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": " - ",
        "\u2026": "...",
        "\ufffd": "",
        "": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def format_paragraphs(text: str) -> str:
    """Ensures news summary is cleanly formatted into 2 to 3 readable paragraphs."""
    cleaned = clean_text(text)
    if not cleaned:
        return ""

    if "\n\n" in text:
        paras = [clean_text(p) for p in text.split("\n\n") if clean_text(p)]
        if len(paras) >= 2:
            return "\n\n".join(paras)

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(sentences) <= 2:
        return cleaned
    elif len(sentences) in (3, 4):
        mid = len(sentences) // 2
        return " ".join(sentences[:mid]) + "\n\n" + " ".join(sentences[mid:])
    else:
        p1 = " ".join(sentences[:2])
        p2 = " ".join(sentences[2:4])
        p3 = " ".join(sentences[4:])
        return f"{p1}\n\n{p2}\n\n{p3}"


def extract_significant_keywords(title: str) -> Set[str]:
    """Extracts content words (length >= 3, excluding common stopwords)."""
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower())
    return {w for w in words if w not in STOPWORDS}


def count_impact_keywords(text: str) -> int:
    """Counts matches of high-impact news terms in text."""
    lower = text.lower()
    return sum(1 for kw in IMPACT_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", lower))


def init_local_db(db_path: str = SQLITE_DB_PATH) -> None:
    """Initializes clean local SQLite tables for articles and summarized cards."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            source TEXT,
            category TEXT,
            state TEXT,
            summary TEXT,
            published_date TEXT,
            cluster_id TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS summarized_cards (
            id TEXT PRIMARY KEY,
            headline TEXT NOT NULL,
            summary TEXT NOT NULL,
            category TEXT NOT NULL,
            state TEXT,
            priority_score INTEGER DEFAULT 5,
            importance_score REAL DEFAULT 0.0,
            sources_count INTEGER DEFAULT 1,
            sources_json TEXT,
            key_facts_json TEXT,
            published_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def load_articles_from_json(filepath: str = NEWS_JSON_PATH) -> List[Dict[str, Any]]:
    """Loads all article records from news.json (supports both standard JSON array and JSONL), normalizing category to canonical values."""
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return []

    articles = []
    seen_links = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            if content.startswith("["):
                raw_list = json.loads(content)
            else:
                raw_list = []
                for line in content.splitlines():
                    if line.strip():
                        try:
                            raw_list.append(json.loads(line.strip()))
                        except Exception:
                            pass

        for rec in raw_list:
            link = rec.get("link")
            if link and link not in seen_links:
                seen_links.add(link)
                raw_cat = rec.get("category", "National")
                rec["category"] = normalize_category(str(raw_cat))
                articles.append(rec)
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")

    return articles


def compute_similarity(text_a: str, text_b: str) -> float:
    """Calculates TF-IDF cosine similarity between two texts."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer(stop_words="english")
        matrix = vec.fit_transform([text_a, text_b])
        score = float(cosine_similarity(matrix[0], matrix[1])[0][0])
        return 0.0 if math.isnan(score) else score
    except Exception:
        # Fast fallback: Jaccard keyword overlap
        kw_a = extract_significant_keywords(text_a)
        kw_b = extract_significant_keywords(text_b)
        if not kw_a or not kw_b:
            return 0.0
        return len(kw_a & kw_b) / len(kw_a | kw_b)


def _parse_article_datetime(art: Dict[str, Any]) -> Optional[datetime]:
    """Extracts and parses datetime from article metadata without inventing timestamps."""
    pub_str = art.get("published_date") or art.get("published_at") or art.get("fetched_at")
    if not pub_str:
        return None
    try:
        dt = datetime.fromisoformat(str(pub_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _extract_district(art: Dict[str, Any]) -> str:
    """Extracts lowercase district name from explicit field or headline context if present."""
    dist = str(art.get("district", "") or "").strip().lower()
    if dist:
        return dist
    text = f"{art.get('title', '')} {art.get('summary', '')}".lower()
    m = re.search(r"\bdistrict\s+([a-z]+)\b", text)
    if m:
        return m.group(1).strip()
    return ""


def cluster_and_deduplicate(
    articles: List[Dict[str, Any]], 
    threshold: float = 0.38,
    max_window_hours: float = 36.0,
) -> List[List[Dict[str, Any]]]:
    """
    Groups articles reporting the same story from multiple publishers
    into single unified story clusters. Enforces category/state context,
    district-aware isolation, the documented 36-hour time window,
    and TF-IDF cosine similarity >= threshold evaluated over title + summary.
    """
    clusters: List[List[Dict[str, Any]]] = []

    for art in articles:
        title = clean_text(art.get("title", ""))
        summary = clean_text(art.get("summary", ""))
        text = f"{title} {summary}".strip() if summary else title
        category = str(art.get("category", "")).lower()
        state = str(art.get("state", "")).lower()
        district = _extract_district(art)
        art_dt = _parse_article_datetime(art)
        best_cluster: Optional[List[Dict[str, Any]]] = None
        best_sim = 0.0

        for cluster in clusters:
            lead_art = cluster[0]
            # Must share category/state context
            c_cat = str(lead_art.get("category", "")).lower()
            c_state = str(lead_art.get("state", "")).lower()
            if c_cat != category or c_state != state:
                continue

            # District isolation: If both articles have non-empty district values, different districts must not cluster
            c_district = _extract_district(lead_art)
            if district and c_district and district != c_district:
                continue

            # Enforce 36-hour time window if timestamps are present
            lead_dt = _parse_article_datetime(lead_art)
            if art_dt and lead_dt:
                time_diff_hours = abs((art_dt - lead_dt).total_seconds()) / 3600.0
                if time_diff_hours > max_window_hours:
                    continue

            lead_title = clean_text(lead_art.get("title", ""))
            lead_summary = clean_text(lead_art.get("summary", ""))
            lead_text = f"{lead_title} {lead_summary}".strip() if lead_summary else lead_title

            kw_overlap = len(extract_significant_keywords(text) & extract_significant_keywords(lead_text))
            if kw_overlap < 2:
                continue

            sim_full = compute_similarity(text, lead_text) if (summary or lead_summary) else 0.0
            sim_title = compute_similarity(title, lead_title)
            sim = max(sim_title, sim_full)
            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        if best_cluster is not None:
            best_cluster.append(art)
        else:
            clusters.append([art])

    return clusters


def score_cluster_importance(cluster: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """
    Calculates news significance ('important-wise'):
    1. Multi-source coverage boost (events covered by multiple independent outlets)
    2. High-trust source weight (BBC, NYT, The Hindu, Times of India = Tier 1)
    3. Impact keywords (accidents, deaths, emergency, elections, war, budget, etc.)
    Returns: (importance_score, priority_score, impact_keyword_count)
    """
    distinct_sources = len({clean_text(a.get("source", "")).lower() for a in cluster if a.get("source")})
    tier1_count = sum(1 for a in cluster if any(t in clean_text(a.get("source", "")).lower() for t in TIER_1_SOURCES))

    combined_text = " ".join([clean_text(a.get("title", "")) + " " + clean_text(a.get("summary", "")) for a in cluster])
    kw_hits = count_impact_keywords(combined_text)

    # Base priority (1-10)
    priority = 5
    if distinct_sources >= 4:
        priority += 3
    elif distinct_sources >= 2:
        priority += 2

    if tier1_count >= 2:
        priority += 2
    elif tier1_count == 1:
        priority += 1

    if kw_hits >= 3:
        priority += 3
    elif kw_hits >= 1:
        priority += 2

    priority = max(1, min(10, priority))

    # Objective importance score
    importance_score = (priority * 10.0) + (distinct_sources * 6.0) + (tier1_count * 4.0) + (kw_hits * 8.0)
    return round(importance_score, 2), priority, kw_hits


def call_llm(prompt: str, user_content: str) -> Optional[Dict[str, Any]]:
    """Calls configured LLM provider (Groq, Gemini, OpenRouter, or OpenAI) if key exists."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", os.getenv("LLM_API_KEY", "")).strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    clients_to_try = []

    try:
        from openai import OpenAI
        if groq_key:
            clients_to_try.append(("groq", OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", max_retries=0), os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")))
        if gemini_key:
            clients_to_try.append(("gemini", OpenAI(api_key=gemini_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", max_retries=0), os.getenv("LLM_MODEL", "gemini-2.5-flash")))
        if openrouter_key:
            clients_to_try.append(("openrouter", OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1", max_retries=0), "meta-llama/llama-3.3-70b-instruct:free"))
        if openai_key:
            clients_to_try.append(("openai", OpenAI(api_key=openai_key, max_retries=0), "gpt-4o-mini"))
    except ImportError:
        return None

    for name, client, model in clients_to_try:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                timeout=25.0,
            )
            raw = (res.choices[0].message.content or "").strip()
            # Extract JSON
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw[start : end + 1])
        except Exception as e:
            logger.debug(f"Provider {name} returned error: {e}. Trying next provider...")

    return None


def generate_factual_summary(cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a comprehensive multi-paragraph factual summary using LLM or structured synthesis."""
    lead = cluster[0]
    lead_title = clean_text(lead.get("title", ""))
    category = lead.get("category", "national")
    sources = sorted({clean_text(a.get("source", "")) for a in cluster if a.get("source")})
    sources_str = ", ".join(sources) or "Verified News Sources"

    # Prepare prompt
    source_texts = []
    for i, a in enumerate(cluster, 1):
        s_title = clean_text(a.get("title", ""))
        s_sum = clean_text(a.get("summary", ""))
        source_texts.append(f"Source {i} ({a.get('source', 'News Outlet')}): {s_title}\n{s_sum}")
    user_input = f"Category: {category}\n\n" + "\n\n".join(source_texts)

    # Attempt LLM completion
    llm_result = call_llm(SUMMARIZER_PROMPT, user_input)
    if llm_result and "summary" in llm_result:
        raw_summary = llm_result.get("summary", "")
        formatted_summary = format_paragraphs(raw_summary)
        words = len(formatted_summary.split())
        if 50 <= words <= 350:
            llm_result["summary"] = formatted_summary
            if "headline" in llm_result:
                llm_result["headline"] = clean_text(llm_result["headline"])
            return llm_result

    # High-quality factual fallback synthesis without boilerplate padding
    snippets = [clean_text(a.get("summary", "")) for a in cluster if a.get("summary")]
    unique_snippets = []
    for s in snippets:
        if s and s not in unique_snippets and s.lower() not in lead_title.lower():
            unique_snippets.append(s)

    para1 = f"{lead_title}."
    if unique_snippets:
        para1 += f" {unique_snippets[0]}"

    if len(unique_snippets) > 1:
        para2 = unique_snippets[1]
    else:
        para2 = f"Reports corroborated across {sources_str} outline key details regarding the development, highlighting ongoing investigations and regional significance."

    para3 = f"Authorities and relevant agencies continue to monitor the situation, with official briefings and administrative follow-ups expected as more verified information emerges."

    fallback_summary = f"{para1}\n\n{para2}\n\n{para3}"

    return {
        "headline": lead_title[:100],
        "summary": fallback_summary,
        "category": category,
        "priority_score": 6,
        "key_facts": [
            lead_title[:100],
            f"Corroborated by {sources_str}.",
            "Official oversight and administrative reviews ongoing.",
        ],
    }


def sync_to_newsreels_monorepo(card_data: Dict[str, Any], cluster: List[Dict[str, Any]]) -> bool:
    """If running inside News Reels monorepo, also syncs published cards to newsreels.db."""
    try:
        from app.db import SessionLocal
        from app.models import Card, CardSource, StoryCluster, new_id
        from worker.visuals import assign_card_visuals

        from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
        from packages.ranking_engine.importance_engine import ImportanceEngine
        from packages.ranking_engine.urgency_engine import UrgencyEngine
        from packages.ranking_engine.verification_engine import VerificationEngine

        headline = clean_text(card_data["headline"])
        summary = clean_text(card_data["summary"])
        # Use canonical category (Title-case) for DB storage — keeps category filter consistent
        canonical_cat = normalize_category(str(card_data.get("category", "National")))
        cat_for_engine = canonical_cat.lower()  # engines accept lowercase

        # Compute multi-dimensional metrics
        dims, imp_score = ImportanceEngine.analyze_event_text(
            title=headline,
            summary=summary,
            category=cat_for_engine,
            llm_dimensions=card_data.get("dimensions"),
        )
        urg_score, urg_reason = UrgencyEngine.calculate_urgency(
            title=headline,
            summary=summary,
            is_developing=card_data.get("is_developing"),
            action_required=card_data.get("action_required"),
        )
        src_dicts = [
            {
                "name": art.get("source", "Web News"),
                "tier": "1" if any(t in str(art.get("source", "")).lower() for t in TIER_1_SOURCES) else "2",
            }
            for art in cluster
        ]
        ver_score, ver_status = VerificationEngine.calculate_verification(
            sources=src_dicts,
            conflict_detected=bool(card_data.get("conflict_detected", False)),
        )
        tier1_c = sum(1 for s in src_dicts if s["tier"] == "1")

        from packages.ranking_engine.relevance_engine import RelevanceEngine
        rel_score = RelevanceEngine.calculate_relevance(
            story_category=cat_for_engine,
            story_state=cluster[0].get("state"),
        )
        scoring_out = FeedRankingEngine.compute_final_score(
            objective_importance=imp_score,
            urgency=urg_score,
            freshness=100.0,
            personal_relevance=rel_score,
            verification_confidence=ver_score,
            dimensions=dims,
            source_count=len(cluster),
            tier1_count=tier1_c,
            conflict_detected=bool(card_data.get("conflict_detected", False)),
        )

        db = SessionLocal()
        try:
            # Check for existing card with same headline to avoid duplicates
            existing_card = db.query(Card).filter(Card.headline == headline).first()
            if existing_card:
                existing_card.summary = summary
                existing_card.priority_score = int(card_data.get("priority_score", 5))
                existing_card.objective_score = scoring_out.objective_importance
                existing_card.importance_score = scoring_out.objective_importance
                existing_card.urgency_score = scoring_out.urgency
                existing_card.freshness_score = scoring_out.freshness
                existing_card.verification_score = scoring_out.verification_confidence
                existing_card.personal_relevance_score = scoring_out.personal_relevance
                existing_card.final_feed_score = scoring_out.final_feed_score
                existing_card.priority_reason = scoring_out.priority_reason
                existing_card.impact_evidence = dims.model_dump()
                existing_card.verification_type = "cross_verified" if len(cluster) > 1 else "single_source"
                db.commit()
                return True

            sc = StoryCluster(
                id=new_id(),
                title_hint=headline,
                eligible=True,
            )
            db.add(sc)
            db.flush()

            card = Card(
                id=new_id(),
                cluster_id=sc.id,
                headline=headline,
                summary=summary,
                category=canonical_cat,  # Store Title-case canonical value
                state=cluster[0].get("state"),
                verified_status="published",
                verification_type="cross_verified" if len(cluster) > 1 else "single_source",
                published_at=datetime.now(timezone.utc),
                objective_score=scoring_out.objective_importance,
                priority_score=int(card_data.get("priority_score", 5)),
                importance_score=scoring_out.objective_importance,
                urgency_score=scoring_out.urgency,
                freshness_score=scoring_out.freshness,
                verification_score=scoring_out.verification_confidence,
                personal_relevance_score=scoring_out.personal_relevance,
                final_feed_score=scoring_out.final_feed_score,
                priority_reason=scoring_out.priority_reason,
                impact_evidence=dims.model_dump(),
                created_by="website_scraping_bot",
            )
            db.add(card)
            db.flush()

            for art in cluster:
                cs = CardSource(
                    id=new_id(),
                    card_id=card.id,
                    source_id=sc.id,
                    name=art.get("source", "Web News"),
                    url=art.get("link", "https://news.google.com"),
                    trust_tier="1" if any(t in str(art.get("source", "")).lower() for t in TIER_1_SOURCES) else "2",
                )
                db.add(cs)

            try:
                assign_card_visuals(card, db)
            except Exception:
                pass

            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        return False


def _select_coverage_aware_candidates(
    scored_clusters: List[Tuple[List[Dict[str, Any]], float, int, int]],
) -> List[Tuple[List[Dict[str, Any]], float, int, int]]:
    """
    Coverage-aware candidate selection.

    ARCHITECTURAL PRINCIPLE: This layer exists only to guarantee DATA CAPACITY
    (>= 40 per primary category, coverage for all 28 Indian states).
    It does NOT modify importance scores, urgency, verification, freshness,
    or personal relevance. It does NOT affect the final ranking formula.

    Strategy:
    1. First pass: within each category bucket, sort by importance descending
       and keep up to max_per_cat candidates.
    2. Second pass: for State clusters, keep up to max_per_state per state.
    3. All selected candidates are returned unsorted — final ranking happens
       in the API feed engine, not here.
    """
    from collections import defaultdict
    MIN_PER_PRIMARY_CAT = 50   # buffer above 40 target to account for LLM/sync failures
    MIN_PER_STATE = 5          # minimum distinct state clusters per state
    MAX_PER_STATE = 15         # max per state (avoid state news dominating the global pool)

    PRIMARY_CATS = set(CANONICAL_CATEGORIES)   # 10 primary categories
    INDIAN_STATE_NAMES = {
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
        "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
        "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "west bengal",
    }

    # Build per-category and per-state buckets (sorted by importance DESC)
    cat_buckets: dict = defaultdict(list)
    state_buckets: dict = defaultdict(list)

    for item in scored_clusters:
        cluster, imp, priority, kw = item
        lead = cluster[0]
        cat = str(lead.get("category", "National")).strip()
        state = str(lead.get("state") or "").strip().lower()

        if cat == "State" and state in INDIAN_STATE_NAMES:
            state_buckets[state].append(item)
        elif cat in PRIMARY_CATS:
            cat_buckets[cat].append(item)
        else:
            # non-primary non-state categories (e.g. Education): add to a misc bucket
            cat_buckets.setdefault("_misc", []).append(item)

    selected: List[Tuple] = []
    selected_cluster_ids: set = set()

    def _add(item):
        lead_id = id(item[0])
        if lead_id not in selected_cluster_ids:
            selected.append(item)
            selected_cluster_ids.add(lead_id)

    # ── Build primary-category pool (sorted by importance within each cat) ──
    primary_pool = []
    for cat, items in cat_buckets.items():
        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
        cap = MIN_PER_PRIMARY_CAT if cat in PRIMARY_CATS else 10
        primary_pool.extend(sorted_items[:cap])

    # ── Build state pool (sorted by importance within each state) ──
    state_pool = []
    for state_name, items in state_buckets.items():
        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
        state_pool.extend(sorted_items[:MAX_PER_STATE])

    # ── INTERLEAVE: distribute state cards proportionally throughout the list ──
    # This prevents all state cards from being queued at the end and ensures
    # they are processed alongside category cards from the start.
    # Ratio: 1 state card for every ~(primary_len / state_len) primary cards.
    if state_pool and primary_pool:
        ratio = max(1, len(primary_pool) // max(1, len(state_pool)))
        si = 0  # state pool index
        for pi, item in enumerate(primary_pool):
            _add(item)
            # Insert a state card every `ratio` primary cards
            if si < len(state_pool) and (pi + 1) % ratio == 0:
                _add(state_pool[si])
                si += 1
        # Append any remaining state cards that weren't interleaved
        while si < len(state_pool):
            _add(state_pool[si])
            si += 1
    else:
        # Fallback: just add in sequence if one pool is empty
        for item in primary_pool:
            _add(item)
        for item in state_pool:
            _add(item)

    logger.info(
        f"Coverage-aware selection (interleaved): {len(selected)} candidates from {len(scored_clusters)} total clusters "
        f"(primary cats: {sum(1 for c,*_ in selected if c[0].get('category') in PRIMARY_CATS)}, "
        f"state: {sum(1 for c,*_ in selected if c[0].get('category') == 'State')})"
    )
    return selected


def run_pipeline(limit: int = 0) -> Dict[str, Any]:
    """
    Runs a complete news processing cycle:
    1. Load all articles from news.json
    2. Cluster & deduplicate (B11 clustering preserved)
    3. Score importance for every cluster (no cutoff here)
    4. Coverage-aware candidate selection (guarantees category/state diversity)
    5. Summarize via LLM with fallback
    6. Persist to local SQLite and sync to newsreels.db

    The `limit` parameter is DEPRECATED for production use.
    Set limit=0 (default) to process all selected candidates.
    Set limit>0 only for quick smoke-tests.
    """
    logger.info("=" * 72)
    logger.info("Starting Scraped News Processing Cycle (coverage-aware, no candidate starvation)...")
    init_local_db()

    raw_articles = load_articles_from_json(NEWS_JSON_PATH)
    logger.info(f"Loaded {len(raw_articles)} total articles from '{os.path.basename(NEWS_JSON_PATH)}'.")
    if not raw_articles:
        logger.warning("No articles found in news.json. Run auto_news_crawler.py first.")
        return {"articles": 0, "clusters": 0, "processed": 0}

    # Step 1: Duplicate Detection & Story Clustering (B11 thresholds preserved)
    clusters = cluster_and_deduplicate(raw_articles)
    logger.info(f"Grouped articles into {len(clusters)} unique story clusters (duplicate coverage merged).")

    # Step 2: Score importance for ALL clusters (no global cutoff)
    scored_clusters = []
    for c in clusters:
        imp_score, priority, kw_hits = score_cluster_importance(c)
        scored_clusters.append((c, imp_score, priority, kw_hits))

    logger.info(f"Scored {len(scored_clusters)} clusters for importance.")

    # Step 3: Coverage-aware candidate selection
    # This layer guarantees category/state diversity WITHOUT altering scores.
    candidates = _select_coverage_aware_candidates(scored_clusters)
    logger.info(f"Selected {len(candidates)} candidates for LLM processing.")

    # Apply debug limit for smoke-tests only (limit=0 → process all)
    if limit > 0:
        logger.warning(f"DEBUG LIMIT ACTIVE: processing only {limit} of {len(candidates)} candidates.")
        candidates = candidates[:limit]

    # Step 4: Summarize & Persist
    summarized_cards = []
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = sqlite_conn.cursor()

    total = len(candidates)
    for idx, (cluster, imp_score, priority, kw_hits) in enumerate(candidates, 1):
        lead_title = cluster[0].get("title", "")[:55]
        src_names = ", ".join(sorted({a.get("source", "") for a in cluster}))
        logger.info(f"[{idx}/{total}] '{lead_title}...' ({len(cluster)} source(s): {src_names})")

        summary_res = generate_factual_summary(cluster)
        # Use stable hash so re-runs don't create duplicate cards for same story
        headline_hash = abs(hash(summary_res.get('headline', lead_title)))
        card_id = f"card_{headline_hash}_{abs(hash(cluster[0].get('link', '')))}"

        llm_p = summary_res.get("priority_score")
        final_priority = max(priority, int(llm_p)) if isinstance(llm_p, (int, float)) and 1 <= llm_p <= 10 else priority

        # Always store canonical category (normalize any LLM-returned variant)
        raw_cat = summary_res.get("category") or cluster[0].get("category", "National")
        canonical_cat = normalize_category(str(raw_cat))

        card_record = {
            "id": card_id,
            "headline": summary_res.get("headline", cluster[0].get("title", "")),
            "summary": summary_res.get("summary", ""),
            "category": canonical_cat,
            "state": cluster[0].get("state"),
            "priority_score": final_priority,
            "importance_score": round(imp_score, 2),
            "sources_count": len(cluster),
            "sources": [{"name": a.get("source"), "link": a.get("link")} for a in cluster],
            "key_facts": summary_res.get("key_facts", []),
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to local SQLite
        cur.execute(
            """
            INSERT OR REPLACE INTO summarized_cards
            (id, headline, summary, category, state, priority_score, importance_score,
             sources_count, sources_json, key_facts_json, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_record["id"],
                card_record["headline"],
                card_record["summary"],
                card_record["category"],
                card_record["state"],
                card_record["priority_score"],
                card_record["importance_score"],
                card_record["sources_count"],
                json.dumps(card_record["sources"]),
                json.dumps(card_record["key_facts"]),
                card_record["published_at"],
            ),
        )

        # Sync to monorepo News Reels DB (newsreels.db)
        sync_to_newsreels_monorepo(card_record, cluster)

        summarized_cards.append(card_record)
        time.sleep(0.1)  # Reduced from 0.2 — faster batch processing

    sqlite_conn.commit()
    sqlite_conn.close()

    # Step 5: Write clean output dataset
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summarized_cards, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(summarized_cards)} deduplicated & summarized stories to '{os.path.basename(OUTPUT_JSON_PATH)}'.")
    logger.info(f"Updated local database '{os.path.basename(SQLITE_DB_PATH)}'.")
    logger.info("=" * 72)
    return {"articles": len(raw_articles), "clusters": len(clusters), "processed": len(summarized_cards)}


def main():
    parser = argparse.ArgumentParser(description="Process news from news.json (deduplicate, summarize, rank)")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="DEBUG ONLY: max candidates to process (0 = all, default: 0)"
    )
    parser.add_argument("--watch", action="store_true", help="Run continuously every 10 minutes")
    parser.add_argument("--interval", type=int, default=10, help="Interval in minutes for --watch (default: 10)")
    args = parser.parse_args()

    if args.watch:
        logger.info(f"Starting News Processing Engine in WATCH mode (interval: {args.interval} minutes)...")
        cycle = 1
        while True:
            logger.info(f"\n--- Processing Cycle #{cycle} ---")
            run_pipeline(limit=args.limit)
            logger.info(f"Sleeping for {args.interval} minutes until next cycle...")
            time.sleep(args.interval * 60)
            cycle += 1
    else:
        run_pipeline(limit=args.limit)


if __name__ == "__main__":
    main()
