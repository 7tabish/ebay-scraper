import re
import csv
import time
import json
from datetime import datetime
from collections import OrderedDict
from urllib.parse import urlparse

import scrapy


def write_to_csv(filename, mode, row_data):
    with open(filename, mode,
              encoding='utf-8', newline = '\n') as f:
        writer = csv.writer(f)
        for data in row_data:
            writer.writerow(data)


class EbaySpider(scrapy.Spider):
    name = 'ebay_spider'
    start_urls = ['https://www.google.com']
    base_url = 'https://www.ebay.co.uk/itm/'
    shipping_fee_url = base_url+'getrates?item={}&_trksid=&quantity=&country=3&co=0&cb=&_='
    output_filename = 'output/eBay Stock Levels(parent).csv'

    csv_headers = [['Product Code', 'Item Cost',
                    'Shipping Cost','Total Stock',
                    'Status', 'repricer_name']]
    rows_data = []

    custom_settings = {
        'CONCURRENT_REQUESTS': '32',
    }

    trim_cost = re.compile(r'[^\d.,]+')

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EbaySpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_idle, scrapy.signals.spider_idle)
        return spider

    def spider_idle(self, spider):
        self.logger.info('Writing data to csv')
        write_to_csv(self.output_filename, 'a', self.rows_data)

    def __init__(self):
        print('in init')
        with open('input/eBay Inventory.csv', 'r') as file:
            self.csv_rows = [x for x in csv.DictReader(file)]

    def parse(self, response):
        #write headers
        write_to_csv(self.output_filename, 'w', self.csv_headers)

        for csv_row in self.csv_rows[1:]:
            sku = csv_row.get('sku')
            repricer_name = csv_row.get('repricer_name')

            url = self.base_url + sku.replace('FLEA ', '')
            yield scrapy.Request(url,
                                 dont_filter=True,
                                 callback=self.parse_product,
                                 meta={'product_code': sku,
                                       'repricer_name': repricer_name}
                                 )


    def parse_product(self, response):
        print('code ',response.status)
        item = OrderedDict()
        repricer_name = response.meta['repricer_name']
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
            item['repricer_name'] = repricer_name

            row_data = [item.get('Product Code'), item.get('Item Cost'),
                        item.get('Shipping Cost'),item.get('Total Stock'),
                        item.get('Status'), item.get('repricer_name')]
            self.rows_data.append(row_data)
        else:
            yield self.get_product_details(response, item, repricer_name )

    def get_product_details(self, response, item, repricer_name ):
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

        #get shipping fee by making request
        sku = item['Product Code'].replace('FLEA ', '')
        item['repricer_name'] = repricer_name

        return scrapy.Request(self.shipping_fee_url.format(sku),
                             callback=self.get_shipping_fee,
                             meta={'item': item})

    def get_shipping_fee(self,response):
        item = response.meta['item']

        shipping_response = json.loads(response.text).get('shippingSummary')\
                            or ''
        shipping_response = scrapy.Selector(text=shipping_response)
        item['Shipping Cost'] = shipping_response.css('span#fshippingCost span::text').get('')

        item['Shipping Cost'] = self.trim_cost.sub('', item['Shipping Cost'])
        if item['Shipping Cost'] == '':
            item['Shipping Cost'] = 0

        row_data = [item.get('Product Code'), item.get('Item Cost'),
                    item.get('Shipping Cost'), item.get('Total Stock'),
                    item.get('Status'), item.get('repricer_name')]

        self.rows_data.append(row_data)

