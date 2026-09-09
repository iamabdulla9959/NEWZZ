import os
import sys
from datetime import datetime, timezone
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.extend(["apps/api", "apps/worker"])

from dotenv import load_dotenv
load_dotenv(".env")

from app.db import SessionLocal
from app.models import Article, Card, ReviewQueueItem, StoryCluster, new_id
from worker.llm import MultiProviderClient
from worker.pipeline import _build_card, _attach_sources, _excerpts
from worker.validate import matches_sensitivity, run_rule_checks
from worker.scoring import calculate_objective_score
from worker.summarize import judge_fact_consistency, summarize_articles

TARGET_CLUSTER_IDS = [
    # 4 National
    "a9399f7d-40b1-46de-b047-d59ba2632183",
    "77d77dda-9c30-47ea-9893-5112cd8174c7",
    "88837dc6-2df1-4e5b-82bf-c021c58ced8a",
    "31050e53-29c2-4eaa-808a-713268f0d8f0",
    # 2 Tech
    "915daff6-930e-4a1a-9906-33d76218ff10",
    "3b0f7e7a-facb-4006-a62f-499dcf8b13f0",
]

def main():
    db = SessionLocal()
    llm = MultiProviderClient()
    print("=== MultiProviderClient Configured ===")
    print("Active providers:", [p.name for p in llm.providers])
    print(f"Targeting {len(TARGET_CLUSTER_IDS)} backlog clusters (4 national, 2 tech)...\n")

    results = []
    quota_errors = []

    for i, cluster_id in enumerate(TARGET_CLUSTER_IDS, 1):
        cluster = db.query(StoryCluster).filter(StoryCluster.id == cluster_id).first()
        if not cluster:
            print(f"[{i}/6] Cluster {cluster_id} not found in DB!")
            continue

        articles = db.query(Article).filter(Article.cluster_id == cluster.id).all()
        category = articles[0].source.category if articles else "national"
        title_snip = articles[0].title[:60] if articles else "Untitled"
        sources_list = [a.source.name for a in articles if a.source]

        print(f"[{i}/6] Processing: '{title_snip}'")
        print(f"      Category: {category} | Sources ({len(articles)}): {sources_list}")

        payload = [
            {
                "name": a.source.name,
                "title": a.title,
                "url": a.url,
                "text": a.raw_text,
            }
            for a in articles
        ]

        # 1. Summarize
        try:
            summary_json = summarize_articles(llm, payload, category_hint=category)
            summarize_provider = llm.last_served_provider
            print(f"      -> Summarized by [{summarize_provider}]: '{summary_json.get('headline')}'")
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "quota" in err_msg.lower():
                quota_errors.append((cluster_id, "summarize", err_msg))
            print(f"      -> FAILED summarize: {exc}")
            continue

        card = _build_card(cluster, articles, summary_json)
        card.created_by = "live_pipeline"
        db.add(card)
        db.flush()
        _attach_sources(card, articles)

        # 2. Rule checks & Sensitivity
        reasons: list[str] = []
        if cluster.flagged_conflict:
            reasons.append("flagged_conflict")
        combined = " ".join([card.headline, card.summary] + [a.title for a in articles])
        if matches_sensitivity(combined):
            reasons.append("sensitivity_keyword")

        rules = run_rule_checks(card.summary)
        reasons.extend(rules.reasons)

        # 3. Fact Consistency Judge
        judge_provider = None
        try:
            source_verifications = [
                f"{a.title}\n{a.original_text or a.raw_text}" for a in articles
            ]
            judge = judge_fact_consistency(llm, card.summary, source_verifications)
            judge_provider = llm.last_served_provider
            print(f"      -> Fact Judge by [{judge_provider}]: consistent={judge.get('consistent')}")
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "quota" in err_msg.lower():
                quota_errors.append((cluster_id, "judge", err_msg))
            judge = {"consistent": False, "issues": [f"judge_error:{exc}"]}

        if not judge.get("consistent"):
            reasons.extend([str(iss) for iss in judge.get("issues") or ["fact_inconsistent"]])

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
            print(f"      -> Card queued for review: {reasons}")
        else:
            card.verified_status = "published"
            card.published_at = datetime.now(timezone.utc)
            obj_score, impact_hits = calculate_objective_score(
                articles=articles,
                headline=card.headline,
                summary=card.summary,
                published_at=card.published_at,
            )
            card.objective_score = obj_score
            card.impact_keywords_count = impact_hits
            print(f"      -> Card PUBLISHED! Score: {obj_score:.2f}, Impact hits: {impact_hits}")

        db.commit()
        results.append({
            "cluster_id": cluster.id,
            "category": card.category,
            "headline": card.headline,
            "summary": card.summary,
            "status": card.verified_status,
            "provider": summarize_provider,
            "reasons": reasons,
        })
        time.sleep(1.0)

    db.close()

    print("\n" + "="*60)
    print("=== SUMMARY OF STEP 15C BACKLOG PROCESSING ===")
    print("="*60)
    print(f"Total processed: {len(results)}/6")
    print(f"Quota / 429 errors encountered: {len(quota_errors)}")
    for r in results:
        status_badge = "PUBLISHED" if r["status"] == "published" else f"PENDING_REVIEW ({', '.join(r['reasons'])})"
        print(f"- [{r['category'].upper()}] [{r['provider']}] [{status_badge}] {r['headline']}")

if __name__ == "__main__":
    main()
