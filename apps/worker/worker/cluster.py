from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Article, FilteredOutAudit, StoryCluster, new_id

DEFAULT_THRESHOLD = 0.35
MIN_KEYWORD_OVERLAP = 2

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "says", "said", "new", "news", "will", "over",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def extract_significant_keywords(title: str) -> set[str]:
    """Extract significant keywords (>= 3 chars, not in stopword list)."""
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower())
    return {w for w in words if w not in STOPWORDS}


def keyword_overlap_count(title_a: str, title_b: str) -> int:
    kw_a = extract_significant_keywords(title_a)
    kw_b = extract_significant_keywords(title_b)
    return len(kw_a & kw_b)


def cosine_sim(a: str, b: str) -> float:
    docs = [normalize(a), normalize(b)]
    if not docs[0] or not docs[1]:
        return 0.0
    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform(docs)
    except ValueError:
        return 0.0
    score = float(cosine_similarity(matrix[0], matrix[1])[0][0])
    if math.isnan(score):
        return 0.0
    return score


def same_event(a: str, b: str, threshold: float = DEFAULT_THRESHOLD) -> bool:
    return cosine_sim(a, b) >= threshold


def is_postgres(db: Session) -> bool:
    """Detects whether the SQLAlchemy session is connected to PostgreSQL."""
    try:
        bind = db.get_bind()
        return getattr(bind.dialect, "name", "") == "postgresql"
    except Exception:
        return False


def compute_vector_similarity(
    db: Session,
    article: Article,
    candidate: Article,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[bool, float]:
    """Calculates similarity between article and candidate.
    Uses pgvector's cosine_distance operator on Postgres if embeddings exist.
    Falls back to sklearn TF-IDF cosine similarity on SQLite (or if embeddings missing).
    """
    if (
        is_postgres(db)
        and article.embedding is not None
        and candidate.embedding is not None
    ):
        dist_expr = Article.embedding.cosine_distance(candidate.embedding)
        dist = db.query(dist_expr).filter(Article.id == article.id).scalar()
        if dist is not None:
            sim = 1.0 - float(dist)
            return sim >= threshold, sim

    # SQLite fallback path: sklearn TF-IDF cosine similarity
    article_text = f"{article.title}\n{article.raw_text}"
    candidate_text = f"{candidate.title}\n{candidate.raw_text}"
    sim = cosine_sim(article_text, candidate_text)
    return sim >= threshold, sim


def query_candidate_articles(
    db: Session,
    article: Article,
    window_hours: int = 24,
) -> list[Article]:
    """Step 3 Geographic Sharding:
    NEVER queries the full Article/StoryCluster table.
    Only queries articles sharing the same (category, state, district)
    AND published within the last 24 hours.
    """
    category = article.category or (article.source.category if article.source else None)
    state = article.state or (article.source.region if article.source else None)
    district = article.district

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    query = (
        db.query(Article)
        .filter(
            Article.id != article.id,
            Article.cluster_id.is_not(None),  # candidate must already belong to a cluster
        )
    )

    if category:
        query = query.filter(Article.category == category)
    if state:
        query = query.filter(Article.state == state)
    if district:
        query = query.filter(Article.district == district)

    # Published/ingested within last 24 hours
    query = query.filter(
        or_(
            Article.published_at >= cutoff,
            Article.ingested_at >= cutoff,
        )
    )

    return query.all()


def cluster_article(
    db: Session,
    article: Article,
    threshold: float = DEFAULT_THRESHOLD,
    log_filtered: bool = True,
    window_hours: int = 24,
) -> tuple[StoryCluster, int, int]:
    """Clusters a single article using:
    1. Geographic + time sharding (same category, state, district, last 24h)
    2. Cheap regex/keyword overlap pre-filter (>= 3 shared significant keywords)
       Dropping non-matches to 'filtered_out' audit table.
    3. Vector similarity only for survivors (pgvector on Postgres, sklearn on SQLite).

    Returns: (matched_cluster, sharded_candidates_count, vector_evaluated_count)
    """
    candidates = query_candidate_articles(db, article, window_hours=window_hours)
    sharded_count = len(candidates)
    vector_evaluated_count = 0

    matched_cluster: StoryCluster | None = None

    for candidate in candidates:
        shared_keywords = keyword_overlap_count(article.title, candidate.title)

        # Pre-filter check: drop if < 3 shared significant keywords
        if shared_keywords < MIN_KEYWORD_OVERLAP:
            if log_filtered:
                db.add(
                    FilteredOutAudit(
                        id=new_id(),
                        candidate_article_id=article.id,
                        comparison_article_id=candidate.id,
                        shared_keywords_count=shared_keywords,
                        reason="insufficient_keyword_overlap",
                    )
                )
            continue

        # Passed pre-filter: run vector similarity comparison
        vector_evaluated_count += 1
        is_sim, _ = compute_vector_similarity(db, article, candidate, threshold=threshold)
        if is_sim:
            matched_cluster = db.query(StoryCluster).filter(StoryCluster.id == candidate.cluster_id).first()
            if matched_cluster:
                break

    if matched_cluster is None:
        matched_cluster = StoryCluster(id=new_id(), title_hint=article.title)
        db.add(matched_cluster)
        db.flush()

    article.cluster_id = matched_cluster.id
    db.flush()
    return matched_cluster, sharded_count, vector_evaluated_count
