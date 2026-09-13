BOT_NAME = "newsbot"

SPIDER_MODULES = ["newsbot.spiders"]
NEWSPIDER_MODULE = "newsbot.spiders"

# ────────────────────────────────────────────────────────
# DEFENSIVE & ETHICAL SCRAPING CONFIGURATION
# ────────────────────────────────────────────────────────

# Obey robots.txt specifications (parses /robots.txt and respects Crawl-delay)
ROBOTSTXT_OBEY = True

# Identify your crawler clearly to the site operator
USER_AGENT = "LocalSecurityLabBot/1.0 (+http://localhost/bot-policy)"

# Polite concurrency and pacing
DOWNLOAD_DELAY = 2.0
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# AutoThrottle automatically adjusts request delays based on server response latency.
# NOTE: Scrapy's RobotsTxtMiddleware sets the download slot delay when Crawl-delay is present.
# AutoThrottle continuously adapts from this initial delay, which you can monitor
# via the detailed AUTOTHROTTLE_DEBUG logs.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = True

# Retry configuration for temporary network/rate-limiting errors
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

# Custom Downloader Middleware: Replace stock RetryMiddleware (priority 550)
# with RetryAfterMiddleware which honors HTTP 'Retry-After' response headers
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    "newsbot.middlewares.RetryAfterMiddleware": 550,
}

# Item processing pipelines
ITEM_PIPELINES = {
    "newsbot.pipelines.JsonWriterPipeline": 300,
    "newsbot.pipelines.SQLitePipeline": 400,
}

# UTF-8 encoding standard
FEED_EXPORT_ENCODING = "utf-8"
