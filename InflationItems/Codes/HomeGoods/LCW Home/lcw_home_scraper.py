import csv
import gzip
import http.client
import json
import random
import sys
import time
import urllib.error
import urllib.request

from datetime import date
from pathlib import Path


class LCWHomeScraper:
    START_URL = "https://www.lcw.com/marka/lcw-home-b-307"

    REPO_ROOT = Path(__file__).resolve().parents[4]
    OUTPUT_DIR = (
        REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "LCW Home"
    )
    OUTPUT_FILE = OUTPUT_DIR / f"lcw_home - {date.today().isoformat()}.csv"

    MODEL_MARKER = "var catalogModel = "

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept-Encoding": "gzip",
    }

    RETRY_STATUSES = {403, 429, 500, 502, 503, 504}
    MAX_ATTEMPTS = 5
    BACKOFF_SECONDS = 5
    MAX_MISSING_SHARE = 0.02

    def __init__(self):
        self.products = {}
        self.failed_pages = []
        self.total_count = None

    def build_page_url(self, page_no):
        if page_no == 1:
            return self.START_URL

        return f"{self.START_URL}?sayfa={page_no}"

    def fetch_html(self, url):
        # requests/urllib3 always offer ALPN "http/1.1" in the TLS handshake;
        # LCW's Akamai edge answers that with 403, the stdlib client passes.
        request = urllib.request.Request(url, headers=self.HEADERS)

        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()

            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)

        return body.decode("utf-8")

    def parse_catalog(self, html_text):
        start = html_text.find(self.MODEL_MARKER)

        if start == -1:
            return None

        start += len(self.MODEL_MARKER)
        model, _ = json.JSONDecoder().raw_decode(html_text, start)
        return model.get("CatalogList")

    def fetch_catalog(self, url):
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                catalog = self.parse_catalog(self.fetch_html(url))

                if catalog is not None:
                    return catalog

                print(f"catalogModel bulunamadı: {url}")

            except urllib.error.HTTPError as e:
                print(f"HTTP {e.code}: {url}")

                if e.code not in self.RETRY_STATUSES:
                    return None

            except (OSError, http.client.HTTPException, ValueError) as e:
                print(f"Sayfa okunamadı: {url} | {e}")

            if attempt < self.MAX_ATTEMPTS:
                delay = self.BACKOFF_SECONDS * 2 ** (attempt - 1)
                time.sleep(delay + random.uniform(0, 2))

        return None

    @staticmethod
    def paid_price(item):
        price = item.get("PriceValue") or 0

        # "Sepette İndirim" is applied automatically at checkout; the listing
        # card and the product page's schema.org offer price both show it.
        for badge in item.get("CampaignBadges") or []:
            basket_price = badge.get("DiscountedPrice") or 0

            if badge.get("ShowDiscountedPrice") and 0 < basket_price < price:
                price = basket_price

        return price

    @staticmethod
    def product_name(item):
        brand = item.get("Brand") or ""
        description = item.get("ProductDescription") or ""
        return " ".join(f"{brand} {description}".split())

    def add_products(self, items):
        new_count = 0

        for item in items:
            product_id = item.get("OptionId")
            name = self.product_name(item)
            price = self.paid_price(item)

            if not product_id or not name or price <= 0:
                continue

            if product_id in self.products:
                continue

            self.products[product_id] = (name, price)
            new_count += 1

        return new_count

    def collect(self):
        page_no = 1
        page_count = 1

        while page_no <= page_count:
            url = self.build_page_url(page_no)
            catalog = self.fetch_catalog(url)

            # An out-of-range "sayfa" silently returns page 1
            if catalog is None or catalog.get("PageIndex") != page_no:
                self.failed_pages.append(page_no)
                print(f"Sayfa {page_no}/{page_count} alınamadı: {url}")
            else:
                page_count = catalog.get("PageCount") or page_count
                self.total_count = catalog.get("ItemCount")
                new_count = self.add_products(catalog.get("Items") or [])

                print(
                    f"Sayfa {page_no}/{page_count} | "
                    f"yeni ürün: {new_count} | "
                    f"toplam: {len(self.products)}/{self.total_count}"
                )

            page_no += 1

            if page_no <= page_count:
                time.sleep(random.uniform(1, 3))

    def write_csv(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with open(self.OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["product_name", "price"])

            for name, price in self.products.values():
                writer.writerow([name, f"{price:.2f}"])

    def run(self):
        self.collect()

        if not self.products:
            print("Hiç ürün alınamadı, dosya yazılmadı.")
            return False

        total = self.total_count or 0
        missing = total - len(self.products)
        print(f"Alınan ürün: {len(self.products)} | sitedeki ürün sayısı: {self.total_count}")

        # The runner counts any CSV as success, so a partial catalogue must not produce one.
        if self.failed_pages or missing > self.MAX_MISSING_SHARE * total:
            print(
                f"EKSİK VERİ: alınamayan sayfalar {self.failed_pages}, "
                f"eksik ürün {missing}; dosya yazılmadı."
            )
            return False

        self.write_csv()

        print("\nBitti.")
        print(f"Dosya: {self.OUTPUT_FILE}")
        print(f"Toplam yazılan ürün: {len(self.products)}")
        return True


if __name__ == "__main__":
    scraper = LCWHomeScraper()
    sys.exit(0 if scraper.run() else 1)
