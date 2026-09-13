from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import WorkerRun

CURRENT_DAILY_CREDIT_BUDGET = 250
NEWSDATA_DAILY_CREDIT_BUDGET = 200
TOTAL_DAILY_CREDIT_BUDGET = CURRENT_DAILY_CREDIT_BUDGET + NEWSDATA_DAILY_CREDIT_BUDGET
BILLABLE_PROVIDERS = ("currents_api", "newsdata_api")


def get_daily_provider_credits(db: Session, provider: str | None = None) -> int:
    """Return today's request count for one provider or both providers."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = db.query(WorkerRun).filter(WorkerRun.timestamp >= today_start)
    if provider:
        query = query.filter(WorkerRun.provider == provider)
    else:
        query = query.filter(WorkerRun.provider.in_(BILLABLE_PROVIDERS))
    runs = query.all()
    return sum(max(0, int(run.credits_used or 0)) for run in runs)


def remaining_daily_credits(db: Session, provider: str) -> int:
    limits = {
        "currents_api": CURRENT_DAILY_CREDIT_BUDGET,
        "newsdata_api": NEWSDATA_DAILY_CREDIT_BUDGET,
    }
    return max(0, limits[provider] - get_daily_provider_credits(db, provider))
