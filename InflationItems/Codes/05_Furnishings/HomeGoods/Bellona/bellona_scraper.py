import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import csv
import os
import random
import re
import json
import sys

BASE_URL = "https://www.bellona.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# robots.txt asks for Crawl-delay 30; the team settled on one connection and
# ~5 s between requests so a full run stays well inside the runner's timeout.
CONCURRENT_CATEGORIES = 1
REQUEST_INTERVAL = (4.5, 5.5)
CATEGORY_ATTEMPTS = 2


class IncompleteCategory(Exception):
    pass


def product_id(item):
    ga4_data_str = item.get("data-prd-ga4-config")
    if ga4_data_str:
        try:
            slug = json.loads(ga4_data_str).get("slug")
            if slug:
                return slug
        except ValueError:
            pass
    link = item.select_one("a[href]")
    return link.get("href") if link else None


class CategoryScanner:
    def __init__(self, base_url):
        self.base_url = base_url

    async def get_categories(self, session, fetch):
        print("Fetching homepage for categories...")
        html = await fetch(session, self.base_url)
        if not html:
            raise IncompleteCategory("homepage could not be fetched")

        soup = BeautifulSoup(html, "html.parser")
        categories = {} 

        # All homepage links, not only the main menu: Online Ozel, Dugun Paketi
        # and some banners list products that no menu category contains.
        nav_items = soup.select('a[href]')

        valid_paths = ["/kategori/", "/koleksiyon/", "/urunler/"]

        for item in nav_items:
            href = item.get("href", "")
            if href and any(path in href for path in valid_paths):
                title_el = item.select_one('span, .product-category-list-title')
                name = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)
                
                url = urljoin(self.base_url, href)
                if url != self.base_url and (name or url not in categories):
                    categories[url] = {"name": name or url.rsplit("/", 1)[-1], "url": url}

        final_categories = list(categories.values())
        print(f"Total unique categories to parse: {len(final_categories)}")
        return final_categories

class LinkCollector:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(CONCURRENT_CATEGORIES)
        self.request_lock = asyncio.Lock()
        self.last_request = 0.0

    async def wait_turn(self):
        async with self.request_lock:
            loop = asyncio.get_running_loop()
            wait = self.last_request + random.uniform(*REQUEST_INTERVAL) - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_request = loop.time()

    async def fetch_with_retry(self, session, url, retries=3):
        for attempt in range(retries):
            await self.wait_turn()
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status == 200:
                        return await response.text()
                    # The homepage keeps links to retired categories; retrying cannot help.
                    if response.status == 404:
                        print(f"Status 404 for {url}; treated as removed.")
                        return ""
                    else:
                        print(f"Status {response.status} for {url}. Attempt {attempt + 1}/{retries}")
            except Exception as e:
                if attempt == retries - 1:
                    print(f"Error on {url}: {type(e).__name__} - {e}")
                    return None
            await asyncio.sleep(random.uniform(2.0, 4.0) * (attempt + 1))
        return None

    async def collect_pages(self, session, category):
        async with self.semaphore:
            for attempt in range(1, CATEGORY_ATTEMPTS + 1):
                try:
                    return await self.collect_category(session, category)
                except IncompleteCategory as e:
                    print(f"[{category['name']}] attempt {attempt}/{CATEGORY_ATTEMPTS} failed: {e}")
                    if attempt == CATEGORY_ATTEMPTS:
                        raise

    async def collect_category(self, session, category):
        """Pages a category until all 'Toplam N' products are collected, else raises."""
        page = 1
        total = None
        all_category_pages = []
        seen_ids = set()

        while True:
            separator = "&" if "?" in category["url"] else "?"
            # The site pages with ?tp=N; sayfa/page are ignored and return page 1.
            url = f"{category['url']}{separator}tp={page}"

            html = await self.fetch_with_retry(session, url)
            if html == "" and page == 1:
                print(f"[{category['name']}] WARNING: category page is 404, skipped")
                return []
            if not html:
                raise IncompleteCategory(f"could not fetch {url}")

            soup = BeautifulSoup(html, "html.parser")
            if page == 1:
                count_el = soup.select_one(".record-count")
                count_text = count_el.get_text(" ", strip=True) if count_el else ""
                match = re.search(r"Toplam\s+(\d+)", count_text)
                if not match:
                    raise IncompleteCategory(f"'Toplam N' not found on {url}")
                total = int(match.group(1))

            page_ids = {product_id(item) for item in soup.select(".showcase")} - {None}
            if not page_ids - seen_ids:
                break
            seen_ids.update(page_ids)

            all_category_pages.append({
                "category": category["name"],
                "url": url,
                "html": html
            })

            print(f"[{category['name']}] page parsed {page}")
            if len(seen_ids) >= total:
                break
            page += 1

        if len(seen_ids) < total:
            raise IncompleteCategory(f"collected {len(seen_ids)} of {total} products")
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
            ga4_data_str = item.get("data-prd-ga4-config")
            if ga4_data_str:
                try:
                    ga4_data = json.loads(ga4_data_str)
                    sku = ga4_data.get("sku", "")
                    title = ga4_data.get("name", "")
                    price = round(float(ga4_data.get("price", 0.0)), 2)
                    
                    if sku and title:
                        extracted_items.append({
                            "sku": sku,
                            "title": title,
                            "price": price
                        })
                        continue 
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            sku = item.get("data-set-id") or item.get("data-id", "")
            
            title_el = item.select_one(".showcase-title a")
            title = title_el.get_text(strip=True) if title_el else "N/A"
            
            price_el = item.select_one(".showcase-price-new")
            raw_price = price_el.get_text(strip=True) if price_el else ""
            numeric_price = self.clean_price(raw_price)
            
            extracted_items.append({
                "sku": sku,
                "title": title,
                "price": numeric_price  
            })
            
        return extracted_items

