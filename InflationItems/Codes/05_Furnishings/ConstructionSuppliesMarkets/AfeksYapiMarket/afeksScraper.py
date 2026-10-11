"""
AfeksYapiMarket daily price scraper.

The category pages are served as plain HTML (Ticimax), so a requests session
is enough; the earlier Camoufox browser is not needed. Each category is paged
with ?sayfa=N until a page brings no new product (past the last page the site
serves the last page again).

Output: InflationItems/Datas/05_Furnishings/ConstructionSuppliesMarkets/
        AfeksYapiMarket/afeks_YYYY-MM-DD.csv  (product_name, price, category)

Usage:
    python afeksScraper.py
"""

import csv
import os
import random
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.afeksyapimarket.com"
CATEGORIES = [
    "/Beyaz-Esya", "/Mutfak", "/Banyo", "/Mobilya", "/Bahce", "/Hirdavat", "/Boya",
    "/Elektrikli-El-Aleti", "/Aydinlatma-ve-Elektrik", "/Dekorasyon-ve-Ev-Gereci",
    "/Isitma-ve-Sogutma", "/Seramik-ve-Insaat", "/Super-Market", "/Oto",
    "/Spor-ve-Outdoor", "/Parke-ve-Ahsap", "/Evcil-Hayvan", "/Kirtasiye",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}
DELAY_RANGE = (1.0, 2.0)
MAX_PAGES = 400
ATTEMPTS = 3

# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_parts = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
_root = _parts.index("InflationItems")
DATA_DIR = os.sep.join(_parts[:_root + 1] + ["Datas"] + _parts[_root + 2:])


def fetch(session, url):
    for attempt in range(ATTEMPTS):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 200:
                return r.text
            print(f"  status {r.status_code}: {url}")
        except requests.RequestException as e:
            print(f"  error: {url}: {e}")
        time.sleep(5 * (attempt + 1))
    return None


def parse_price(text):
    text = text.replace("₺", "").replace("TL", "").strip()
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_page(html):
    soup = BeautifulSoup(html, "lxml")
    products = []
    for card in soup.select("div.productDetail.videoAutoPlay"):
        link = card.select_one("a")
        price_el = card.select_one("span.discountPriceSpan")
        if not link or not price_el:
            continue
        name = (link.get("title") or link.get_text(strip=True)).strip()
        price = parse_price(price_el.get_text(strip=True))
        if name and price:
            products.append((name, price))
    return products


def scrape_category(session, category):
    seen = {}
    for page in range(1, MAX_PAGES + 1):
        html = fetch(session, f"{BASE_URL}{category}?sayfa={page}")
        if html is None:
            return None
        products = parse_page(html)
        new = [p for p in products if p not in seen]
        if not new:
            break
        for p in new:
            seen[p] = True
        print(f"[{category}] page {page}: +{len(new)} (total {len(seen)})")
        time.sleep(random.uniform(*DELAY_RANGE))
    else:
        # Hitting the page cap means the stop condition never fired.
        print(f"[{category}] reached {MAX_PAGES} pages without an end")
        return None
    return list(seen)


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    rows, failed = [], []
    for category in CATEGORIES:
        products = scrape_category(session, category)
        if not products:
            failed.append(category)
            continue
        rows.extend((name, price, category.strip("/")) for name, price in products)

    # A partial day must not look like a complete one.
    if failed:
        print(f"Incomplete, CSV not written; failed: {', '.join(failed)}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"afeks_{datetime.now():%Y-%m-%d}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["product_name", "price", "category"])
        writer.writerows(rows)
    print(f"Saved {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()
