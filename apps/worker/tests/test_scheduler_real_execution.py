from __future__ import annotations

import http.server
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Article, Base, IngestionLease, IngestionRequest, Source, WorkerRun, new_id

RSS_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Deterministic Scheduler Test Feed</title>
 <link>http://127.0.0.1</link>
 <description>Fixture feed for process-level APScheduler execution verification</description>
 <item>
  <title>Autonomous Satellite Telemetry Confirmed by Space Command</title>
  <link>http://127.0.0.1/news/satellite-telemetry-confirmed-991</link>
  <description>Ground stations confirmed telemetry reception from the payload at 12:00 UTC.</description>
  <pubDate>Fri, 31 Oct 2026 12:00:00 GMT</pubDate>
 </item>
</channel>
</rss>
"""


class MockRSSServerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(RSS_FIXTURE_XML.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress server request logging in test output
        pass


def test_actual_worker_process_scheduler_execution():
    """Proves that APScheduler in a separate OS process executes RSS ingestion on interval,
    inserts articles, records WorkerRuns, and safely skips duplicates on subsequent intervals.
    """
    # 1. Start local mock HTTP server on a free port
    server = http.server.HTTPServer(("127.0.0.1", 0), MockRSSServerHandler)
    server_port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "scheduler_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    try:
        # Create all schema tables on the isolated database
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        # Seed 1 active RSS source pointing to our local mock server
        Session = sessionmaker(bind=engine)
        seed_db = Session()
        source_id = new_id()
        try:
            feed_url = f"http://127.0.0.1:{server_port}/rss.xml"
            src = Source(
                id=source_id,
                name="Scheduler Verification Wire",
                category="national",
                rss_url=feed_url,
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

        # 3. Environment configuration for the worker subprocess
        env = os.environ.copy()
        env["DATABASE_URL"] = db_url
        env["RSS_INGEST_INTERVAL_SECONDS"] = "2"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = f"{worker_dir};{api_dir};{repo_dir}"
        env["RUN_ONCE"] = ""
        # Point to empty LLM key so process runs purely on local deterministic heuristics
        env["LLM_API_KEY"] = ""
        env["GEMINI_API_KEY"] = ""
        env["GROQ_API_KEY"] = ""
        env["OPENROUTER_API_KEY"] = ""

        # 4. Launch real worker OS process
        cmd = [sys.executable, "-m", "worker.main"]
        proc = subprocess.Popen(
            cmd,
            cwd=str(worker_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Let the process run for 15.0 seconds (allowing multiple interval triggers at 2s intervals)
            time.sleep(15.0)
        finally:
            proc.terminate()
            stdout_data, stderr_data = "", ""
            try:
                stdout_data, stderr_data = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_data, stderr_data = proc.communicate(timeout=2)
            server.shutdown()
            print(f"WORKER STDOUT:\n{stdout_data}")
            if stderr_data:
                print(f"WORKER STDERR:\n{stderr_data}")

        # 5. Connect to the test database and inspect execution artifacts
        verify_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        VerifySession = sessionmaker(bind=verify_engine)
        vdb = VerifySession()
        try:
            # Check articles table: exactly 1 article should exist (first cycle inserted, second cycle ignored duplicate)
            articles = vdb.query(Article).all()
            assert len(articles) == 1, f"Expected exactly 1 article, found {len(articles)}"
            assert "Autonomous Satellite Telemetry" in articles[0].title
            assert articles[0].source_id == source_id

            # Check worker_runs table: at least 2 distinct scheduled runs must have been recorded
            runs = (
                vdb.query(WorkerRun)
                .filter(WorkerRun.provider == "rss_pipeline")
                .order_by(WorkerRun.timestamp.asc())
                .all()
            )
            assert len(runs) >= 2, f"Expected at least 2 worker runs recorded by APScheduler, found {len(runs)}"

            # First cycle should have ingested 1 article
            first_run = runs[0]
            assert first_run.sources_polled >= 1
            assert first_run.articles_ingested == 1

            # Second cycle should have polled the source but ingested 0 new articles (deduplication)
            second_run = runs[1]
            assert second_run.sources_polled >= 1
            assert second_run.articles_ingested == 0

        finally:
            vdb.close()
            verify_engine.dispose()
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
