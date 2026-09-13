import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, db_path: str = "news_aggregator.db"):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT UNIQUE NOT NULL,
                    summary TEXT,
                    author TEXT,
                    published_date TEXT,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles (source)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles (fetched_at)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id INTEGER PRIMARY KEY,
                    subscribed_at TEXT NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fetch_metadata (
                    source TEXT PRIMARY KEY,
                    last_fetched_at TEXT,
                    last_status TEXT,
                    last_error TEXT,
                    items_found INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def insert_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Inserts a batch of normalized articles.
        Returns ONLY the list of articles that were genuinely new and successfully inserted.
        """
        new_items = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            for art in articles:
                try:
                    cur.execute(
                        """
                        INSERT INTO articles (source, title, link, summary, author, published_date, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            art["source"],
                            art["title"],
                            art["link"],
                            art.get("summary", ""),
                            art.get("author", ""),
                            art.get("published_date", ""),
                            art["fetched_at"],
                        ),
                    )
                    new_items.append(art)
                except sqlite3.IntegrityError:
                    # Link already exists in database; skip duplicate
                    continue
            conn.commit()
        return new_items

    def get_latest_articles(self, limit: int = 10, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve the most recently fetched articles, optionally filtered by publisher source."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if source:
                cur.execute(
                    """
                    SELECT source, title, link, summary, author, published_date, fetched_at
                    FROM articles
                    WHERE source = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (source, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT source, title, link, summary, author, published_date, fetched_at
                    FROM articles
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def search_articles(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Case-insensitive substring search matching against article title and summary."""
        term = f"%{query.strip()}%"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT source, title, link, summary, author, published_date, fetched_at
                FROM articles
                WHERE title LIKE ? OR summary LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (term, term, limit),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def add_subscription(self, chat_id: int) -> bool:
        """Register a chat for automated 15-min push notifications. Returns True if newly added."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO subscriptions (chat_id, subscribed_at) VALUES (?, ?)",
                    (chat_id, now),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_subscription(self, chat_id: int) -> bool:
        """Remove a chat from subscription registry. Returns True if was present."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
            removed = cur.rowcount > 0
            conn.commit()
            return removed

    def is_subscribed(self, chat_id: int) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM subscriptions WHERE chat_id = ?", (chat_id,))
            return cur.fetchone() is not None

    def get_all_subscriptions(self) -> List[int]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM subscriptions")
            return [row["chat_id"] for row in cur.fetchall()]

    def record_fetch_metadata(self, source: str, status: str, items_found: int = 0, error: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO fetch_metadata (source, last_fetched_at, last_status, last_error, items_found)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    last_fetched_at = excluded.last_fetched_at,
                    last_status = excluded.last_status,
                    last_error = excluded.last_error,
                    items_found = excluded.items_found
                """,
                (source, now, status, error, items_found),
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate telemetry: counts per source, total articles, and last fetch timestamp."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source")
            counts = {row["source"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(*) as total FROM articles")
            total = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as subs FROM subscriptions")
            subs = cur.fetchone()["subs"]

            cur.execute("SELECT source, last_fetched_at, last_status FROM fetch_metadata")
            meta = {row["source"]: {"last_fetched": row["last_fetched_at"], "status": row["last_status"]} for row in cur.fetchall()}

        return {
            "total_articles": total,
            "active_subscriptions": subs,
            "source_counts": counts,
            "metadata": meta,
        }
