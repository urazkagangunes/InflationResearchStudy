import os
from datetime import datetime
import csv
import logging
from scrapling.spiders import Spider, Response

# Set up logging to track progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BeymenSpider(Spider):
    name = "beymen_club_spider"
    
    # Base category URLs for Men and Women
    start_urls = [
        "https://www.beymenclub.com/tr/erkek-30060",
        "https://www.beymenclub.com/tr/kadin-30058"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepare directory and filename
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', '..', '..', 'Datas', 'ClothingStores', 'beymenclub')
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, f"{today_str}.csv")
        
        # Open CSV file to write products
        self.csv_file = open(file_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.csv_file, fieldnames=["Category", "Product Name", "Price"])
        self.writer.writeheader()

    def __del__(self):
        # Ensure the file is closed when the spider finishes
        if hasattr(self, 'csv_file') and not self.csv_file.closed:
            self.csv_file.close()

    async def parse(self, response: Response):
        logging.info(f"Parsing page: {response.url}")
        
        # Determine category based on URL
        category = "Erkek" if "/erkek" in response.url.lower() else "Kadın" if "/kadin" in response.url.lower() else "Unknown"
        
        # Select all product cards
        products = response.css('.m-productCard')
        logging.info(f"Found {len(products)} products on this page.")
        
        for product in products:
            # Extract product title (brand is in title, desc is actual name)
            title = product.xpath('.//*[contains(@class, "m-productCard__desc")]/text()').get()
            if not title or not title.strip():
                title = product.xpath('.//img/@alt').get()
                
            # Extract product price
            price = product.css('.m-productCard__newPrice::text').get()
            if not price:
                price = product.css('.m-productCard__lastPrice::text').get()
            if not price:
                price = product.css('.m-productPrice__new::text').get()
            
            if title and price:
                title = title.strip()
                price = price.strip()
                self.writer.writerow({
                    "Category": category,
                    "Product Name": title,
                    "Price": price
                })
        
        # Handle Pagination
        # If products are found, manually construct the next page URL to continue until empty
        if len(products) > 0:
            import urllib.parse
            parsed_url = urllib.parse.urlparse(response.url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Beymen Club typically uses 'sayfa' parameter for pagination
            current_page = int(query_params.get('sayfa', ['1'])[0])
            
            # For this test, let's limit to 50 pages to prevent infinite loops,
            # or it will naturally stop when products list is empty.
            if current_page < 50:
                next_page_num = current_page + 1
                query_params['sayfa'] = [str(next_page_num)]
                new_query = urllib.parse.urlencode(query_params, doseq=True)
                next_page_url = urllib.parse.urlunparse(parsed_url._replace(query=new_query))
                
                yield response.follow(next_page_url)
            
if __name__ == "__main__":
    # Start the spider
    logging.info("Starting Beymen Club Scraper...")
    spider = BeymenSpider()
    spider.start()
    logging.info("Scraping completed. Data saved to products.csv")
