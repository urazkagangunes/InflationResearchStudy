"""
Huawei Türkiye technology scraper (requests only, no browser).

Coverage (checked 2026-09-28): the full e-commerce catalogue comes from
``/.rest/service/ecommerce/v1/products/tr`` (~290 product ids, most of them
discontinued). Prices come in batches from the endpoint the site itself calls
(``itrinity-de.c.huawei.com/convert/queryMinPriceAndInv``); only ids with a
price there are currently sold (~120).

Names: the category pages (phones, laptops, ...) embed each shelf product as
JSON (``marketingName`` + ``ecProductId``). Accessories and a few others have a
price but appear on no listing page and their buy page is empty; for those the
name is derived from the product URL slug and ``listed_on_site`` is False, so
they can be filtered out in the analysis if only visibly listed products are
wanted. ``offer`` items (extended warranty, test entries) are skipped.

Price = "Başlangıç" (minimum unit price across colours/variants), the same
value the site shows.

Output: InflationItems/Datas/08_Communication/Huawei/huawei_YYYY-MM-DD.csv
"""

import csv
import html
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://consumer.huawei.com"
CATALOG_API = f"{BASE}/.rest/service/ecommerce/v1/products/tr"
PRICE_API = "https://itrinity-de.c.huawei.com/convert/queryMinPriceAndInv"
LISTING_PAGES = {
    "Telefon": f"{BASE}/tr/phones/",
    "PC": f"{BASE}/tr/laptops/",
    "Tablet": f"{BASE}/tr/tablets/",
    "Akıllı Saat": f"{BASE}/tr/wearables/",
    "Ses": f"{BASE}/tr/audio/",
    "Router": f"{BASE}/tr/routers/",
}
# catalogue URL section -> category label (sections not listed keep their own name)
SECTION_LABELS = {
    "phones": "Telefon", "laptops": "PC", "desktops": "PC", "monitors": "Monitör",
    "tablets": "Tablet", "wearables": "Akıllı Saat", "headphones": "Ses", "speakers": "Ses",
    "audio": "Ses", "routers": "Router", "accessories": "Aksesuar",
}
SKIP_SECTIONS = {"offer"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": f"{BASE}/tr/",
}
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
PRICE_BATCH = 20
FIELDS = ["Product ID", "Product Name", "Price", "Category", "listed_on_site", "Product URL"]

# "marketingName":"HUAWEI nova 13 Pro","productId":"SPCG...",...,"ecProductId":"18090..."
PRODUCT_RE = re.compile(r'"marketingName":"([^"]+)"[^{}]*?"ecProductId":"(\d+)"')

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "08_Communication" / "Huawei"

log = logging.getLogger("huawei")


def get(session, url, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            log.warning("%s attempt %d/%d failed: %s", url, attempt, MAX_RETRIES, e)
            time.sleep(3 * attempt)
    return None


def listed_names(session):
    """Product id -> (name, category) for everything shown on the listing pages."""
    names = {}
    for category, url in LISTING_PAGES.items():
        r = get(session, url)
        if r is None:
            log.error("[%s] listing page could not be fetched", category)
            continue
        found = PRODUCT_RE.findall(html.unescape(r.text))
        for name, pid in found:
            names.setdefault(pid, (name.strip(), category))
        log.info("[%s] %d products on listing page", category, len(set(p for _, p in found)))
        time.sleep(1)
    return names


def fetch_prices(session, ids):
    prices = {}
    for i in range(0, len(ids), PRICE_BATCH):
        params = [("productIds", pid) for pid in ids[i:i + PRICE_BATCH]] + [("siteCode", "TR"), ("loginFrom", "1")]
        r = get(session, PRICE_API, params=params)
        if r is None:
            continue
        try:
            rows = (r.json().get("data") or {}).get("minPriceAndInvList") or []
        except ValueError:
            log.warning("price API returned non-JSON")
            continue
        for row in rows:
            if row.get("minUnitPrice") is not None:
                prices[str(row.get("productId"))] = float(row["minUnitPrice"])
        time.sleep(0.5)
    return prices


def slug_name(pdp_link):
    slug = pdp_link.rstrip("/").removesuffix(".html").rsplit("/", 1)[-1]
    return "HUAWEI " + slug.replace("-", " ")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    out_file = OUT_DIR / f"huawei_{datetime.now():%Y-%m-%d}.csv"

    session = requests.Session()
    session.headers.update(HEADERS)

    names = listed_names(session)
    r = get(session, CATALOG_API)
    catalog = {}
    if r is not None:
        try:
            catalog = r.json()
        except ValueError:
            log.error("catalogue API returned non-JSON")
    log.info("Catalogue: %d products, listing pages: %d", len(catalog), len(names))

    ids = list(dict.fromkeys(list(catalog) + list(names)))
    prices = fetch_prices(session, ids)
    log.info("Priced (currently sold): %d", len(prices))

    rows = []
    for pid in ids:
        if pid not in prices:
            continue
        link = (catalog.get(pid) or {}).get("pdpLink") or ""
        section = link.split("/tr/")[-1].split("/")[0] if "/tr/" in link else ""
        if section in SKIP_SECTIONS:
            continue
        if pid in names:
            name, category = names[pid]
            listed = True
        elif link:
            name, category, listed = slug_name(link), SECTION_LABELS.get(section, section), False
        else:
            continue  # priced id with neither a name nor a catalogue entry
        url = BASE + link.replace("/content/huawei-cbg-site", "").replace(".html", "/") if link else ""
        rows.append({"Product ID": pid, "Product Name": name, "Price": prices[pid], "Category": category,
                     "listed_on_site": listed, "Product URL": url})

    if not rows:
        log.error("No data collected.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Saved %d products (%d listed on site) to %s",
             len(rows), sum(r["listed_on_site"] for r in rows), out_file)


if __name__ == "__main__":
    main()
