import re
import csv
import time
import json
import requests
from datetime import datetime
from collections import OrderedDict
from urllib.parse import urlparse


import scrapy


def write_to_csv(filename, mode, row_data):
    with open(filename, mode,
              encoding='utf-8', newline = '\n') as f:
        writer = csv.writer(f)
        writer.writerow(row_data)


class EbaySpider(scrapy.Spider):
    name = 'ebay_spider'
    start_urls = ['https://www.google.com']
    base_url = 'https://www.ebay.co.uk/itm/'
    shipping_fee_url = base_url+'getrates?item={}&_trksid=&quantity=&country=3&co=0&cb=&_='

    input_filename = f'output/{datetime.now().strftime("%m-%d-%y")}.csv'

    handle_httpstatus_list = [400, 401, 402, 403, 404, 405,
                              406, 407, 409, 500, 501, 502,
                              503, 504, 505, 506, 507, 509]
    csv_headers = ['Product Code', 'Item Cost', 'Total Stock',
                   'Status', 'Shipping Cost']

    trim_cost = re.compile(r'[^\d.,]+')

    def __init__(self):
        with open('input/eBay Inventory.csv', 'r') as file:
            self.sku_list = [x['sku'] for x in csv.DictReader(file)]

    # @classmethod
    # def from_crawler(cls, crawler, *args, **kwargs):
    #     spider = super(EbaySpider, cls).from_crawler(crawler, *args, **kwargs)
    #     crawler.signals.connect(spider.spider_idle, scrapy.signals.spider_idle)
    #     return spider
    #
    # def spider_idle(self, spider):
    #     print('*****************wait for 30 sec..')
    #     time.sleep(30)
    #     req = scrapy.Request(url=self.start_urls[0], callback=self.parse, dont_filter=True)
    #     self.crawler.engine.crawl(req, spider)

    def parse(self, response):
        #write headers
        write_to_csv(self.input_filename, 'w', self.csv_headers)

        for sku in self.sku_list[1:10]:
            url = self.base_url + sku.replace('FLEA ', '')
            yield scrapy.Request(url,
                                 dont_filter=True,
                                 callback=self.parse_product,
                                 meta={'product_code': sku}
                                 )


    def parse_product(self, response):
        item = OrderedDict()
        item['Product Code'] = response.meta['product_code']
        query = urlparse(response.url).query

        # query will exist if page is redirect to other product
        if (query or response.css('p.error-header__headline')):
            self.logger.info(f'Product not found'
                             f' for product id {item["Product Code"]}')
            item['Item Cost'] = 0
            item['Total Stock'] = 0
            item['Status'] = 'Product not found!'
            item['Shipping Cost'] = 0

            row_data = [item['Product Code'], item['Item Cost'], item['Total Stock'],
                        item['Status'], item['Shipping Cost']]

            self.logger.info('writting item: ',item)
            write_to_csv(self.input_filename, 'a', row_data)
        else:
            yield self.get_product_details(response, item)

    def get_product_details(self, response, item):
        item['Item Cost'] = response.css('span[itemprop="price"]::text').get(0)

        if item['Item Cost']:
            # remove currency symbol from cost
            item['Item Cost'] = self.trim_cost.sub('', item['Item Cost'])

        out_of_stock = response.css('#w1-6-_msg::text').get('').strip()
        if out_of_stock:
            item['Total Stock'] = 0
            item['Status'] = out_of_stock
        else:
            status_msg = response.css('span#qtySubTxt'
                                      ' span::text').get('').strip()

            # check is the numeric value (stock) exists in status_msg
            total_stock = re.findall(r'[0-9]+',
                                     status_msg)
            if total_stock:
                item['Total Stock'] = total_stock[0]
                item['Status'] = 'available'

            # if no numeric value then set the status_msg as it is to item
            # and default stock value is 3
            else:
                if status_msg:
                    item['Total Stock'] = 3
                    item['Status'] = status_msg
                else:
                    item['Total Stock'] = 0
                    item['Status'] = 'click & collect only'

        #get shipping fee by making get request
        sku = item['Product Code'].replace('FLEA ', '')
        shipping_response = requests.get(self.shipping_fee_url.format(sku))
        shipping_response = json.loads(shipping_response.text)
        shipping_response = scrapy.Selector(text=shipping_response['shippingSummary'])
        item['Shipping Cost'] = shipping_response.css('span#fshippingCost span::text').get(0)
        if item['Shipping Cost'] == 'Free':
            item['Shipping Cost'] = 0

        row_data = [item['Product Code'], item['Item Cost'], item['Total Stock'],
                    item['Status'], item['Shipping Cost']]

        self.logger.info('Writing item: ',item)
        write_to_csv(self.input_filename, 'a', row_data)


