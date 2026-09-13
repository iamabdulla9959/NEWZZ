import os
from dataclasses import dataclass, field
from typing import List
import yaml


@dataclass
class FeedSource:
    name: str
    url: str


@dataclass
class Config:
    telegram_bot_token: str
    db_path: str
    fetch_interval_min: int
    user_agent: str
    request_timeout_seconds: int
    feeds: List[FeedSource] = field(default_factory=list)


DEFAULT_FEEDS = [
    FeedSource("BBC News", "http://feeds.bbci.co.uk/news/rss.xml"),
    FeedSource("The New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    FeedSource("The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss"),
    FeedSource("The Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    FeedSource("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    FeedSource("WION News", "https://news.google.com/rss/search?q=site:wionews.com&hl=en-IN&gl=IN&ceid=IN:en"),
]


def load_config(feeds_path: str = "feeds.yaml") -> Config:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "news_aggregator.db").strip()
    fetch_interval = int(os.getenv("FETCH_INTERVAL_MIN", "15"))

    user_agent = "NewsAggregatorBot/1.0 (+https://github.com/nuhmanpk/WebScrapper)"
    timeout = 15
    feeds = []

    if os.path.exists(feeds_path):
        try:
            with open(feeds_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                user_agent = data.get("user_agent", user_agent)
                timeout = int(data.get("request_timeout_seconds", timeout))
                for item in data.get("feeds", []):
                    if "name" in item and "url" in item:
                        feeds.append(FeedSource(name=item["name"], url=item["url"]))
        except Exception as e:
            # Fall back gracefully to built-in default feeds
            pass

    if not feeds:
        feeds = DEFAULT_FEEDS

    return Config(
        telegram_bot_token=token,
        db_path=db_path,
        fetch_interval_min=fetch_interval,
        user_agent=user_agent,
        request_timeout_seconds=timeout,
        feeds=feeds,
    )
