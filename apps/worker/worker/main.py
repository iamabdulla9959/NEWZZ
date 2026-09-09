from __future__ import annotations

import os
import sys
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from worker import paths  # noqa: F401

from app.db import SessionLocal
from app.models import StoryCluster, WorkerRun, new_id
from worker.ingest import ingest_all_active
from worker.llm import MultiProviderClient
from worker.newsdata import NEWSDATA_POLL_INTERVAL_MINUTES, poll_newsdata_sources
from worker.pipeline import cluster_unassigned_articles, evaluate_cluster, process_eligible_clusters
from worker.scoring import recalculate_recent_cards_decay
from worker.serpapi_news import poll_serpapi_sources
from worker.serpapi_news import poll_serpapi_sources

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

# Separate tuneable scheduling intervals
RSS_INGEST_INTERVAL_SECONDS: int = int(os.getenv("INGEST_INTERVAL_SECONDS", "900"))  # 15 mins default
NEWSDATA_INGEST_INTERVAL_MINUTES: int = int(
    os.getenv("NEWSDATA_INGEST_INTERVAL_MINUTES", str(NEWSDATA_POLL_INTERVAL_MINUTES))
)  # 60-90 mins default
RECENCY_DECAY_INTERVAL_MINUTES: int = int(os.getenv("RECENCY_DECAY_INTERVAL_MINUTES", "60"))  # 1-2 hours default

# Hard architectural guard:
# Production worker scheduled jobs MUST NEVER invoke or schedule dev-only source clients (such as NewsAPI).
# NewsAPI.org terms forbid commercial / production use on its free tier.
# Dev-only sources (source_type="newsapi_dev_only") are strictly excluded from all production scheduler jobs.
PROD_EXCLUDED_SOURCE_TYPES: tuple[str, ...] = ("newsapi_dev_only",)


def _get_llm_client() -> MultiProviderClient | None:
    has_llm_key = any([
        os.getenv("LLM_API_KEY"),
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GROQ_API_KEY"),
        os.getenv("OPENROUTER_API_KEY"),
    ])
    return MultiProviderClient() if has_llm_key else None


def run_rss_once(llm: MultiProviderClient | None = None) -> None:
    """Runs RSS and official_local ingestion on 10-15 minute cadence."""
    start_time = time.time()
    db = SessionLocal()
    polled = 0
    created = 0
    errors: list[str] = []
    active_llm = llm if llm is not None else _get_llm_client()

    try:
        polled, created, ingest_errors = ingest_all_active(db, llm=active_llm)
        errors.extend(ingest_errors)

        clustered = cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)

        published_or_queued: list[str] = []
        if active_llm:
            published_or_queued = process_eligible_clusters(db, active_llm)

        print(
            f"[RSS] sources_polled={polled} ingest_new={created} clustered={clustered} cards={len(published_or_queued)} errors={len(errors)}"
        )
    except Exception as exc:
        err_msg = f"RSS worker run exception: {exc}"
        print(err_msg)
        errors.append(err_msg)
    finally:
        duration = time.time() - start_time
        try:
            run_row = WorkerRun(
                id=new_id(),
                provider="rss",
                sources_polled=polled,
                articles_ingested=created,
                credits_used=0,
                errors=errors if errors else None,
                duration_seconds=round(duration, 3),
            )
            db.add(run_row)
            db.commit()
        except Exception as exc:
            print(f"Failed to record RSS WorkerRun: {exc}")
        finally:
            db.close()


def run_newsdata_once(llm: MultiProviderClient | None = None) -> None:
    """Runs NewsData.io ingestion on slower 60-90 minute cadence with credit tracking."""
    api_key = os.getenv("NEWSDATA_API_KEY", "").strip()
    if not api_key:
        print("[NewsData] NEWSDATA_API_KEY not configured; skipping NewsData poll.")
        return

    start_time = time.time()
    db = SessionLocal()
    polled = 0
    created = 0
    credits_used = 0
    errors: list[str] = []
    active_llm = llm if llm is not None else _get_llm_client()

    try:
        polled, created, credits_used, nd_errors = poll_newsdata_sources(
            db, api_key=api_key, llm=active_llm
        )
        errors.extend(nd_errors)

        # Articles flow into the EXACT same clustering and verification pipeline
        clustered = cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)

        published_or_queued: list[str] = []
        if active_llm:
            published_or_queued = process_eligible_clusters(db, active_llm)

        print(
            f"[NewsData] sources_polled={polled} ingest_new={created} credits_used={credits_used} clustered={clustered} cards={len(published_or_queued)} errors={len(errors)}"
        )
    except Exception as exc:
        err_msg = f"NewsData worker run exception: {exc}"
        print(err_msg)
        errors.append(err_msg)
    finally:
        duration = time.time() - start_time
        try:
            run_row = WorkerRun(
                id=new_id(),
                provider="newsdata_api",
                sources_polled=polled,
                articles_ingested=created,
                credits_used=credits_used,
                errors=errors if errors else None,
                duration_seconds=round(duration, 3),
            )
            db.add(run_row)
            db.commit()
        except Exception as exc:
            print(f"Failed to record NewsData WorkerRun: {exc}")
        finally:
            db.close()


