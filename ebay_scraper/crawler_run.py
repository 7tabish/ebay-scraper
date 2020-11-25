import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor
from twisted.internet.task import deferLater

from ebay_scraper.ebay_scraper.spiders.ebay_spider import EbaySpider

def sleep(self, *args, seconds):
    """Non blocking sleep callback"""
    return deferLater(reactor, seconds, lambda: None)

process = CrawlerProcess()

def _crawl(result, spider):
    deferred = process.crawl(spider)
    deferred.addCallback(lambda results: print('waiting 2 min before restart...'))
    deferred.addCallback(sleep, seconds=120)
    deferred.addCallback(_crawl, spider)
    return deferred


_crawl(None, EbaySpider)
process.start()
