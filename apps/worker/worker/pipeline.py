from __future__ import annotations

from datetime import datetime, timezone
import time

from sqlalchemy.orm import Session


from worker import paths  # noqa: F401

from app.models import (
    Article,
    Card,
    CardSource,
    ReviewQueueItem,
    StoryCluster,
    new_id,
)
from worker.cluster import DEFAULT_THRESHOLD, cluster_article
from worker.llm import LLMClient
from worker.summarize import judge_fact_consistency, summarize_articles
from worker.validate import matches_sensitivity, run_rule_checks
from worker.scoring import calculate_objective_score
from worker.visuals import assign_card_visuals
from worker.verify import (
    SourceRef,
    detect_numeric_conflicts,
    determine_verification_type,
    is_publish_eligible,
)


def cluster_unassigned_articles(
    db: Session,
    threshold: float = DEFAULT_THRESHOLD,
    log_filtered: bool = True,
) -> int:
    """Clusters unassigned articles using geographic sharding and title keyword pre-filtering."""
    unassigned = db.query(Article).filter(Article.cluster_id.is_(None)).all()
    assigned = 0
    for article in unassigned:
        cluster_article(db, article, threshold=threshold, log_filtered=log_filtered)
        assigned += 1
    db.commit()
    return assigned


def evaluate_cluster(db: Session, cluster: StoryCluster) -> None:
    articles = db.query(Article).filter(Article.cluster_id == cluster.id).all()
    if not articles:
        cluster.eligible = False
        cluster.flagged_conflict = False
        cluster.conflict_notes = []
        db.commit()
        return

    refs = [
        SourceRef(
            source_id=a.source_id,
            trust_tier=a.source.trust_tier,
            name=a.source.name,
            verified_local_source=bool(getattr(a.source, "verified_local_source", False)),
            wire_attribution=getattr(a, "wire_attribution", None),
            text=f"{a.title}\n{a.raw_text}",
            headline=a.title,
        )
        for a in articles
    ]
    category = (
        articles[0].category
        or (articles[0].source.category if articles and articles[0].source else "")
    )
    cluster.eligible = is_publish_eligible(refs, scope=category)
    numeric = _collect_numbers(articles)
    notes = detect_numeric_conflicts(numeric)
    cluster.flagged_conflict = bool(notes)
    cluster.conflict_notes = notes
    db.commit()


def process_eligible_clusters(db: Session, llm: LLMClient) -> list[str]:
    produced: list[str] = []
    clusters = db.query(StoryCluster).filter(StoryCluster.eligible.is_(True)).all()
    print(f"[Pipeline] Found {len(clusters)} eligible clusters to process", flush=True)
    for idx, cluster in enumerate(clusters):
        existing = (
            db.query(Card)
            .filter(Card.cluster_id == cluster.id, Card.verified_status != "rejected")
            .first()
        )
        if existing:
            continue
        articles = db.query(Article).filter(Article.cluster_id == cluster.id).all()
        if not articles:
            continue
        category = articles[0].source.category if articles else "national"
        title_snip = articles[0].title[:50] if articles else "Untitled"
        print(f"[Pipeline] [{idx+1}/{len(clusters)}] Summarizing: '{title_snip}' ({len(articles)} sources)...", flush=True)
        time.sleep(3.2)
        payload = [

            {
                "name": a.source.name,
                "title": a.title,
                "url": a.url,
                "text": a.raw_text,
            }
            for a in articles
        ]
        try:
            summary_json = summarize_articles(llm, payload, category_hint=category)
        except Exception as exc:  # fail closed
            card = _build_card(cluster, articles, {
                "headline": articles[0].title[:80] if articles else "Review needed",
                "summary": "",
                "category": category,
            })
            db.add(card)
            db.flush()
            _attach_sources(card, articles)
            db.add(
                ReviewQueueItem(
                    id=new_id(),
                    card_id=card.id,
                    reasons=[f"summarize_error:{exc}"],
                    source_excerpts=_excerpts(articles),
                    status="pending",
                )
            )
            card.verified_status = "pending_review"
            db.commit()
            produced.append(card.id)
            print(f"[Pipeline] -> Card queued (summarize_error): {exc}", flush=True)
            continue

        card = _build_card(cluster, articles, summary_json)
        db.add(card)
        db.flush()
        _attach_sources(card, articles)
        assign_card_visuals(card, db)

        reasons: list[str] = []
        if card.content_type != "NEWS":
            reasons.append(f"content_type:{card.content_type}")
        if cluster.flagged_conflict:
            reasons.append("flagged_conflict")
        combined = " ".join([card.headline, card.summary] + [a.title for a in articles])
        if matches_sensitivity(combined):
            reasons.append("sensitivity_keyword")

        rules = run_rule_checks(card.summary)
        reasons.extend(rules.reasons)

        # Fact consistency: use original_text when available to avoid lossy translation intermediates
        try:
            source_verifications = [
                f"{a.title}\n{a.original_text or a.raw_text}" for a in articles
            ]
            judge = judge_fact_consistency(llm, card.summary, source_verifications)
        except Exception as exc:  # fail closed
            judge = {"consistent": False, "issues": [f"judge_error:{exc}"]}
        if not judge.get("consistent"):
            reasons.extend([str(i) for i in judge.get("issues") or ["fact_inconsistent"]])

        if reasons:
            card.verified_status = "pending_review"
            db.add(
                ReviewQueueItem(
                    id=new_id(),
                    card_id=card.id,
                    reasons=reasons,
                    source_excerpts=_excerpts(articles),
                    status="pending",
                )
            )
            print(f"[Pipeline] -> Card queued: {reasons}", flush=True)
        else:
            card.verified_status = "published"
            card.published_at = datetime.now(timezone.utc)
            obj_score, impact_hits = calculate_objective_score(
                articles=articles,
                headline=card.headline,
                summary=card.summary,
                published_at=card.published_at,
                priority_score=card.priority_score,
            )
            card.objective_score = obj_score
            card.impact_keywords_count = impact_hits

            # Multi-Dimensional Ranking Engine Integration
            try:
                from packages.ranking_engine.importance_engine import ImportanceEngine
                from packages.ranking_engine.urgency_engine import UrgencyEngine
                from packages.ranking_engine.verification_engine import VerificationEngine
                from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine

                dims, imp_score = ImportanceEngine.analyze_event_text(
                    title=card.headline,
                    summary=card.summary,
                    category=card.category,
                )
                urg_score, _ = UrgencyEngine.calculate_urgency(
                    title=card.headline,
                    summary=card.summary,
                    is_developing=True,
                )
                ver_score, ver_meta = VerificationEngine.calculate_verification(
                    sources=[{"name": getattr(a.source, "name", "Wire"), "url": getattr(a, "url", "")} for a in articles],
                    conflict_detected=bool(cluster.flagged_conflict),
                )
                scoring_out = FeedRankingEngine.compute_final_score(
                    objective_importance=imp_score,
                    urgency=urg_score,
                    freshness=100.0,
                    personal_relevance=25.0,
                    verification_confidence=ver_score,
                    dimensions=dims,
                    source_count=len(articles),
                    tier1_count=ver_meta.get("tier1_source_count", 0),
                )
                card.importance_score = imp_score
                card.urgency_score = urg_score
                card.freshness_score = 100.0
                card.verification_score = ver_score
                card.personal_relevance_score = 25.0
                card.final_feed_score = scoring_out.final_feed_score
                card.priority_reason = scoring_out.priority_reason
                card.impact_evidence = dims.model_dump()
            except Exception as rank_err:
                print(f"[Pipeline] Ranking engine fallback warning: {rank_err}", flush=True)

            print(f"[Pipeline] -> Card published (score={card.final_feed_score or obj_score}): '{card.headline}'", flush=True)
        db.commit()
        produced.append(card.id)
    return produced


