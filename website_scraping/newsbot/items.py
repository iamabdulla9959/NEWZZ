import scrapy


class NewsItem(scrapy.Item):
    title = scrapy.Field()
    link = scrapy.Field()
    summary = scrapy.Field()
    content = scrapy.Field()
    author = scrapy.Field()
    published_date = scrapy.Field()
    source = scrapy.Field()
    fetched_at = scrapy.Field()
