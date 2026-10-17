"""
Yapimaks daily price scraper.

An empty search (/arama?q=) lists every product, 48 per page, as plain HTML;
past the last page the site serves the last page again. That is about 175
requests a day instead of one per product (8300+), which the site's rate limit
(429 with Retry-After) would not allow. The product sitemap gives the expected
count. Names are taken from the card image's alt text, the upper-case form the
earlier daily files used. The Camoufox scrapers (camoufoxscraper.py,
chromiumscraper.py) opened every product page in a browser.

Output: InflationItems/Datas/05_Furnishings/ConstructionSuppliesMarkets/
        yapimaks/YYYY-MM-DD.csv

Usage:
    python yapimaks_scraper.py
"""

import csv
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "coicop").is_dir())))
import coicop  # noqa: E402

BASE_URL = "https://yapimaks.com"
SEARCH_URL = f"{BASE_URL}/arama"
SITEMAP_URL = f"{BASE_URL}/sitemap/products1.xml"
PRODUCT_HREF_RE = re.compile(r"-p(\d+)$")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}
DELAY_RANGE = (1.5, 2.5)
ATTEMPTS = 4
MAX_PAGES = 400
MIN_COVERAGE = 0.98

# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_parts = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
_root = _parts.index("InflationItems")
DATA_DIR = os.sep.join(_parts[:_root + 1] + ["Datas"] + _parts[_root + 2:])


def fetch(session, url, params=None):
    for attempt in range(ATTEMPTS):
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.text
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "60")) + 5
                print(f"  429, waiting {wait}s")
                time.sleep(wait)
                continue
            print(f"  status {r.status_code}: {url} {params or ''}")
        except requests.RequestException as e:
            print(f"  error: {url} {params or ''}: {e}")
        time.sleep(10 * (attempt + 1))
    return None


def parse_price(text):
    text = text.replace("TL", "").replace("₺", "").strip()
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_page(html):
    soup = BeautifulSoup(html, "lxml")
    products = []
    for card in soup.select("div.card"):
        link = card.select_one("a[href]")
        if not link or not PRODUCT_HREF_RE.search(link["href"]):
            continue
        img = card.select_one("img[alt]")
        # A discounted card may carry more than one price; the last one is the
        # price the customer pays.
        prices = card.select('[class*="price"]')
        if not img or not prices:
            continue
        price = parse_price(prices[-1].get_text(" ", strip=True))
        name = img.get("alt", "").strip()
        if name and price:
            products.append({
                "product_name": name,
                "price": price,
                "product_id": PRODUCT_HREF_RE.search(link["href"]).group(1),
                "url": BASE_URL + link["href"],
            })
    return products


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    sitemap = fetch(session, SITEMAP_URL)
    if not sitemap:
        print("Sitemap could not be read.")
        sys.exit(1)
    expected = len({u for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap)
                    if PRODUCT_HREF_RE.search(u)})

    found = {}
    for page in range(1, MAX_PAGES + 1):
        time.sleep(random.uniform(*DELAY_RANGE))
        html = fetch(session, SEARCH_URL, {"q": "", "page": page})
        if html is None:
            print(f"Page {page} failed, CSV not written.")
            sys.exit(1)
        new = [p for p in parse_page(html) if p["product_id"] not in found]
        if not new:
            break
        for p in new:
            found[p["product_id"]] = p
        print(f"page {page}: +{len(new)} (total {len(found)})")
    else:
        print(f"Reached {MAX_PAGES} pages without an end, CSV not written.")
        sys.exit(1)

    coverage = len(found) / expected if expected else 0
    print(f"{len(found)} products, sitemap lists {expected} ({coverage:.1%})")
    if coverage < MIN_COVERAGE:
        print("Coverage below minimum, CSV not written.")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{datetime.now():%Y-%m-%d}.csv")
    rows = sorted(found.values(), key=lambda r: int(r["product_id"]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(coicop.FIELDS)
        # The search listing carries no category; the code comes from the name.
        writer.writerows(coicop.row(r["product_name"], r["price"], "", "yapimaks") for r in rows)
    print(f"Saved {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()
