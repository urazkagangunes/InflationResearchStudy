import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import csv
import os
import random
import re

BASE_URL = "https://www.filtasyapi.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CONCURRENT_REQUESTS = 5
DELAY_RANGE = (0.5, 1.5)

class CategoryScanner:
    def __init__(self, base_url):
        self.base_url = base_url

    async def get_categories(self, session):
        async with session.get(self.base_url) as response:
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        categories = []

        # only first-level-navigation
        first_level = soup.select('li[data-selector="first-level-navigation"] > a')

        for item in first_level:
            name = item.get_text(strip=True)
            url = urljoin(self.base_url, item.get("href"))
            categories.append({"name": name, "url": url})

        print("categories count:", len(categories))
        return categories

class LinkCollector:
    async def collect_pages(self, session, category):
        page = 1
        all_category_pages = []
        
        while True:
            url = f"{category['url']}?sayfa={page}"
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        break
                    html = await response.text()
                
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".showcase") 
                
                if not items:
                    break

                all_category_pages.append({
                    "category": category["name"],
                    "url": url,
                    "html": html
                })
                
                # checking next pages
                next_btn = soup.select_one(".pagination-next")
                if not next_btn and page > 1:
                    break
                
                print(f"[{category['name']}] {page} pages scraped")
                page += 1
                await asyncio.sleep(random.uniform(*DELAY_RANGE))
                
            except Exception as e:
                print(f"error on page {url}: {e}")
                break

        return all_category_pages

class DataExtractor:
    def clean_price(self, price_str: str) -> float:

        if not price_str:
            return 0.0
        
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        
        if '.' in cleaned and ',' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
            
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def extract(self, page_data):
        soup = BeautifulSoup(page_data["html"], "html.parser")
        extracted_items = []
        items = soup.select(".showcase")

        for item in items:
            title_el = item.select_one(".showcase-title")
            price_el = item.select_one(".showcase-price-new") or item.select_one(".showcase-price")
            
            raw_price = price_el.get_text(strip=True) if price_el else ""
            numeric_price = self.clean_price(raw_price)
            
            extracted_items.append({
                # "category": page_data["category"],
                "title": title_el.get_text(strip=True) if title_el else "N/A",
                "price": numeric_price  
            })
        return extracted_items

class Storage:
    @staticmethod
    def data_dir_for_market():
        return os.path.join("InflationItems", "Datas", "ConstructionSuppliesMarkets", "FiltasYapi")

    @staticmethod
    def save(rows: list[dict]) -> str:
        path = Storage.data_dir_for_market()
        os.makedirs(path, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"FiltaşYapı_{today}.csv"
        out_path = os.path.join(path, filename)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["title", "price"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            
            w.writeheader()
            w.writerows(rows)

        print(f"saved {len(rows)} products in {out_path}")
        return out_path


class Scraper:
    def __init__(self):
        self.scanner = CategoryScanner(BASE_URL)
        self.collector = LinkCollector()
        self.extractor = DataExtractor()

    async def run(self):
        connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS, ssl=False)
        async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
            categories = await self.scanner.get_categories(session)

            categories = [c for c in categories if any(x in c['url'] for x in ['kategori', 'urun', 'filter'])]
            
            tasks = [self.collector.collect_pages(session, cat) for cat in categories]
            results = await asyncio.gather(*tasks)

            all_data = []
            for pages in results:
                for page in pages:
                    all_data.extend(self.extractor.extract(page))

            Storage.save(all_data)

if __name__ == "__main__":
    asyncio.run(Scraper().run())