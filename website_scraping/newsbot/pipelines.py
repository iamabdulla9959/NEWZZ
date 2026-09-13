import json
import logging
import sqlite3
from itemadapter import ItemAdapter

logger = logging.getLogger(__name__)


class JsonWriterPipeline:
    """
    Appends extracted NewsItems as line-delimited JSON (JSONL) records to news.json.
    Configured at Priority 300.
    """

    def open_spider(self, spider):
        # Open in append mode so repeated scheduled runs accumulate new data
        self.file = open("news.json", "a", encoding="utf-8")

    def close_spider(self, spider):
        if hasattr(self, "file") and not self.file.closed:
            self.file.close()

    def process_item(self, item, spider):
        line = json.dumps(ItemAdapter(item).asdict(), ensure_ascii=False)
        self.file.write(line + "\n")
        return item


class SQLitePipeline:
    """
    Stores extracted NewsItems into a local SQLite database with duplicate URL detection.
    Configured at Priority 400.
    """

    def __init__(self, db_name="news.db"):
        self.db_name = db_name
        self.crawler = None
        self.connection = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self, spider):
        self.connection = sqlite3.connect(self.db_name)
        self.cursor = self.connection.cursor()
        # Initialize schema with a UNIQUE constraint on the article link
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                link TEXT UNIQUE NOT NULL,
                summary TEXT,
                content TEXT,
                author TEXT,
                published_date TEXT,
                source TEXT,
                fetched_at TEXT
            )
            """
        )
        # Create an index on 'source' for efficient partitioned querying
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_source ON articles (source)"
        )
        self.connection.commit()

    def close_spider(self, spider):
        if self.connection:
            self.connection.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if not self.cursor or not self.connection:
            return item

        try:
            self.cursor.execute(
                """
                INSERT INTO articles (title, link, summary, content, author, published_date, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    adapter.get("title", ""),
                    adapter.get("link", ""),
                    adapter.get("summary", ""),
                    adapter.get("content", ""),
                    adapter.get("author", ""),
                    adapter.get("published_date", ""),
                    adapter.get("source", ""),
                    adapter.get("fetched_at", ""),
                ),
            )
            self.connection.commit()
        except sqlite3.IntegrityError:
            # On duplicate URL, increment Scrapy stats counter and log at debug level
            if self.crawler and self.crawler.stats:
                self.crawler.stats.inc_value("dedup/skipped")
            spider.logger.debug(f"Duplicate article skipped: {adapter.get('link')}")

        return item
