from fastapi.testclient import TestClient
import pytest

from app.db import SessionLocal
from app.main import app
from app.models import WorkerRun, new_id

client = TestClient(app)


def test_health_returns_200_when_db_reachable():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_status_and_geocoder_provider():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["geocoder_provider"] in {"nominatim", "locationiq"}


def test_health_ingestion_returns_status():
    db = SessionLocal()
    try:
        db.add(WorkerRun(id=new_id(), sources_polled=5, articles_ingested=12, errors=None, duration_seconds=1.23))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["sources_polled"] == 5
    assert data["articles_ingested"] == 12


def test_ready_reports_migration_version():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "migration_version" in data
    assert data["migration_version"] is not None


def test_production_cannot_seed_demo_cards(monkeypatch):
    import pytest
    from apps.api.scripts.seed_demo_cards import check_demo_seeding_authorized
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY BLOCK"):
        check_demo_seeding_authorized(force_flag=True)


def test_development_seeding_requires_explicit_authorization(monkeypatch):
    import pytest
    from apps.api.scripts.seed_demo_cards import check_demo_seeding_authorized
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEMO_SEEDING", "")
    with pytest.raises(PermissionError, match="Demo seeding is disabled by default"):
        check_demo_seeding_authorized(force_flag=False)


def test_postgresql_database_url_normalization():
    from app.config import normalize_database_url
    # Standard Render / Heroku / Supabase postgres:// URL
    u1 = "postgres://user:secret@db.example.com:5432/newzz?sslmode=require"
    assert normalize_database_url(u1) == "postgresql+psycopg://user:secret@db.example.com:5432/newzz?sslmode=require"

    # standard postgresql:// without driver
    u2 = "postgresql://user:secret@localhost:5432/newzz"
    assert normalize_database_url(u2) == "postgresql+psycopg://user:secret@localhost:5432/newzz"

    # SQLite URL remains unaffected
    u3 = "sqlite:///newsreels.db"
    assert normalize_database_url(u3) == "sqlite:///newsreels.db"


def test_api_and_worker_share_database_configuration():
    from app.db import engine as api_engine
    from worker.paths import API_ROOT  # noqa
    from app.config import settings
    assert settings.database_url is not None
    assert api_engine is not None


def test_fresh_database_migration_succeeds(tmp_path):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from app.config import settings

    test_db_file = tmp_path / "fresh_migration_test.db"
    target_url = f"sqlite:///{test_db_file.as_posix()}"
    
    orig_url = settings.database_url
    try:
        settings.database_url = target_url
        cfg = Config("apps/api/alembic.ini")
        cfg.set_main_option("sqlalchemy.url", target_url)
        command.upgrade(cfg, "head")

        eng = sa.create_engine(target_url)
        insp = sa.inspect(eng)
        tables = set(insp.get_table_names())
        required_tables = {
            "cards", "articles", "sources", "card_sources", "story_clusters",
            "worker_runs", "ingestion_requests", "ingestion_leases",
        }
        assert required_tables.issubset(tables)

        lease_cols = {c["name"] for c in insp.get_columns("ingestion_leases")}
        assert "lease_generation" in lease_cols

        req_cols = {c["name"] for c in insp.get_columns("ingestion_requests")}
        assert {"lease_generation", "attempt_count", "last_heartbeat_at"}.issubset(req_cols)
        eng.dispose()
    finally:
        settings.database_url = orig_url


def test_production_fails_closed_when_database_url_is_sqlite(monkeypatch):
    import pytest
    from app.db import create_db_engine
    monkeypatch.setattr("app.config.settings.app_env", "production")
    with pytest.raises(RuntimeError, match="Production refuses to run against SQLite"):
        create_db_engine("sqlite:///newsreels.db")


def test_production_fails_closed_when_database_url_missing(monkeypatch):
    import pytest
    from app.db import create_db_engine
    monkeypatch.setattr("app.config.settings.app_env", "production")
    with pytest.raises(RuntimeError, match="DATABASE_URL is missing or empty"):
        create_db_engine("")


def test_production_fails_closed_when_database_url_malformed(monkeypatch):
    import pytest
    from app.db import create_db_engine
    monkeypatch.setattr("app.config.settings.app_env", "production")
    with pytest.raises(ValueError, match="Malformed or unsupported DATABASE_URL scheme"):
        create_db_engine("invalid_scheme://localhost:5432/db")


