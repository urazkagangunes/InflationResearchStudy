import csv
import os
import re
import time
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.nalburcuk.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

REQUEST_DELAY   = 0.6  # seconds of sleep after each product request (per thread)
MAX_WORKERS     = 3    # parallel threads
REQUEST_TIMEOUT = 30   # seconds
RETRY_WAITS     = [10, 20, 40]  # seconds to wait on 429 before each retry

# XML sitemap namespace
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# ---------------------------------------------------------------------------
# Regex patterns — match both quoted and unquoted JS object keys
# ---------------------------------------------------------------------------
PAGEPARAMS_START_RE = re.compile(r'pageParams\s*=\s*\{product\s*:')

FULL_NAME_RE  = re.compile(r'fullName\s*:\s*"([^"]+)"')
SALE_PRICE_RE = re.compile(r'salePrice\s*:\s*([\d]+(?:\.\d+)?)')
REG_PRICE_RE  = re.compile(r'priceWithCurrency\s*:\s*([\d]+(?:\.\d+)?)')
SKU_RE        = re.compile(r'\bsku\s*:\s*"([^"]+)"')
CATEGORY_RE   = re.compile(r'categoryName\s*:\s*"([^"]+)"')
BRAND_RE      = re.compile(r'brandName\s*:\s*"([^"]+)"')

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def inflationitems_root() -> str:
    """
    This file lives at:
      [project_root]/InflationItems/Codes/ConstructionSuppliesMarkets/Nalburcuk/nalburcuk_scraper.py
    Four dirname() calls reach InflationItems/.
    """
    here = os.path.abspath(__file__)
    return os.path.dirname(   # Nalburcuk/
        os.path.dirname(       # ConstructionSuppliesMarkets/
            os.path.dirname(   # Codes/
                os.path.dirname(here)  # InflationItems/
            )
        )
    )

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(session: requests.Session, url: str) -> requests.Response:
    """GET with automatic retry on 429 (rate limit)."""
    for attempt, wait in enumerate(RETRY_WAITS + [None]):
        resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 429 and wait is not None:
            print(f"    [429] Rate limited, waiting {wait}s before retry ({attempt+1}/{len(RETRY_WAITS)}) ...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # raise after final attempt
    return resp

# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------

def _parse_locs(xml_text: str, filter_substr: Optional[str] = None) -> List[str]:
    """
    Extract all <loc> values from sitemap XML.
    Falls back to simple regex parsing if ElementTree fails (e.g. encoding issues).
    """
    locs: List[str] = []

    # Try ElementTree first
    try:
        root = ET.fromstring(xml_text)
        # Try with namespace
        for elem in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if elem.text:
                locs.append(elem.text.strip())
        # Try without namespace if nothing found
        if not locs:
            for elem in root.iter("loc"):
                if elem.text:
                    locs.append(elem.text.strip())
    except ET.ParseError:
        # Regex fallback
        locs = re.findall(r"<loc>\s*(https?://[^\s<]+)\s*</loc>", xml_text)

    if filter_substr:
        locs = [u for u in locs if filter_substr in u]
    return locs


def get_product_sitemap_urls(session: requests.Session) -> List[str]:
    """Fetch main sitemap.xml and return every product sub-sitemap URL."""
    resp = _get(session, SITEMAP_URL)
    locs = _parse_locs(resp.text, filter_substr="sitemap_product")
    return locs


def get_product_urls_from_sitemap(session: requests.Session, sitemap_url: str) -> List[str]:
    """Fetch one product sitemap and return all /urun/ product page URLs."""
    try:
        resp = _get(session, sitemap_url)
        return _parse_locs(resp.text, filter_substr="/urun/")
    except Exception as exc:
        print(f"  !! Sitemap fetch failed ({sitemap_url}): {exc}")
        return []

# ---------------------------------------------------------------------------
# Product page parsing
# ---------------------------------------------------------------------------

def parse_product_page(html: str) -> Optional[Dict]:
    """
    Locate the `pageParams = { ... }` block and extract product fields.
    Returns a dict or None if required fields are missing.
    """
    m = PAGEPARAMS_START_RE.search(html)
    if not m:
        return None

    # Work with the substring starting at `pageParams = {`
    # Use a generous slice (first 8 KB is enough for the product object)
    snippet = html[m.start(): m.start() + 8000]

    name_m  = FULL_NAME_RE.search(snippet)
    price_m = SALE_PRICE_RE.search(snippet)
    if not price_m:
        price_m = REG_PRICE_RE.search(snippet)

    if not name_m or not price_m:
        return None

    sku_m  = SKU_RE.search(snippet)
    cat_m  = CATEGORY_RE.search(snippet)
    brand_m = BRAND_RE.search(snippet)

    # Format price as Turkish decimal string (e.g. "2646,90")
    raw_price = float(price_m.group(1))
    price_str = f"{raw_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "name":     name_m.group(1).strip(),
        "price":    price_str,
        "sku":      sku_m.group(1).strip()  if sku_m  else "",
        "category": cat_m.group(1).strip()  if cat_m  else "",
        "brand":    brand_m.group(1).strip() if brand_m else "",
    }


