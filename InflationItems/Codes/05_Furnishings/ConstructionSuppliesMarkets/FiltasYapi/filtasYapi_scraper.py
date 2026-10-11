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
    def __init__(self):
        self.failed = []

    async def fetch(self, session, url, attempts=3):
        # A single failed request used to end the category silently, so a
        # whole category could be missing from the day's file.
        for attempt in range(attempts):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.text()
                    print(f"status {response.status} on {url}")
            except Exception as e:
                print(f"error on page {url}: {e}")
            await asyncio.sleep(2 * (attempt + 1))
        return None

    async def collect_pages(self, session, category):
        page = 1
        all_category_pages = []

        while True:
            # The site pages with ?tp=; it ignores ?sayfa= and keeps serving page 1.
            url = f"{category['url']}?tp={page}"
            try:
                html = await self.fetch(session, url)
                if html is None:
                    self.failed.append(f"{category['name']} (page {page})")
                    break

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
                print(f"[{category['name']}] {page} pages scraped")
                next_btn = soup.select_one(".paginate-right.paginate-active")
                if not next_btn:
                    break

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
                "product_name": title_el.get_text(strip=True) if title_el else "N/A",
                "price": numeric_price  
            })
        return extracted_items

class Storage:
    @staticmethod
    def data_dir_for_market():
        # The data folder mirrors this code folder (InflationItems/Codes/... ->
        # InflationItems/Datas/...), so the path holds in any category layout
        # and does not depend on the working directory.
        parts = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
        root = parts.index("InflationItems")
        return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])

    @staticmethod
    def save(rows: list[dict]) -> str:
        path = Storage.data_dir_for_market()
        os.makedirs(path, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"FiltaşYapı_{today}.csv"
        out_path = os.path.join(path, filename)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["product_name", "price"]
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

            if self.collector.failed:
                print("incomplete, CSV not written; failed: " + ", ".join(self.collector.failed))
                raise SystemExit(1)

            all_data = []
            for pages in results:
                for page in pages:
                    all_data.extend(self.extractor.extract(page))

            Storage.save(all_data)

if __name__ == "__main__":
    asyncio.run(Scraper().run())