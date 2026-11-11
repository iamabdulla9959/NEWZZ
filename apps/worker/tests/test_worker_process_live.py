import http.server
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Article, Base, Source, WorkerRun, new_id

FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture Local News</title>
    <link>http://127.0.0.1/feed</link>
    <description>Deterministic Test Feed</description>
    <item>
      <title>Controlled Process Test Article 2026</title>
      <link>http://127.0.0.1/article/live-process-101</link>
      <description>Demonstrating full real OS process execution without third-party network access.</description>
      <pubDate>Wed, 31 Oct 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class MockRSSHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(FIXTURE_XML.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging


@pytest.fixture(scope="module")
def mock_rss_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockRSSHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/feed.xml"
    server.shutdown()


def test_actual_worker_process_live_execution(mock_rss_server, tmp_path):
    """Executes a real OS-level worker process against a disposable database and fixture RSS server."""
    db_file = tmp_path / "disposable_worker_proof.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # Initialize schema in disposable database
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed the mock RSS source
    source = Source(
        id=new_id(),
        name="Fixture Local News",
        category="national",
        region="IN",
        rss_url=mock_rss_server,
        trust_tier="1",
        is_active=True,
    )
    db.add(source)
    db.commit()
    db.close()

    repo_root = Path(__file__).resolve().parents[3]
    worker_script = repo_root / "apps" / "worker" / "worker" / "main.py"

    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["PYTHONUNBUFFERED"] = "1"
    env["DATABASE_URL"] = db_url
    env["RUN_ONCE"] = "1"
    env["PYTHONPATH"] = f"{repo_root};{repo_root / 'apps' / 'api'};{repo_root / 'apps' / 'worker'}"

    # 1. Launch worker as a real separate operating-system process
    proc1 = subprocess.Popen(
        [sys.executable, str(worker_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(repo_root),
    )
    pid1 = proc1.pid
    stdout1, stderr1 = proc1.communicate(timeout=30)

    print(f"\n[Process Proof Run 1] PID: {pid1}, ExitCode: {proc1.returncode}")
    print(f"Stdout:\n{stdout1}")
    if stderr1:
        print(f"Stderr:\n{stderr1}")

    assert proc1.returncode == 0
    assert "[RSS]" in stdout1
    assert "ingest_new=1" in stdout1

    # Verify database received the expected Article and WorkerRun
    db = Session()
    articles = db.query(Article).all()
    assert len(articles) == 1
    assert articles[0].title == "Controlled Process Test Article 2026"
    assert articles[0].url == "http://127.0.0.1/article/live-process-101"

    runs = db.query(WorkerRun).filter(WorkerRun.provider == "rss_pipeline").all()
    assert len(runs) >= 1
    assert runs[-1].articles_ingested == 1
    db.close()

    # 2. Second pass: restart worker and confirm duplicate ingestion does NOT occur
    proc2 = subprocess.Popen(
        [sys.executable, str(worker_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(repo_root),
    )
    pid2 = proc2.pid
    stdout2, stderr2 = proc2.communicate(timeout=30)

    print(f"\n[Process Proof Run 2 - Deduplication Check] PID: {pid2}, ExitCode: {proc2.returncode}")
    print(f"Stdout:\n{stdout2}")

    assert proc2.returncode == 0
    assert "ingest_new=0" in stdout2

    # Verify no duplicate Article rows exist
    db = Session()
    articles_after = db.query(Article).all()
    assert len(articles_after) == 1
    runs_after = db.query(WorkerRun).filter(WorkerRun.provider == "rss_pipeline").all()
    assert len(runs_after) >= 2
    assert runs_after[-1].articles_ingested == 0
    db.close()


def test_actual_worker_process_scheduler_startup(tmp_path):
    """Launches the worker in scheduler mode to verify scheduler initialization and single-job registration."""
    db_file = tmp_path / "scheduler_worker_proof.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)

    repo_root = Path(__file__).resolve().parents[3]
    worker_script = repo_root / "apps" / "worker" / "worker" / "main.py"

    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["PYTHONUNBUFFERED"] = "1"
    env["DATABASE_URL"] = db_url
    env.pop("RUN_ONCE", None)  # Ensure scheduler mode
    env["PYTHONPATH"] = f"{repo_root};{repo_root / 'apps' / 'api'};{repo_root / 'apps' / 'worker'}"

    proc = subprocess.Popen(
        [sys.executable, str(worker_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(repo_root),
    )
    pid = proc.pid
    first_line = proc.stdout.readline()
    proc.terminate()
    stdout_rest, stderr = proc.communicate(timeout=10)
    stdout = first_line + stdout_rest

    print(f"\n[Scheduler Banner Proof] PID: {pid}")
    print(f"Stdout:\n{stdout}")

    assert "Worker [" in stdout
    assert "started with schedules:" in stdout
    assert "ManualRequestsPoll every 10s" in stdout
    assert "RSS every 15m" in stdout