class Storage:
    @staticmethod
    def data_dir_for_market():
        # The data folder mirrors this code folder (InflationItems/Codes/... ->
        # InflationItems/Datas/...), so the path holds in any category layout.
        parts = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
        root = parts.index("InflationItems")
        return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])

    @staticmethod
    def save(rows: list[dict]) -> str:
        if not rows:
            print("No data for saving.")
            return ""

        path = Storage.data_dir_for_market()
        os.makedirs(path, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"Bellona_{today}.csv"
        out_path = os.path.join(path, filename)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["product_name", "price"])
            w.writerows([row["title"], row["price"]] for row in rows)

        print(f"Saved {len(rows)} unique items to {out_path}")
        return out_path

class Scraper:
    def __init__(self):
        self.scanner = CategoryScanner(BASE_URL)
        self.collector = LinkCollector()
        self.extractor = DataExtractor()

    async def run(self):
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
            categories = await self.scanner.get_categories(session, self.collector.fetch_with_retry)

            tasks = [self.collector.collect_pages(session, cat) for cat in categories]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            failed = [(cat["name"], r) for cat, r in zip(categories, results)
                      if isinstance(r, BaseException)]
            if failed:
                for name, error in failed:
                    print(f"Category failed: {name}: {type(error).__name__} - {error}")
                raise IncompleteCategory(f"{len(failed)} of {len(categories)} categories incomplete")

            all_data = []
            for pages in results:
                if pages:
                    for page in pages:
                        all_data.extend(self.extractor.extract(page))

            unique_items = {}
            for item in all_data:
                key = f"{item.get('sku', '')}_{item.get('title', '')}_{item.get('price', 0)}"
                if item.get("title") and item.get("title") != "N/A":
                    unique_items[key] = item

            final_list = list(unique_items.values())
            if not final_list:
                raise IncompleteCategory("no products collected")
            Storage.save(final_list)

if __name__ == "__main__":
    try:
        asyncio.run(Scraper().run())
    except Exception as e:
        print(f"Run failed, no CSV written: {type(e).__name__} - {e}")
        sys.exit(1)