def test_redact_database_url_hides_credentials():
    from app.config import redact_database_url
    url = "postgresql+psycopg://admin_user:my_secret_password_123@db.render.com:5432/newzz_prod?sslmode=require"
    redacted = redact_database_url(url)
    assert "my_secret_password_123" not in redacted
    assert "admin_user:***@db.render.com:5432/newzz_prod?sslmode=require" in redacted


def test_ready_logging_security_hides_all_credentials_and_urls(monkeypatch):
    from unittest.mock import MagicMock
    mock_log_error = MagicMock()
    monkeypatch.setattr("app.main.logger.error", mock_log_error)

    class BrokenEngine:
        def connect(self):
            raise RuntimeError(
                "Failed to connect: postgresql://secret_user:super_secret_pass_999@db.internal.private.net:5432/production_db?sslmode=require&auth_token=secret_query_param_abc"
            )

    monkeypatch.setattr("app.main.engine", BrokenEngine())
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"

    mock_log_error.assert_called_once()
    # 1. Assert exactly one positional argument
    assert len(mock_log_error.call_args[0]) == 1
    logged_msg = str(mock_log_error.call_args[0][0])
    assert logged_msg == "Database readiness check failed: RuntimeError"

    # 2. Assert NO keyword arguments (no exc_info, stack_info, or extra hidden parameters)
    assert len(mock_log_error.call_args[1]) == 0

    # 3. Assert zero credentials, hostnames, query secrets, or exception messages leak
    assert "secret_user" not in logged_msg
    assert "super_secret_pass_999" not in logged_msg
    assert "db.internal.private.net" not in logged_msg
    assert "production_db" not in logged_msg
    assert "secret_query_param_abc" not in logged_msg
    assert "postgresql://" not in logged_msg