def run_serpapi_once(llm: MultiProviderClient | None = None) -> None:
    """Runs SerpApi ingestion on a strict 12-hour cadence to conserve 100/mo API limit."""
    start_time = time.time()
    db = SessionLocal()
    polled = 0
    created = 0
    errors: list[str] = []
    active_llm = llm if llm is not None else _get_llm_client()

    try:
        polled, created, serpapi_errors = poll_serpapi_sources(db, llm=active_llm)
        errors.extend(serpapi_errors)

        # Articles flow into the EXACT same clustering and verification pipeline
        clustered = cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)

        published_or_queued: list[str] = []
        if active_llm:
            published_or_queued = process_eligible_clusters(db, active_llm)

        print(
            f"[SerpApi] sources_polled={polled} ingest_new={created} clustered={clustered} cards={len(published_or_queued)} errors={len(errors)}"
        )
    except Exception as exc:
        err_msg = f"SerpApi worker run exception: {exc}"
        print(err_msg)
        errors.append(err_msg)
    finally:
        duration = time.time() - start_time
        try:
            run_row = WorkerRun(
                id=new_id(),
                provider="serpapi",
                sources_polled=polled,
                articles_ingested=created,
                credits_used=created, # approx
                errors=errors if errors else None,
                duration_seconds=round(duration, 3),
            )
            db.add(run_row)
            db.commit()
        except Exception as exc:
            print(f"Failed to record SerpApi WorkerRun: {exc}")
        finally:
            db.close()


def run_recency_decay_once() -> int:
    """Recalculates recency decay for published cards from the last 48 hours."""
    start_time = time.time()
    db = SessionLocal()
    updated = 0
    errors: list[str] = []
    try:
        updated = recalculate_recent_cards_decay(db, max_age_hours=48)
        print(f"[RecencyDecay] updated={updated} cards", flush=True)
        return updated
    except Exception as exc:
        err_msg = f"Recency decay error: {exc}"
        print(f"[RecencyDecay] {err_msg}", flush=True)
        errors.append(err_msg)
        return 0
    finally:
        duration = time.time() - start_time
        try:
            run_row = WorkerRun(
                id=new_id(),
                provider="recency_decay",
                sources_polled=0,
                articles_ingested=updated,
                credits_used=0,
                errors=errors if errors else None,
                duration_seconds=round(duration, 3),
            )
            db.add(run_row)
            db.commit()
        except Exception as exc:
            print(f"Failed to record RecencyDecay WorkerRun: {exc}")
        finally:
            db.close()


def run_once() -> None:
    """Runs a single pass of both ingestion streams and recency decay."""
    llm = _get_llm_client()
    run_rss_once(llm=llm)
    run_newsdata_once(llm=llm)
    run_serpapi_once(llm=llm)
    run_recency_decay_once()


def main() -> None:
    if os.getenv("RUN_ONCE") == "1":
        run_once()
        return

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_rss_once,
        "interval",
        seconds=RSS_INGEST_INTERVAL_SECONDS,
        next_run_time=now,
        id="rss_ingest",
        max_instances=1,
    )
    scheduler.add_job(
        run_newsdata_once,
        "interval",
        minutes=NEWSDATA_INGEST_INTERVAL_MINUTES,
        next_run_time=now + timedelta(minutes=5),
        id="newsdata_ingest",
        max_instances=1,
    )
    scheduler.add_job(
        run_recency_decay_once,
        "interval",
        minutes=RECENCY_DECAY_INTERVAL_MINUTES,
        next_run_time=now + timedelta(minutes=15),
        id="recency_decay",
        max_instances=1,
    )
    scheduler.add_job(
        run_serpapi_once,
        "interval",
        hours=12,
        next_run_time=now + timedelta(minutes=10),
        id="serpapi_ingest",
        max_instances=1,
    )
    print(
        f"Worker started with schedules: RSS every {RSS_INGEST_INTERVAL_SECONDS}s, NewsData every {NEWSDATA_INGEST_INTERVAL_MINUTES}m, SerpApi every 12h, RecencyDecay every {RECENCY_DECAY_INTERVAL_MINUTES}m"
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()



if __name__ == "__main__":
    main()

