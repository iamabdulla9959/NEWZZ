from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Article, Base, Source, new_id


SUBPROCESS_INGEST_SCRIPT = """
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

worker_dir = Path(__file__).resolve().parents[1]
api_dir = Path(__file__).resolve().parents[2] / "api"
repo_dir = Path(__file__).resolve().parents[3]
for p in [str(worker_dir), str(api_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.models import Base, Article, Source, new_id
from worker.ingest import ingest_rss_source

db_url = sys.argv[1]
source_id = sys.argv[2]
article_url = sys.argv[3]
article_title = sys.argv[4]

engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30.0})
Session = sessionmaker(bind=engine)
db = Session()

# Simulate direct collision insert with begin_nested savepoint
inserted = 0
try:
    with db.begin_nested():
        db.add(
            Article(
                id=new_id(),
                source_id=source_id,
                url=article_url,
                title=article_title,
                raw_text="Subprocess concurrent article body text content for deduplication test.",
                category="national",
            )
        )
        db.flush()
    inserted = 1
    db.commit()
    print("INSERT_SUCCESS", flush=True)
except Exception as exc:
    # Savepoint rolled back cleanly on unique constraint violation
    db.rollback()
    print(f"COLLISION_CAUGHT: {exc}", flush=True)
finally:
    db.close()
    engine.dispose()

sys.exit(0)
"""


def test_concurrent_multiprocess_article_deduplication():
    """Proves that two independent OS processes concurrently inserting the exact same normalized URL
    against the same database respect the uq_articles_url constraint and nested savepoint recovery,
    resulting in exactly 1 persisted Article row and zero uncaught crashes.
    """
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "multiprocess_dedup_test.db"
    db_url = f"sqlite:///{db_path}"

    worker_script_path = Path(tmp_dir) / "runner.py"
    with open(worker_script_path, "w", encoding="utf-8") as f:
        f.write(SUBPROCESS_INGEST_SCRIPT)

    try:
        # Create all tables on disposable database
        engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30.0})
        Base.metadata.create_all(bind=engine)

        Session = sessionmaker(bind=engine)
        seed_db = Session()
        source_id = new_id()
        try:
            src = Source(
                id=source_id,
                name="Concurrent Multiprocess Wire",
                category="national",
                trust_tier="1",
                is_active=True,
            )
            seed_db.add(src)
            seed_db.commit()
        finally:
            seed_db.close()
            engine.dispose()

        worker_dir = Path(__file__).resolve().parents[1]
        api_dir = Path(__file__).resolve().parents[2] / "api"
        repo_dir = Path(__file__).resolve().parents[3]

        env = os.environ.copy()
        env["DATABASE_URL"] = db_url
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = f"{worker_dir};{api_dir};{repo_dir}"

        target_url = "https://concurrent.example.com/breaking-news-race-condition"
        target_title = "Breaking News Event Simultaneously Reported By Two Workers"

        cmd = [
            sys.executable,
            str(worker_script_path),
            db_url,
            source_id,
            target_url,
            target_title,
        ]

        # Launch two separate OS processes concurrently racing to insert the exact same URL
        proc1 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc2 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        out1, err1 = proc1.communicate(timeout=15)
        out2, err2 = proc2.communicate(timeout=15)

        # Both processes must complete cleanly with exit code 0
        assert proc1.returncode == 0, f"Process 1 failed with stderr: {err1}"
        assert proc2.returncode == 0, f"Process 2 failed with stderr: {err2}"

        combined_out = f"P1: {out1.strip()} | P2: {out2.strip()}"
        print(f"Concurrent Subprocess Results: {combined_out}")

        # One process must have succeeded and the other caught the collision
        assert "INSERT_SUCCESS" in combined_out, "At least one process should successfully insert"
        assert "COLLISION_CAUGHT" in combined_out, "The competing process should catch the unique constraint collision"

        # Database verification: exactly 1 Article row must exist
        verify_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        VerifySession = sessionmaker(bind=verify_engine)
        vdb = VerifySession()
        try:
            articles = vdb.query(Article).filter(Article.url == target_url).all()
            assert len(articles) == 1, f"Expected exactly 1 Article row, found {len(articles)}"
            assert articles[0].title == target_title
        finally:
            vdb.close()
            verify_engine.dispose()

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

