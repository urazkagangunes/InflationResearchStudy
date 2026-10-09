import csv
import json
import math
import random
import re
import sys
import time
import urllib.robotparser
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.mediamarkt.com.tr"
# Pages of one category disagree on its count (dryers: 79 or 80) and some
# products show on two pages and others on none; the sort parameter that
# could fix the order is disallowed by robots.txt. A category may fall short
# by a few products, the store as a whole may not.
MIN_COVERAGE = 0.98
MIN_CATEGORY_COVERAGE = 0.90
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Listing categories and the TÜİK 2026 basket items (COICOP 05) they cover.
# Overlapping categories are deduplicated by product id.
CATEGORIES = [
    ("buzdolabi", 465709),            # 531101 refrigerator
    ("derin-dondurucular", 678524),   # 531103 deep freezer
    ("bulasik-makineleri", 712509),   # 531106 dishwasher
    ("camasir-makineleri", 809009),   # 531201 washing machine
    ("kurutma-makineleri", 809010),   # 531202 dryer
    ("firin", 678525),                # 531108 ovens and cookers
    ("ankastre-firin", 465726),       # 531108
    ("ocak", 678526),                 # 531108
    ("ankastre-ocaklar", 465727),     # 531108
    ("klimalar", 465752),             # 531301 air conditioner
    ("isiticilar", 806516),           # 531303 heater
    ("kombiler", 465754),             # 531306 combi boiler
    ("piller-ve-sarj-cihazlari", 811062),  # 552201 battery
]

# The battery category also lists chargers and camera battery packs, which are
# not the basket item; the site's own type filter is behind a query that
# robots.txt disallows.
NOT_BATTERY_RE = re.compile(
    r"şarj (cihaz|aleti|ünitesi)|battery pack|fotoğraf makinesi batarya", re.IGNORECASE)

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / ".git").exists()), Path(__file__).resolve().parents[5])
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "MediaMarkt"

STATE_RE = re.compile(r"window.__PRELOADED_STATE__ = (\{.*?\});?\s*</script>", re.S)


def make_session():
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "tr-TR,tr;q=0.9",
    })
    return session


def read_robots(session):
    robots = urllib.robotparser.RobotFileParser()
    response = session.get(f"{BASE_URL}/robots.txt", timeout=30)
    response.raise_for_status()
    robots.parse(response.text.splitlines())
    return robots


def category_url(slug, category_id):
    return f"{BASE_URL}/tr/category/{slug}-{category_id}.html"


def fetch_state(session, url, page, delay):
    time.sleep(delay + random.uniform(1, 3))
    response = session.get(url, params={"page": page} if page > 1 else None, timeout=60)
    response.raise_for_status()
    match = STATE_RE.search(response.text)
    if not match:
        raise ValueError(f"no page state on {url} page {page}")
    # The state is a JS literal; "undefined" is its only non-JSON token.
    return json.loads(re.sub(r":undefined([,}\]])", r":null\1", match.group(1)))


def parse_page(state):
    cache = state["apolloState"]
    root = cache["ROOT_QUERY"]
    category = next(v for k, v in root.items() if k.startswith("categoryV4"))
    names = {v["id"]: v["productName"] for v in cache.values()
             if isinstance(v, dict) and "productName" in v and "id" in v}
    products = []
    for key, feature in cache.items():
        if not key.startswith("CofrPriceFeature:"):
            continue
        price = (feature.get("price") or {}).get("amount")
        products.append({
            "id": feature["id"],
            "product_name": " ".join((names.get(feature["id"]) or "").split()),
            "price": Decimal(str(price)) if price else None,
            # Third-party sellers set their own prices; only MediaMarkt's own
            # offers make a single retailer's price series.
            "marketplace": bool(feature.get("isProductOfTypeMarketplace")),
            "bundle": bool(feature.get("isProductOfTypeBundle")),
        })
    return category["totalProducts"], products


def fetch_pages(session, url, delay, products):
    total, batch = parse_page(fetch_state(session, url, 1, delay))
    page_size = len(batch) or 1
    for page in range(1, math.ceil(total / page_size) + 1):
        if page > 1:
            _, batch = parse_page(fetch_state(session, url, page, delay))
        if not batch:
            break
        for item in batch:
            products.setdefault(item["id"], item)
    return total


def fetch_category(session, slug, category_id, delay, passes=2):
    # A short category is paged once more and the passes are merged.
    url = category_url(slug, category_id)
    products = {}
    for _ in range(passes):
        total = fetch_pages(session, url, delay, products)
        if len(products) >= total:
            break
    return total, list(products.values())


def get_csv_path():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return OUT_DIR / f"mediamarkt_{date}.csv"


def write_csv(rows, csv_path):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_name", "price"])
        writer.writerows(rows)


def main():
    sys.stdout.reconfigure(errors="replace")
    started = time.time()
    session = make_session()

    try:
        robots = read_robots(session)
    except (requests.RequestException, ValueError) as e:
        print(f"robots.txt could not be read: {e}; CSV not written.")
        sys.exit(1)
    first_url = category_url(*CATEGORIES[0])
    if not robots.can_fetch(USER_AGENT, f"{first_url}?page=2"):
        print("robots.txt disallows the category pages; CSV not written.")
        sys.exit(1)
    delay = robots.crawl_delay(USER_AGENT) or 0
    print(f"robots.txt Crawl-delay: {delay or 'none'}")

    products, short = {}, []
    found_sum = total_sum = 0
    for slug, category_id in CATEGORIES:
        try:
            total, items = fetch_category(session, slug, category_id, delay)
        except (requests.RequestException, ValueError, KeyError, StopIteration) as e:
            print(f"{slug}: failed after retries: {e!r}; CSV not written.")
            sys.exit(1)
        unique = {item["id"]: item for item in items}
        own = sum(1 for item in unique.values() if not item["marketplace"])
        print(f"  {slug}: {len(unique)}/{total}, MediaMarkt's own {own}")
        if total and len(unique) / total < MIN_CATEGORY_COVERAGE:
            short.append(slug)
        found_sum += min(len(unique), total)
        total_sum += total
        for product_id, item in unique.items():
            products.setdefault(product_id, item)
    coverage = found_sum / total_sum if total_sum else 0

    own = [p for p in products.values() if not p["marketplace"] and not p["bundle"]
           and not NOT_BATTERY_RE.search(p["product_name"])]
    rows = [(p["product_name"], f"{p['price']:.2f}")
            for p in own if p["price"] and p["product_name"]]
    print(f"Products: {len(products)}, MediaMarkt's own: {len(own)}, "
          f"written: {len(rows)}, coverage: {coverage:.1%}, "
          f"short categories: {short or 'none'}, "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial listing must not produce one.
    if short or coverage < MIN_COVERAGE or not rows:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} products -> {csv_path}")


if __name__ == "__main__":
    main()