def _build_card(cluster: StoryCluster, articles: list[Article], summary_json: dict) -> Card:
    category = str(summary_json.get("category") or (articles[0].source.category if articles else "national"))
    refs = [
        SourceRef(
            source_id=a.source_id,
            trust_tier=a.source.trust_tier,
            name=a.source.name,
            verified_local_source=bool(getattr(a.source, "verified_local_source", False)),
            wire_attribution=getattr(a, "wire_attribution", None),
            text=f"{a.title}\n{a.raw_text}",
            headline=a.title,
        )
        for a in articles
    ]
    v_type = determine_verification_type(refs, scope=category, flagged_conflict=cluster.flagged_conflict)
    district = articles[0].district if (articles and articles[0].district) else None
    state = articles[0].state or (articles[0].source.region if articles else None)

    is_dev_only = any(
        getattr(a.source, "source_type", None) == "newsapi_dev_only"
        for a in articles if getattr(a, "source", None)
    )
    created_by_tag = "dev_testing" if is_dev_only else "live_pipeline"

    try:
        priority_score = int(summary_json.get("priority_score", 5))
    except (ValueError, TypeError):
        priority_score = 5
        
    content_type = str(summary_json.get("content_type", "NEWS")).upper().strip()
    if content_type not in ["NEWS", "NEWSLETTER", "PROMOTIONAL", "OPINION", "PRESS_RELEASE", "ANALYSIS", "UNKNOWN"]:
        content_type = "UNKNOWN"

    return Card(
        id=new_id(),
        cluster_id=cluster.id,
        headline=str(summary_json.get("headline") or "")[:255],
        summary=str(summary_json.get("summary") or ""),
        category=category,
        verified_status="draft",
        verification_type=v_type,
        district=district,
        state=state,
        priority_score=priority_score,
        content_type=content_type,
        created_by=created_by_tag,
    )



def _attach_sources(card: Card, articles: list[Article]) -> None:
    seen: set[str] = set()
    for article in articles:
        if article.source_id in seen:
            continue
        seen.add(article.source_id)
        card.sources.append(
            CardSource(
                id=new_id(),
                card_id=card.id,
                source_id=article.source_id,
                article_id=article.id,
                name=article.source.name,
                url=article.url,
                trust_tier=str(article.source.trust_tier),
            )
        )


def _excerpts(articles: list[Article]) -> str:
    parts = [f"{a.source.name}\n{a.url}\n{a.title}\n{(a.original_text or a.raw_text)[:800]}" for a in articles]
    return "\n\n-----\n\n".join(parts)


def _collect_numbers(articles: list[Article]) -> dict[str, list[float]]:
    """Lightweight numeric harvest for conflict checks (labeled '<n> <word>')."""
    import re

    collected: dict[str, list[float]] = {}
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s+([a-zA-Z]+)")
    for article in articles:
        text = f"{article.title} {article.raw_text}".lower()
        for num, label in pattern.findall(text):
            collected.setdefault(label, []).append(float(num))
    return collected
