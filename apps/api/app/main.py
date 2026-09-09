from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.db import engine
from app.routers.admin import router as admin_router
from app.routers.feed import router as feed_router

app = FastAPI(title="News Reels API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:19006",
        "http://127.0.0.1:19006",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingestion Health Endpoint & Uptime Monitoring
# ---------------------------------------------------------------------------
# How to wire to UptimeRobot free tier once deployed:
# 1. Sign up for a free account at https://uptimerobot.com
# 2. Add New Monitor -> Monitor Type: "HTTP(s)"
# 3. Friendly Name: "NewsReels Ingestion Worker"
# 4. URL (or IP): "https://<your-api-domain>/health/ingestion"
# 5. Monitoring Interval: 5 minutes (or 15 minutes on free tier)
# 6. Advanced Settings -> Keyword: Alert when keyword does NOT exist -> "status": "ok"
#    (or set HTTP status alert if health/ingestion returns 503 on worker stalls > 30m)
# 7. Add Alert Contact to receive email/webhook notifications when ingestion stops.
# ---------------------------------------------------------------------------
@app.get("/health/ingestion")
def health_ingestion() -> dict:
    from app.db import SessionLocal
    from app.models import WorkerRun
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        latest = db.query(WorkerRun).order_by(WorkerRun.timestamp.desc()).first()
        if not latest:
            return {
                "status": "warning",
                "message": "No worker runs recorded yet",
                "last_run_timestamp": None,
                "sources_polled": 0,
                "articles_ingested": 0,
                "errors": [],
            }
        
        # Check staleness (e.g. if last run was > 45 minutes ago)
        now = datetime.now(timezone.utc)
        diff_seconds = 0.0
        if latest.timestamp:
            ts = latest.timestamp if latest.timestamp.tzinfo else latest.timestamp.replace(tzinfo=timezone.utc)
            diff_seconds = (now - ts).total_seconds()

        status = "ok"
        if latest.errors and len(latest.errors) > 0:
            status = "degraded"
        if diff_seconds > 2700:  # > 45 mins
            status = "stale"

        return {
            "status": status,
            "provider": getattr(latest, "provider", "rss"),
            "last_run_timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
            "seconds_since_last_run": round(diff_seconds, 1),
            "sources_polled": latest.sources_polled,
            "articles_ingested": latest.articles_ingested,
            "credits_used": getattr(latest, "credits_used", 0),
            "errors": latest.errors or [],
            "duration_seconds": latest.duration_seconds,
        }
    finally:
        db.close()


_dist_dir = Path(__file__).resolve().parent.parent.parent / "mobile" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="static")

