from datetime import datetime, timezone
from typing import Any
import scrapy
from scrapy.http import Response, TextResponse
from newsbot.items import NewsItem


class WionSpider(scrapy.Spider):
    """
    Polite crawler for WION News adhering to robots.txt and sitemap guidelines.
    """
    name = "wion"
    allowed_domains = ["wionews.com"]
    # WION's official real-time news sitemap published in robots.txt
    start_urls = ["https://www.wionews.com/sitemaps/news-sitemap.xml"]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 2.0,                  # 2 seconds between requests
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,    # Avoid concurrent hammering
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "USER_AGENT": "NewsAggregatorBot/1.0 (+https://github.com/nuhmanpk/WebScrapper)",
    }

    # pyrefly: ignore[bad-override-mutable-attribute]
    def parse(self, response: Response, **kwargs: Any) -> Any:
        """Parse the Google News XML sitemap to extract recent article URLs."""
        if not isinstance(response, TextResponse):
            return
        response.selector.remove_namespaces()
        article_urls = response.xpath("//url/loc/text()").getall()

        # Follow the 10 most recent article URLs
        for url in article_urls[:10]:
            yield response.follow(url.strip(), callback=self.parse_article)

    def parse_article(self, response: Response) -> Any:
        """Extract article metadata from WION's article HTML structure."""
        item = NewsItem()

        # Primary headline
        title = (
            response.css("h1::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or ""
        )
        item["title"] = title.strip()
        item["link"] = response.url

        # Summary / Description
        summary = (
            response.css("meta[property='og:description']::attr(content)").get()
            or response.css("meta[name='description']::attr(content)").get()
            or ""
        )
        item["summary"] = summary.strip()

        # Article body text (combining paragraph nodes)
        paragraphs = response.css("div.article-content p::text, div.content p::text, article p::text").getall()
        item["content"] = " ".join(p.strip() for p in paragraphs if p.strip())

        # Author / Byline
        author = (
            response.css("meta[name='author']::attr(content)").get()
            or response.css("span.author-name::text").get()
            or "WION Web Team"
        )
        item["author"] = author.strip()

        # Publication date
        pub_date = (
            response.css("meta[property='article:published_time']::attr(content)").get()
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        item["published_date"] = pub_date.strip()

        item["source"] = "WION News"
        item["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        yield item
