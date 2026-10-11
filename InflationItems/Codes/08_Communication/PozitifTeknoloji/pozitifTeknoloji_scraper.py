"""
Pozitif Teknoloji (pt.com.tr) scraper.

pt.com.tr runs WooCommerce, whose public Store API
(``/wp-json/wc/store/v1/products``) returns the whole catalogue with prices,
stock status, SKU and categories — ~1240 products in 13 requests
(checked 2026-09-28; the old category-page crawler with a hand-written
category list found ~510, and product-sitemap.xml lists ~1150).

Every product is kept; ``in_stock`` and ``is_outlet`` (refurbished/outlet
categories) are columns so the analysis can filter them instead of the
scraper silently dropping them.

Output: InflationItems/Datas/08_Communication/PozitifTeknoloji/pozitifTeknoloji_YYYY-MM-DD.csv
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime

import requests

BASE_URL = "https://www.pt.com.tr"
STORE_API = f"{BASE_URL}/wp-json/wc/store/v1/products"
PER_PAGE = 100
MAX_PAGES = 100  # safety cap (~13 pages today)
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
PAGE_DELAY = 1.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}

FIELDS = ["name", "category", "price", "regular_price", "sku", "product_id",
          "in_stock", "is_outlet", "categories", "url"]

# Klasör yolu (önceki scraper'larla aynı mantık)
current_script_path = os.path.abspath(__file__)
base_project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))
data_dir = os.path.join(base_project_dir, "Datas", "08_Communication", "PozitifTeknoloji")
OUTPUT_FILE = os.path.join(data_dir, f"pozitifTeknoloji_{datetime.now().strftime('%Y-%m-%d')}.csv")

log = logging.getLogger("pozitif")


def fetch_page(session, page):
    """Returns (products, total_pages) or (None, None) after all retries fail."""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = session.get(STORE_API, params={"per_page": PER_PAGE, "page": page}, timeout=REQUEST_TIMEOUT)
            if r.status_code == 400 and page > 1:
                return [], None  # past the last page
            r.raise_for_status()
            return r.json(), int(r.headers.get("X-WP-TotalPages") or 0) or None
        except (requests.RequestException, ValueError) as e:
            log.warning("page %d attempt %d/%d failed: %s", page, attempt, RETRY_COUNT, e)
            time.sleep(3 * attempt)
    return None, None


def money(prices, key):
    raw = (prices or {}).get(key)
    if raw in (None, ""):
        return None
    unit = int((prices or {}).get("currency_minor_unit") or 0)
    return round(int(raw) / (10 ** unit), 2)


def to_row(p):
    cats = p.get("categories") or []
    names = [c.get("name", "") for c in cats]
    return {
        "name": (p.get("name") or "").strip(),
        # deepest category is listed last by WooCommerce (e.g. Mac > MacBook Air)
        "category": names[-1] if names else "",
        "price": money(p.get("prices"), "price"),
        "regular_price": money(p.get("prices"), "regular_price"),
        "sku": p.get("sku") or "",
        "product_id": p.get("id"),
        "in_stock": bool(p.get("is_in_stock")),
        "is_outlet": any("outlet" in (c.get("slug") or "") for c in cats),
        "categories": " > ".join(names),
        "url": p.get("permalink") or "",
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    session = requests.Session()
    session.headers.update(HEADERS)

    rows, seen = [], set()
    total_pages = None
    page = 1
    while page <= min(total_pages or MAX_PAGES, MAX_PAGES):
        products, tp = fetch_page(session, page)
        if products is None:
            log.error("page %d failed after retries; stopping", page)
            break
        total_pages = total_pages or tp
        if not products:
            break
        for p in products:
            row = to_row(p)
            if row["product_id"] in seen or not row["name"] or row["price"] is None:
                continue
            seen.add(row["product_id"])
            rows.append(row)
        log.info("page %d/%s: %d products (total %d)", page, total_pages or "?", len(products), len(rows))
        page += 1
        time.sleep(PAGE_DELAY)

    if not rows:
        log.error("No products collected.")
        sys.exit(1)

    os.makedirs(data_dir, exist_ok=True)
    rows.sort(key=lambda r: (r["category"], r["name"]))
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Saved %d products (%d in stock, %d outlet) to %s", len(rows),
             sum(r["in_stock"] for r in rows), sum(r["is_outlet"] for r in rows), OUTPUT_FILE)


if __name__ == "__main__":
    main()
