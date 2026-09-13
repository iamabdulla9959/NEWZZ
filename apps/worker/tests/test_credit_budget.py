from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models import Source, WorkerRun
from worker.credit_budget import (
    CURRENT_DAILY_CREDIT_BUDGET,
    NEWSDATA_DAILY_CREDIT_BUDGET,
    TOTAL_DAILY_CREDIT_BUDGET,
    get_daily_provider_credits,
)
from worker.currents import poll_currents_sources
from worker.newsdata import poll_newsdata_sources


def _run(db, provider: str, credits: int) -> None:
    db.add(
        WorkerRun(
            id=f"{provider}-{credits}-{datetime.now(timezone.utc).timestamp()}",
            provider=provider,
            sources_polled=credits,
            articles_ingested=0,
            credits_used=credits,
            timestamp=datetime.now(timezone.utc),
        )
    )
    db.commit()


def test_providers_have_independent_daily_budgets(db):
    _run(db, "currents_api", CURRENT_DAILY_CREDIT_BUDGET)
    _run(db, "newsdata_api", NEWSDATA_DAILY_CREDIT_BUDGET)
    assert get_daily_provider_credits(db, "currents_api") == 250
    assert get_daily_provider_credits(db, "newsdata_api") == 200
    assert get_daily_provider_credits(db) == TOTAL_DAILY_CREDIT_BUDGET

    source = Source(
        id="currents-budget-source",
        name="Currents Budget Source",
        category="science",
        region="IN",
        source_type="currents_api",
        is_active=True,
    )
    db.add(source)
    db.commit()
    client = MagicMock()

    polled, created, credits, errors = poll_currents_sources(db, client=client)
    assert (polled, created, credits) == (0, 0, 0)
    assert any("250/250" in error for error in errors)
    client.fetch_latest.assert_not_called()


def test_newsdata_stops_at_its_own_200_request_limit(db):
    db.query(WorkerRun).delete()
    db.commit()
    _run(db, "currents_api", CURRENT_DAILY_CREDIT_BUDGET)
    _run(db, "newsdata_api", NEWSDATA_DAILY_CREDIT_BUDGET)
    source = Source(
        id="newsdata-budget-source",
        name="NewsData Budget Source",
        category="science",
        region="IN",
        source_type="newsdata_api",
        is_active=True,
    )
    db.add(source)
    db.commit()
    client = MagicMock()
    client.fetch_latest.return_value = ([], 1, [])

    polled, created, credits, errors = poll_newsdata_sources(db, client=client)
    assert polled == 0
    assert created == 0
    assert credits == 0
    assert any("200/200" in error for error in errors)
