from csv import DictReader
from collections import OrderedDict
from datetime import datetime
import scrapy
import re


class EbaySpider(scrapy.Spider):
    name = 'ebay_spider'
    base_url = 'https://www.ebay.co.uk/itm/'


    custom_settings = {
        'FEED_URI': f'output/ebay-data-{datetime.today().strftime("%d-%m-%Y")}.csv',
        'FEED_FORMAT': 'csv',
    }



    handle_httpstatus_list = [400, 401, 402, 403, 404, 405, 406, 407, 409, 500, 501, 502, 503, 504, 505, 506, 507, 509]

    def __init__(self):
        with open('input/eBay Inventory.csv','r') as file:
            self.sku_list = [x['sku'] for x in DictReader(file)]

    def start_requests(self):
        headers = {
            'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N)'
                          ' AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/87.0.4280.66 Mobile Safari/537.36'
        }

        for sku in self.sku_list[1:100]:
            url = self.base_url + sku.replace('FLEA ', '')
            #url1 = self.scraper_api_t.format('https://www.ebay.co.uk/itm/333342244478')
            yield scrapy.Request(url,
                                 callback=self.parse,
                                 meta={'product_code':sku}
                                 )

    def parse(self, response):
        item = OrderedDict()
        item['Product Code'] = response.meta['product_code']

        if response.css('p.error-header__headline'):
            item['Item Cost'] = 0
            # item['Shipping'] = 0
            item['Total Stock'] = 0
            item['Status'] = 'Product not found!'

            yield item

        else:
           yield self.get_product_details(response, item)


    def get_product_details(self, response, item):
        item['Item Cost'] = response.css('span[itemprop="price"]::text').get(0)
        # item['Shipping Cost'] =response.css('span#shSummary *::text').getall()
        out_of_stock = response.css('#w1-6-_msg::text').get('')

        if out_of_stock:
            item['Total Stock'] = 0
            item['Status'] = out_of_stock
        else:
            status_msg = response.css('span#qtySubTxt span::text').get('').strip()

            # check is the numeric value (stock) exists in status_msg
            total_stock = re.findall(r'[0-9]+', status_msg)
            if total_stock:
                item['Total Stock'] = total_stock[0]
                item['Status'] = 'available'

            # if no numeric value then set the status_msg as it is to item
            else:
                if status_msg:
                    item['Total Stock'] = 3
                    item['Status'] = status_msg
                else:
                    item['Total Stock'] = 0
                    item['Status'] = 'click & collect only'

        item['url'] = response.url

        return item