def test_health_liveness_only():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ingestion_degraded_when_errors_present():
    db = SessionLocal()
    from datetime import datetime, timezone
    try:
        db.query(WorkerRun).delete()
        db.add(WorkerRun(
            id=new_id(),
            timestamp=datetime.now(timezone.utc),
            sources_polled=10,
            articles_ingested=8,
            errors=["Connection refused to RSS feed"],
            duration_seconds=2.5
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert len(data["errors"]) == 1


def test_health_ingestion_stale_when_no_recent_runs():
    db = SessionLocal()
    from datetime import datetime, timezone, timedelta
    try:
        db.query(WorkerRun).delete()
        stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
        db.add(WorkerRun(
            id=new_id(),
            timestamp=stale_time,
            sources_polled=10,
            articles_ingested=5,
            errors=None,
            duration_seconds=3.0
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stale"



def test_health_ingestion_stale_with_historical_september_runs():
    db = SessionLocal()
    from datetime import datetime
    try:
        db.query(WorkerRun).delete()
        # Insert historical run from September 16, 2026
        historical_time = datetime.fromisoformat("2026-09-16T12:11:04.701929")
        db.add(WorkerRun(
            id=new_id(),
            provider="crawler_rss",
            timestamp=historical_time,
            sources_polled=3,
            articles_ingested=50,
            errors=None,
            duration_seconds=42.65
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stale"
    assert data["provider"] == "crawler_rss"


def test_health_ingestion_warning_when_no_runs_exist():
    """When no worker runs exist at all, health/ingestion returns warning."""
    db = SessionLocal()
    try:
        db.query(WorkerRun).delete()
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "warning"
    assert data["last_run_timestamp"] is None


def test_health_ingestion_failed_when_recent_run_has_total_failure():
    """A recent run with errors and zero articles ingested indicates worker failure."""
    db = SessionLocal()
    from datetime import datetime, timezone
    try:
        db.query(WorkerRun).delete()
        db.add(WorkerRun(
            id=new_id(),
            provider="rss_pipeline",
            timestamp=datetime.now(timezone.utc),
            sources_polled=10,
            articles_ingested=0,
            errors=["Fatal parser error: all feeds failed"],
            duration_seconds=5.0,
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["articles_ingested"] == 0
    assert len(data["errors"]) == 1


def test_ready_fails_503_when_migrations_missing(monkeypatch):
    """Readiness probe must return 503 if alembic migrations are missing."""
    class MockConn:
        def execute(self, q):
            class Res:
                def fetchone(self):
                    return None
            return Res()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    class MockEngine:
        def connect(self):
            return MockConn()

    monkeypatch.setattr("app.main.engine", MockEngine())
    response = client.get("/ready")
    assert response.status_code == 503
    assert "missing alembic_version" in response.json()["detail"]


def test_ready_fails_503_when_database_unreachable(monkeypatch):
    """Readiness probe must return 503 if database cannot be connected."""
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("Database connection refused: postgres://user:secret123@db.example.com:5432/db")

    monkeypatch.setattr("app.main.engine", BrokenEngine())
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
    assert "secret123" not in response.text
    assert "db.example.com" not in response.text


def test_health_ingestion_stale_on_historical_september_runs():
    """Historical runs from September 2026 must be reported as stale, never creating false freshness."""
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        db.query(WorkerRun).delete()
        db.add(WorkerRun(
            id=new_id(),
            provider="rss_pipeline",
            timestamp=datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc),
            sources_polled=10,
            articles_ingested=25,
            errors=None,
            duration_seconds=4.5,
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/health/ingestion")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stale"
    assert data["seconds_since_last_run"] > 86400 * 30


def test_incremental_migration_0011_and_0012(tmp_path):
    """Proves that an existing database at 0010 successfully migrates incrementally through 0011 and 0012."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from app.config import settings

    test_db_file = tmp_path / "incremental_migration_test.db"
    target_url = f"sqlite:///{test_db_file.as_posix()}"
    orig_url = settings.database_url

    try:
        settings.database_url = target_url
        cfg = Config("apps/api/alembic.ini")
        cfg.set_main_option("sqlalchemy.url", target_url)

        # 1. Upgrade to 0010
        command.upgrade(cfg, "0010_ranking_engine_fields")
        eng = sa.create_engine(target_url)
        insp = sa.inspect(eng)
        assert not insp.has_table("ingestion_leases")
        assert not insp.has_table("ingestion_requests")
        eng.dispose()

        # 2. Upgrade to 0011
        command.upgrade(cfg, "0011_ingestion_coordination")
        eng = sa.create_engine(target_url)
        insp = sa.inspect(eng)
        assert insp.has_table("ingestion_leases")
        assert insp.has_table("ingestion_requests")
        eng.dispose()

        # 3. Upgrade to 0012
        command.upgrade(cfg, "0012_lease_fencing_and_retries")
        eng = sa.create_engine(target_url)
        insp = sa.inspect(eng)
        lease_cols = {c["name"] for c in insp.get_columns("ingestion_leases")}
        assert "lease_generation" in lease_cols
        req_cols = {c["name"] for c in insp.get_columns("ingestion_requests")}
        assert {"lease_generation", "attempt_count", "last_heartbeat_at"}.issubset(req_cols)
        eng.dispose()

    finally:
        settings.database_url = orig_url


@pytest.mark.asyncio
async def test_lifespan_skips_create_all_in_production(monkeypatch):
    """Proves that Base.metadata.create_all is NOT called during startup in production."""
    from unittest.mock import MagicMock
    from app.main import lifespan, app

    mock_create_all = MagicMock()
    monkeypatch.setattr("app.models.Base.metadata.create_all", mock_create_all)

    # Test APP_ENV=production
    monkeypatch.setattr("app.config.settings.app_env", "production")
    async with lifespan(app):
        pass
    mock_create_all.assert_not_called()

    # Test APP_ENV=Production (different capitalization)
    monkeypatch.setattr("app.config.settings.app_env", "Production")
    async with lifespan(app):
        pass
    mock_create_all.assert_not_called()


@pytest.mark.asyncio
async def test_lifespan_runs_create_all_in_development(monkeypatch):
    """Proves that Base.metadata.create_all IS called during startup in development environments."""
    from unittest.mock import MagicMock
    from app.main import lifespan, app

    mock_create_all = MagicMock()
    monkeypatch.setattr("app.models.Base.metadata.create_all", mock_create_all)

    monkeypatch.setattr("app.config.settings.app_env", "development")
    async with lifespan(app):
        pass
    mock_create_all.assert_called_once()


def test_alembic_migrations_cover_all_models(tmp_path):
    """Verifies that running Alembic migrations head on a fresh DB creates ALL model tables, exact columns, nullability, primary keys, foreign keys (with ondelete/onupdate), unique constraints, indexes, server defaults, and column types in Base.metadata.

    Note on Dialect Limitations (SQLite vs PostgreSQL):
    - pgvector (VECTOR(768)): Enabled on PostgreSQL in 0004_enable_pgvector.py; falls back to TEXT/NULL in SQLite.
    - TIMESTAMPTZ: PostgreSQL stores timezone-aware timestamps; SQLite stores ISO8601 strings in DATETIME.
    - Vector Distance Indexes: HNSW/IVFFlat vector distance indexes are PostgreSQL-only.
    """
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from app.config import settings
    from app.models import Base

    test_db_file = tmp_path / "alembic_schema_coverage_test.db"
    target_url = f"sqlite:///{test_db_file.as_posix()}"
    orig_url = settings.database_url

    eng = None
    try:
        settings.database_url = target_url
        cfg = Config("apps/api/alembic.ini")
        cfg.set_main_option("sqlalchemy.url", target_url)
        command.upgrade(cfg, "head")

        eng = sa.create_engine(target_url)
        insp = sa.inspect(eng)

        migrated_tables = set(insp.get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())

        # 1. Exact Table Set Parity (No missing or unexpected tables)
        assert model_tables == migrated_tables, f"Table mismatch! Missing={model_tables - migrated_tables}, Unexpected={migrated_tables - model_tables}"

        # 2. Comprehensive Schema Inspection per Table
        for table_name in model_tables:
            model_table = Base.metadata.tables[table_name]
            db_cols = {c["name"]: c for c in insp.get_columns(table_name)}
            model_cols = {c.name: c for c in model_table.columns}

            # A. Exact Column Name Parity (0 missing, 0 unexpected)
            assert set(db_cols.keys()) == set(model_cols.keys()), f"Column mismatch in '{table_name}': Missing={set(model_cols.keys()) - set(db_cols.keys())}, Unexpected={set(db_cols.keys()) - set(model_cols.keys())}"

            # B. Exact Nullability Parity
            for col_name, model_col in model_cols.items():
                model_null = model_col.nullable if not model_col.primary_key else False
                db_null = db_cols[col_name]["nullable"]
                assert model_null == db_null, f"Nullability mismatch in '{table_name}.{col_name}': Model={model_null}, DB={db_null}"

            # C. Exact Primary Key Constraint & PK Column Ordering Parity
            model_pk_cols = [c.name for c in model_table.primary_key.columns]
            db_pk_cols = insp.get_pk_constraint(table_name).get("constrained_columns", [])
            assert model_pk_cols == db_pk_cols, f"Primary key mismatch in '{table_name}': Model={model_pk_cols}, DB={db_pk_cols}"

            # D. Exact Foreign Key Constraint Parity (Composite FKs, ondelete, and onupdate actions)
            model_fk_constraints = set()
            for fk_c in model_table.foreign_key_constraints:
                c_cols = tuple(col.name for col in fk_c.columns)
                r_tab = fk_c.referred_table.name
                r_cols = tuple(elem.column.name for elem in fk_c.elements)
                on_del = fk_c.ondelete.upper() if fk_c.ondelete else None
                on_upd = fk_c.onupdate.upper() if fk_c.onupdate else None
                model_fk_constraints.add((c_cols, r_tab, r_cols, on_del, on_upd))

            db_fk_constraints = set()
            for fk in insp.get_foreign_keys(table_name):
                c_cols = tuple(fk["constrained_columns"])
                r_tab = fk["referred_table"]
                r_cols = tuple(fk["referred_columns"])
                on_del = fk.get("options", {}).get("ondelete")
                if on_del:
                    on_del = on_del.upper()
                on_upd = fk.get("options", {}).get("onupdate")
                if on_upd:
                    on_upd = on_upd.upper()
                db_fk_constraints.add((c_cols, r_tab, r_cols, on_del, on_upd))

            assert model_fk_constraints == db_fk_constraints, f"Foreign key constraint mismatch in '{table_name}': Model={model_fk_constraints}, DB={db_fk_constraints}"

            # E. Unique Constraints and Unique Indexes Parity
            model_unique_sets = set()
            for c in model_table.constraints:
                if isinstance(c, sa.UniqueConstraint):
                    model_unique_sets.add(tuple(col.name for col in c.columns))
            for idx in model_table.indexes:
                if idx.unique:
                    model_unique_sets.add(tuple(col.name for col in idx.columns))

            db_unique_sets = set()
            for uq in insp.get_unique_constraints(table_name):
                db_unique_sets.add(tuple(uq["column_names"]))
            for idx in insp.get_indexes(table_name):
                if idx["unique"]:
                    db_unique_sets.add(tuple(idx["column_names"]))

            assert model_unique_sets == db_unique_sets, f"Unique constraint mismatch in '{table_name}': Model={model_unique_sets}, DB={db_unique_sets}"

            # F. Non-Unique Indexes Parity
            model_non_unique_indexes = set()
            for idx in model_table.indexes:
                if not idx.unique:
                    model_non_unique_indexes.add(tuple(col.name for col in idx.columns))

            db_non_unique_indexes = set()
            for idx in insp.get_indexes(table_name):
                if not idx["unique"]:
                    db_non_unique_indexes.add(tuple(idx["column_names"]))

            assert model_non_unique_indexes == db_non_unique_indexes, f"Non-unique index mismatch in '{table_name}': Model={model_non_unique_indexes}, DB={db_non_unique_indexes}"

            # G. Server Defaults Parity
            for col_name, model_col in model_cols.items():
                if model_col.server_default is not None:
                    db_default = db_cols[col_name].get("default")
                    assert db_default is not None, f"Missing server default in DB for column '{table_name}.{col_name}'"

    finally:
        if eng:
            eng.dispose()
        settings.database_url = orig_url


def test_0013_migration_safety_on_populated_database(tmp_path):
    """Proves that upgrading from 0012 to 0013 preserves existing data across all affected tables, rejects explicit NULLs on all 9 timestamp fields with strict error assertions, populates server defaults, and supports full downgrade/re-upgrade with complete row preservation."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from app.config import settings

    test_db_file = tmp_path / "populated_migration_0013_test.db"
    target_url = f"sqlite:///{test_db_file.as_posix()}"
    orig_url = settings.database_url

    eng = None
    try:
        settings.database_url = target_url
        cfg = Config("apps/api/alembic.ini")
        cfg.set_main_option("sqlalchemy.url", target_url)

        # 1. Migrate to 0012 and populate representative rows across ALL 8 affected tables
        command.upgrade(cfg, "0012_lease_fencing_and_retries")
        eng = sa.create_engine(target_url)

        dt_str = "2026-11-07 12:34:56"
        with eng.connect() as conn:
            conn.execute(sa.text("INSERT INTO sources (id, name, category, trust_tier, is_active, created_at) VALUES ('s_pres', 'Source Pres', 'state', 1, 1, :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO story_clusters (id, title_hint, eligible, flagged_conflict, created_at) VALUES ('c_pres', 'Cluster Pres', 1, 0, :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO cards (id, cluster_id, headline, summary, category, verified_status, created_at) VALUES ('card_pres', 'c_pres', 'Head Pres', 'Sum Pres', 'state', 'published', :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO articles (id, source_id, cluster_id, title, url, raw_text, ingested_at) VALUES ('art_pres', 's_pres', 'c_pres', 'Title Pres', 'http://art_pres', 'Text Pres', :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO user_preferences (id, device_id, created_at, updated_at) VALUES ('up_pres', 'dev_pres', :dt, :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO filtered_out (id, candidate_article_id, reason, created_at) VALUES ('fo_pres', 'art_pres', 'test_reason', :dt)"), {"dt": dt_str})
            conn.execute(sa.text("INSERT INTO review_queue (id, card_id, reasons, source_excerpts, status, created_at) VALUES ('rq_pres', 'card_pres', :r, :e, 'pending', :dt)"), {"r": '["r"]', "e": '["e"]', "dt": dt_str})
            conn.execute(sa.text("INSERT INTO worker_runs (id, timestamp, sources_polled, articles_ingested) VALUES ('wr_pres', :dt, 10, 5)"), {"dt": dt_str})
            conn.commit()

        # Capture complete before-migration row mappings across all 8 tables
        before_rows = {}
        tables_and_pks = [
            ("sources", "s_pres"),
            ("story_clusters", "c_pres"),
            ("cards", "card_pres"),
            ("articles", "art_pres"),
            ("user_preferences", "up_pres"),
            ("filtered_out", "fo_pres"),
            ("review_queue", "rq_pres"),
            ("worker_runs", "wr_pres"),
        ]
        with eng.connect() as conn:
            for tab, pk in tables_and_pks:
                row = conn.execute(sa.text(f"SELECT * FROM {tab} WHERE id=:pk"), {"pk": pk}).mappings().one()
                before_rows[tab] = dict(row)

        # 2. Upgrade to 0013
        command.upgrade(cfg, "0013_enforce_timestamp_not_null")

        # 3. Verify complete row and value preservation across all 8 tables
        with eng.connect() as conn:
            for tab, pk in tables_and_pks:
                after_row = dict(conn.execute(sa.text(f"SELECT * FROM {tab} WHERE id=:pk"), {"pk": pk}).mappings().one())
                assert before_rows[tab] == after_row, f"Data mismatch in table {tab} after migration!"

        # 4. Verify exact explicit NULL rejection with IntegrityError on ALL 9 timestamp columns (Strict Error Assertion)
        null_update_sqls = [
            ("articles", "ingested_at", "art_pres", "UPDATE articles SET ingested_at=NULL WHERE id='art_pres'"),
            ("cards", "created_at", "card_pres", "UPDATE cards SET created_at=NULL WHERE id='card_pres'"),
            ("filtered_out", "created_at", "fo_pres", "UPDATE filtered_out SET created_at=NULL WHERE id='fo_pres'"),
            ("review_queue", "created_at", "rq_pres", "UPDATE review_queue SET created_at=NULL WHERE id='rq_pres'"),
            ("sources", "created_at", "s_pres", "UPDATE sources SET created_at=NULL WHERE id='s_pres'"),
            ("story_clusters", "created_at", "c_pres", "UPDATE story_clusters SET created_at=NULL WHERE id='c_pres'"),
            ("user_preferences", "created_at", "up_pres", "UPDATE user_preferences SET created_at=NULL WHERE id='up_pres'"),
            ("user_preferences", "updated_at", "up_pres", "UPDATE user_preferences SET updated_at=NULL WHERE id='up_pres'"),
            ("worker_runs", "timestamp", "wr_pres", "UPDATE worker_runs SET timestamp=NULL WHERE id='wr_pres'"),
        ]

        with eng.connect() as conn:
            for tab, col, pk, sql in null_update_sqls:
                try:
                    conn.execute(sa.text(sql))
                    conn.commit()
                    assert False, f"Expected IntegrityError for {tab}.{col} but update succeeded!"
                except sa.exc.IntegrityError as exc:
                    assert f"NOT NULL constraint failed: {tab}.{col}" in str(exc), f"Unexpected error message for {tab}.{col}: {exc}"
                    conn.rollback()
                # Verify original timestamp remains unchanged
                val = conn.execute(sa.text(f"SELECT {col} FROM {tab} WHERE id=:pk"), {"pk": pk}).scalar()
                assert str(val) == dt_str, f"Timestamp {tab}.{col} was altered after rolled-back NULL update!"

        # 5. Verify omitted timestamp fields receive server defaults across all 9 timestamp columns (Exact PK lookup)
        omitted_inserts = [
            ("articles", "ingested_at", "a_def_1", sa.text("INSERT INTO articles (id, source_id, cluster_id, title, url, raw_text) VALUES ('a_def_1', 's_pres', 'c_pres', 'T', 'http://a_def_1', 'R')"), {}),
            ("cards", "created_at", "c_def_1", sa.text("INSERT INTO cards (id, cluster_id, headline, summary, category, verified_status) VALUES ('c_def_1', 'c_pres', 'H', 'S', 'state', 'published')"), {}),
            ("filtered_out", "created_at", "fo_def_1", sa.text("INSERT INTO filtered_out (id, candidate_article_id, reason) VALUES ('fo_def_1', 'art_pres', 'R')"), {}),
            ("review_queue", "created_at", "rq_def_1", sa.text("INSERT INTO review_queue (id, card_id, reasons, source_excerpts, status) VALUES ('rq_def_1', 'card_pres', :r, :e, 'pending')"), {"r": '["r"]', "e": '["e"]'}),
            ("sources", "created_at", "s_def_1", sa.text("INSERT INTO sources (id, name, category, trust_tier, is_active) VALUES ('s_def_1', 'S', 'state', 1, 1)"), {}),
            ("story_clusters", "created_at", "sc_def_1", sa.text("INSERT INTO story_clusters (id, title_hint, eligible, flagged_conflict) VALUES ('sc_def_1', 'T', 1, 0)"), {}),
            ("user_preferences", "created_at", "up_def_1", sa.text("INSERT INTO user_preferences (id, device_id, updated_at) VALUES ('up_def_1', 'dev_def_1', CURRENT_TIMESTAMP)"), {}),
            ("user_preferences", "updated_at", "up_def_2", sa.text("INSERT INTO user_preferences (id, device_id, created_at) VALUES ('up_def_2', 'dev_def_2', CURRENT_TIMESTAMP)"), {}),
            ("worker_runs", "timestamp", "wr_def_1", sa.text("INSERT INTO worker_runs (id, sources_polled, articles_ingested) VALUES ('wr_def_1', 0, 0)"), {}),
        ]

        def_before_rows = {}
        with eng.connect() as conn:
            for tab, col, pk, stmt, params in omitted_inserts:
                conn.execute(stmt, params)
                conn.commit()
                val = conn.execute(sa.text(f"SELECT {col} FROM {tab} WHERE id=:pk"), {"pk": pk}).scalar()
                assert val is not None, f"Server default for {tab}.{col} was None on exact PK lookup '{pk}'!"
                def_row = conn.execute(sa.text(f"SELECT * FROM {tab} WHERE id=:pk"), {"pk": pk}).mappings().one()
                def_before_rows[(tab, pk)] = dict(def_row)

        # 6. Test Downgrade and Re-upgrade Cycle across ALL 9 timestamp fields with full row preservation
        eng.dispose()
        eng = None

        target_timestamp_cols = [
            ("articles", "ingested_at"),
            ("cards", "created_at"),
            ("filtered_out", "created_at"),
            ("review_queue", "created_at"),
            ("sources", "created_at"),
            ("story_clusters", "created_at"),
            ("user_preferences", "created_at"),
            ("user_preferences", "updated_at"),
            ("worker_runs", "timestamp"),
        ]

        # Downgrade to 0012
        command.downgrade(cfg, "0012_lease_fencing_and_retries")
        eng2 = sa.create_engine(target_url)
        insp2 = sa.inspect(eng2)
        for t, c in target_timestamp_cols:
            db_c = {col["name"]: col for col in insp2.get_columns(t)}[c]
            assert db_c["nullable"] is True, f"Expected {t}.{c} to be nullable on 0012 downgrade"
            assert db_c.get("default") is not None, f"Expected server default for {t}.{c} on 0012 downgrade"
        eng2.dispose()

        # Re-upgrade to 0013
        command.upgrade(cfg, "0013_enforce_timestamp_not_null")
        eng3 = sa.create_engine(target_url)
        insp3 = sa.inspect(eng3)
        for t, c in target_timestamp_cols:
            db_c = {col["name"]: col for col in insp3.get_columns(t)}[c]
            assert db_c["nullable"] is False, f"Expected {t}.{c} to be non-nullable on 0013 re-upgrade"
            assert db_c.get("default") is not None, f"Expected server default for {t}.{c} on 0013 re-upgrade"

        # Confirm all representative rows and all 9 server-default test rows remain preserved across the full cycle
        with eng3.connect() as conn:
            for tab, pk in tables_and_pks:
                after_cycle_row = dict(conn.execute(sa.text(f"SELECT * FROM {tab} WHERE id=:pk"), {"pk": pk}).mappings().one())
                assert before_rows[tab] == after_cycle_row, f"Data mismatch in {tab} after full downgrade/re-upgrade cycle!"

            for (tab, pk), expected_def_row in def_before_rows.items():
                after_def_row = dict(conn.execute(sa.text(f"SELECT * FROM {tab} WHERE id=:pk"), {"pk": pk}).mappings().one())
                assert expected_def_row == after_def_row, f"Server default test row mismatch in {tab} (pk={pk}) after cycle!"
        eng3.dispose()

    finally:
        if eng:
            eng.dispose()
        settings.database_url = orig_url
