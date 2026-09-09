from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import WorkerRun
from worker.llm import LLMProvider, MultiProviderClient
from worker.main import run_once


def test_multiprovider_fallback_on_primary_failure():
    """DoD: Killing/rate-limiting the primary LLM provider causes automatic fallback to next provider."""
    # Primary provider: simulates Gemini 429 RateLimit error
    gemini_mock = MagicMock()
    gemini_mock.chat.completions.create.side_effect = RuntimeError("RateLimitError: 429 Resource has been exhausted")
    gemini_prov = LLMProvider("gemini", "key1", "http://gemini", "gemini-2.0-flash", client=gemini_mock)

    # Secondary provider: Groq succeeds
    groq_mock = MagicMock()
    groq_response = MagicMock()
    groq_response.choices = [
        MagicMock(message=MagicMock(content='{"headline": "Test Groq", "summary": "Groq summary", "category": "tech", "key_facts": [], "conflicts": []}'))
    ]
    groq_mock.chat.completions.create.return_value = groq_response
    groq_prov = LLMProvider("groq", "key2", "http://groq", "llama-3.3-70b", client=groq_mock)

    client = MultiProviderClient(providers=[gemini_prov, groq_prov])

    result = client.complete_json("system", "user")
    assert result["headline"] == "Test Groq"
    assert client.last_served_provider == "groq"


def test_multiprovider_fallback_to_openrouter_free_model():
    """Fallback propagates through secondary down to tertiary OpenRouter."""
    gemini_mock = MagicMock()
    gemini_mock.chat.completions.create.side_effect = RuntimeError("Gemini 503 Overloaded")
    gemini_prov = LLMProvider("gemini", "key1", "http://gemini", "gemini-2.0-flash", client=gemini_mock)

    groq_mock = MagicMock()
    groq_mock.chat.completions.create.side_effect = RuntimeError("Groq RateLimitError")
    groq_prov = LLMProvider("groq", "key2", "http://groq", "llama-3.3-70b", client=groq_mock)

    openrouter_mock = MagicMock()
    openrouter_response = MagicMock()
    openrouter_response.choices = [
        MagicMock(message=MagicMock(content="Translated English text from OpenRouter"))
    ]
    openrouter_mock.chat.completions.create.return_value = openrouter_response
    openrouter_prov = LLMProvider("openrouter", "key3", "http://openrouter", "llama-3.2-3b", client=openrouter_mock)

    client = MultiProviderClient(providers=[gemini_prov, groq_prov, openrouter_prov])
    text = client.complete_text("system", "user")
    assert text == "Translated English text from OpenRouter"
    assert client.last_served_provider == "openrouter"


def test_worker_runs_table_records_every_run(monkeypatch):
    """DoD: worker_runs table shows a row after every run, including failed ones."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    import app.db as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", Session)
    import worker.main as main_mod
    monkeypatch.setattr(main_mod, "SessionLocal", Session)

    # 1. Normal run
    monkeypatch.setattr(main_mod, "ingest_all_active", lambda db, **kw: (3, 5, []))
    monkeypatch.setattr(main_mod, "cluster_unassigned_articles", lambda db: 5)
    main_mod.run_rss_once()

    db = Session()
    runs = db.query(WorkerRun).filter(WorkerRun.provider == "rss").all()
    assert len(runs) == 1
    assert runs[0].sources_polled == 3
    assert runs[0].articles_ingested == 5
    assert runs[0].errors is None or len(runs[0].errors) == 0

    # 2. Failing run
    def failing_ingest(db, **kw):
        raise ConnectionError("Network down to RSS feeds")

    monkeypatch.setattr(main_mod, "ingest_all_active", failing_ingest)
    main_mod.run_rss_once()

    runs = db.query(WorkerRun).filter(WorkerRun.provider == "rss").order_by(WorkerRun.timestamp.asc()).all()
    assert len(runs) == 2
    assert runs[1].errors is not None
    assert any("Network down" in e for e in runs[1].errors)

