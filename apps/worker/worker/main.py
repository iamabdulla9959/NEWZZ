from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure apps/worker, apps/api, and repo root are on sys.path before any project imports
_worker_root = Path(__file__).resolve().parents[1]
_api_root = Path(__file__).resolve().parents[2] / "api"
_repo_root = Path(__file__).resolve().parents[3]
for p in [str(_worker_root), str(_api_root), str(_repo_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from worker import paths  # noqa: F401

from app.db import SessionLocal
from app.models import Source, StoryCluster, WorkerRun, new_id
from worker.llm import MultiProviderClient
from worker.newsdata import NEWSDATA_POLL_INTERVAL_MINUTES, poll_newsdata_sources
from worker.currents import CURRENTS_POLL_INTERVAL_MINUTES, poll_currents_sources
from worker.pipeline import cluster_unassigned_articles, evaluate_cluster, process_eligible_clusters
from worker.scoring import recalculate_recent_cards_decay
import httpx
from worker.ingest import ingest_rss_source, USER_AGENT
from worker.coordination import (
    acquire_lease,
    acquire_lease_with_generation,
    renew_lease,
    release_lease,
    is_lease_valid,
    validate_lease_fencing,
    atomic_claim_request_with_lease,
    claim_pending_request,
    finish_request,
    recover_abandoned_requests,
    heartbeat_lease,
    heartbeat_request,
    IngestionHeartbeat,
    StaleLeaseError,
)

WORKER_ID = f"worker-{os.getpid()}-{int(time.time())}"

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

# Separate tuneable scheduling intervals
NEWSDATA_INGEST_INTERVAL_MINUTES: int = int(
    os.getenv("NEWSDATA_INGEST_INTERVAL_MINUTES", str(NEWSDATA_POLL_INTERVAL_MINUTES))
)  # 60-90 mins default
RECENCY_DECAY_INTERVAL_MINUTES: int = int(os.getenv("RECENCY_DECAY_INTERVAL_MINUTES", "60"))  # 1-2 hours default
CURRENTS_INGEST_INTERVAL_MINUTES: int = int(
    os.getenv("CURRENTS_INGEST_INTERVAL_MINUTES", str(CURRENTS_POLL_INTERVAL_MINUTES))
)
RSS_INGEST_INTERVAL_MINUTES: int = int(os.getenv("RSS_INGEST_INTERVAL_MINUTES", "15"))
RSS_INGEST_INTERVAL_SECONDS: int | None = (
    int(os.getenv("RSS_INGEST_INTERVAL_SECONDS"))
    if os.getenv("RSS_INGEST_INTERVAL_SECONDS")
    else None
)

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


def run_rss_once(
    llm: MultiProviderClient | None = None,
    http_client: httpx.Client | None = None,
    require_lease: bool = False,
    worker_id: str | None = None,
    lease_generation: int | None = None,
) -> None:
    """Runs canonical RSS ingestion across active sources into articles and clusters."""
    start_time = time.time()
    w_id = worker_id or WORKER_ID
    db = SessionLocal()
    current_gen = lease_generation
    if require_lease:
        acquired, gen = acquire_lease_with_generation(
            db, lease_name="canonical_ingestion", holder_id=w_id, ttl_seconds=300
        )
        if not acquired:
            print(f"[{w_id}] Skipped RSS run: execution lease held by another process", flush=True)
            db.close()
            return
        current_gen = gen

    polled = 0
    created = 0
    errors: list[str] = []
    active_llm = llm if llm is not None else _get_llm_client()

    try:
        sources = db.query(Source).filter(Source.is_active == True, Source.rss_url.isnot(None)).all()
        if not sources:
            try:
                from scripts.ingest_live import ensure_sources
                sources = ensure_sources(db)
            except ImportError:
                try:
                    from worker.scripts.ingest_live import ensure_sources
                    sources = ensure_sources(db)
                except ImportError:
                    sources = []

        owns_client = http_client is None
        client = http_client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        try:
            for src in sources:
                polled += 1
                try:
                    new_arts = ingest_rss_source(
                        db,
                        src,
                        client=client,
                        llm=active_llm,
                        expected_lease_holder=w_id if (require_lease or current_gen is not None) else None,
                        expected_lease_generation=current_gen,
                    )
                    created += new_arts
                except Exception as src_exc:
                    err = f"RSS poll failed for {src.name}: {src_exc}"
                    errors.append(err)
        finally:
            if owns_client:
                client.close()

        if current_gen is not None:
            if not validate_lease_fencing(db, lease_name="canonical_ingestion", holder_id=w_id, expected_generation=current_gen):
                db.rollback()
                raise StaleLeaseError(f"Lease superseded for worker '{w_id}' at gen {current_gen} before clustering")

        clustered = cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)

        published_or_queued: list[str] = []
        if active_llm:
            published_or_queued = process_eligible_clusters(
                db,
                active_llm,
                expected_lease_holder=w_id if require_lease else None,
                expected_lease_generation=current_gen if require_lease else None,
            )

        print(
            f"[RSS] sources_polled={polled} ingest_new={created} clustered={clustered} "
            f"cards={len(published_or_queued)} errors={len(errors)}"
        )
    except StaleLeaseError as stale_exc:
        err_msg = f"RSS worker stale lease: {stale_exc}"
        print(err_msg, flush=True)
        errors.append(err_msg)
        raise
    except Exception as exc:
        err_msg = f"RSS worker run exception: {exc}"
        print(err_msg, flush=True)
        errors.append(err_msg)
    finally:
        if require_lease:
            release_lease(db, lease_name="canonical_ingestion", holder_id=w_id, expected_generation=current_gen)
        duration = time.time() - start_time
        try:
            is_stale = any("stale" in str(e).lower() or "superseded" in str(e).lower() for e in errors)
            run_row = WorkerRun(
                id=new_id(),
                provider="rss_pipeline",
                sources_polled=polled,
                articles_ingested=0 if is_stale else created,
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


def run_currents_once(llm: MultiProviderClient | None = None) -> None:
    """Runs Currents ingestion and the shared verification pipeline."""
    start_time = time.time()
    db = SessionLocal()
    polled = created = requests_used = 0
    errors: list[str] = []
    active_llm = llm if llm is not None else _get_llm_client()
    try:
        polled, created, requests_used, errors = poll_currents_sources(
            db, api_key=os.getenv("CURRENTS_API_KEY", "").strip(), llm=active_llm
        )
        clustered = cluster_unassigned_articles(db)
        for cluster in db.query(StoryCluster).all():
            evaluate_cluster(db, cluster)
        if active_llm:
            process_eligible_clusters(db, active_llm)
        print(
            f"[Currents] sources_polled={polled} ingest_new={created} requests={requests_used} "
            f"clustered={clustered} errors={len(errors)}"
        )
    except Exception as exc:
        errors.append(f"Currents worker run exception: {exc}")
        print(errors[-1])
    finally:
        try:
            db.add(
                WorkerRun(
                    id=new_id(),
                    provider="currents_api",
                    sources_polled=polled,
                    articles_ingested=created,
                    credits_used=requests_used,
                    errors=errors or None,
                    duration_seconds=round(time.time() - start_time, 3),
                )
            )
            db.commit()
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


def process_pending_requests(
    worker_id: str | None = None,
    llm: MultiProviderClient | None = None,
) -> int:
    """Discovers, claims, and executes any pending manual IngestionRequests."""
    w_id = worker_id or WORKER_ID
    db = SessionLocal()
    processed = 0
    try:
        # Recover any crashed/abandoned running requests before claiming
        recover_abandoned_requests(db, max_age_seconds=300, max_retries=3)

        # Atomically claim request and acquire execution lease
        req, gen = atomic_claim_request_with_lease(db, worker_id=w_id, ttl_seconds=300)
        if not req:
            return 0

        print(f"[{w_id}] Processing manual IngestionRequest {req.id} (lease gen {gen})...", flush=True)
        with IngestionHeartbeat(
            session_factory=SessionLocal,
            lease_name="canonical_ingestion",
            holder_id=w_id,
            generation=gen,
            request_id=req.id,
            interval_seconds=5.0,
            ttl_seconds=300,
        ) as hb:
            try:
                active_llm = llm if llm is not None else _get_llm_client()
                run_rss_once(llm=active_llm, require_lease=False, worker_id=w_id, lease_generation=gen)
                finish_request(
                    db,
                    request_id=req.id,
                    worker_id=w_id,
                    status="succeeded",
                    result_summary={"message": "Canonical ingestion completed successfully"},
                    expected_generation=gen,
                )
                processed += 1
            except StaleLeaseError as stale_exc:
                print(f"[{w_id}] Execution aborted due to stale lease: {stale_exc}", flush=True)
            except Exception as exc:
                finish_request(
                    db,
                    request_id=req.id,
                    worker_id=w_id,
                    status="failed",
                    error_message=str(exc),
                    expected_generation=gen,
                )
            finally:
                release_lease(db, lease_name="canonical_ingestion", holder_id=w_id, expected_generation=gen)
    finally:
        db.close()
    return processed


def run_scheduled_rss():
    run_rss_once(require_lease=True)


def run_once() -> None:
    """Runs RSS, Currents, NewsData, recency decay, and any pending manual requests."""
    llm = _get_llm_client()
    process_pending_requests(llm=llm)
    run_rss_once(llm=llm)
    run_currents_once(llm=llm)
    run_newsdata_once(llm=llm)
    run_recency_decay_once()


def main() -> None:
    if os.getenv("RUN_ONCE") == "1":
        run_once()
        return

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)

    # Recover any crashed/abandoned requests at startup
    startup_db = SessionLocal()
    try:
        recover_abandoned_requests(startup_db, max_age_seconds=300, max_retries=3)
    finally:
        startup_db.close()

    scheduler = BlockingScheduler(timezone="UTC", job_defaults={"misfire_grace_time": 60})
    scheduler.add_job(
        process_pending_requests,
        "interval",
        seconds=10,
        next_run_time=now,
        id="manual_requests_poll",
        max_instances=1,
    )
    if RSS_INGEST_INTERVAL_SECONDS:
        scheduler.add_job(
            run_scheduled_rss,
            "interval",
            seconds=RSS_INGEST_INTERVAL_SECONDS,
            next_run_time=now + timedelta(seconds=1),
            id="rss_ingest",
            max_instances=1,
        )
    else:
        scheduler.add_job(
            run_scheduled_rss,
            "interval",
            minutes=RSS_INGEST_INTERVAL_MINUTES,
            next_run_time=now + timedelta(seconds=2),
            id="rss_ingest",
            max_instances=1,
        )
    scheduler.add_job(
        run_currents_once,
        "interval",
        minutes=CURRENTS_INGEST_INTERVAL_MINUTES,
        next_run_time=now + timedelta(minutes=2),
        id="currents_ingest",
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
    rss_display = (
        f"{RSS_INGEST_INTERVAL_SECONDS}s"
        if RSS_INGEST_INTERVAL_SECONDS
        else f"{RSS_INGEST_INTERVAL_MINUTES}m"
    )
    print(
        f"Worker [{WORKER_ID}] started with schedules: "
        f"ManualRequestsPoll every 10s, "
        f"RSS every {rss_display}, "
        f"Currents every {CURRENTS_INGEST_INTERVAL_MINUTES}m, "
        f"NewsData every {NEWSDATA_INGEST_INTERVAL_MINUTES}m, "
        f"RecencyDecay every {RECENCY_DECAY_INTERVAL_MINUTES}m",
        flush=True,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