# Thread-local storage so each thread has its own session
_thread_local = threading.local()

def _get_thread_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update(HEADERS)
        _thread_local.session = s
    return _thread_local.session


def scrape_one_product(url: str) -> Optional[Dict]:
    """Fetch a single product page, parse it, sleep politely, return data or None."""
    session = _get_thread_session()
    try:
        resp = _get(session, url)
        data = parse_product_page(resp.text)
        time.sleep(REQUEST_DELAY)
        if data is not None:
            data["url"] = url
        return data
    except Exception as exc:
        print(f"  !! Product failed ({url}): {exc}")
        return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    setup_session = requests.Session()

    # ── Step 1: Discover product sitemaps ────────────────────────────────
    print("Fetching main sitemap ...")
    sitemap_urls = get_product_sitemap_urls(setup_session)
    print(f"  Found {len(sitemap_urls)} product sitemap(s).")

    # ── Step 2: Collect all product URLs ─────────────────────────────────
    print("Collecting product URLs from sitemaps ...")
    all_product_urls: List[str] = []
    for idx, smap_url in enumerate(sitemap_urls, 1):
        urls = get_product_urls_from_sitemap(setup_session, smap_url)
        all_product_urls.extend(urls)
        print(f"  [{idx:>2}/{len(sitemap_urls)}] {len(urls):>4} products  ({smap_url.split('/')[-1].split('?')[0]})")
        time.sleep(1.5)

    # Deduplicate while preserving order
    seen_urls: set = set()
    unique_urls: List[str] = []
    for u in all_product_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            unique_urls.append(u)

    print(f"\nTotal unique product URLs: {len(unique_urls)}")

    # ── Step 3: Scrape product pages (parallel) ───────────────────────────
    print(f"Scraping product pages with {MAX_WORKERS} workers ...\n")

    collected: List[Dict] = []
    failed_count = 0
    done_count = 0
    total = len(unique_urls)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(scrape_one_product, url): url for url in unique_urls}
        for future in as_completed(future_to_url):
            done_count += 1
            data = future.result()
            if data:
                collected.append(data)
            else:
                failed_count += 1

            if done_count % 100 == 0 or done_count == total:
                print(
                    f"  Progress: {done_count}/{total}  "
                    f"ok={len(collected)}  failed={failed_count}"
                )

    print(f"\nDone. Collected {len(collected)} products, {failed_count} failed.")

    # ── Step 4: Deduplicate by SKU (keep first occurrence) ───────────────
    seen_skus: set = set()
    final_rows: List[Dict] = []
    for row in collected:
        key = row.get("sku") or row.get("url", "")
        if key and key in seen_skus:
            continue
        seen_skus.add(key)
        final_rows.append(row)

    print(f"Unique products after SKU dedup: {len(final_rows)}")

    # ── Step 5: Write CSV ─────────────────────────────────────────────────
    out_dir = os.path.join(
        inflationitems_root(),
        "Datas", "ConstructionSuppliesMarkets", "Nalburcuk"
    )
    os.makedirs(out_dir, exist_ok=True)

    today    = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"nalburcuk_{today}.csv")

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SKU", "Product Name", "Category", "Price (TL)", "URL"])
        for row_id, row in enumerate(final_rows, 1):
            writer.writerow([
                row_id,
                row.get("sku", ""),
                row.get("name", ""),
                row.get("category", ""),
                row.get("price", ""),
                row.get("url", ""),
            ])

    print(f"\nSaved {len(final_rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
