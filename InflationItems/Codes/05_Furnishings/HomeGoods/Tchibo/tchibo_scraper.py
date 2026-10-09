import csv
import math
import random
import re
import sys
import time
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.tchibo.com.tr"
# JSON endpoint behind the category page's "Daha fazla yükle" button.
API_URL = f"{BASE_URL}/service/categoryfrontend/api/categories/products"
# Listing of the "Ev, Yaşam & Mobilya" section (/categories/ev-yasam), the
# scope of the spring 2026 files. Some subcategory pages add products that
# this listing and its count leave out; those are not collected.
CATEGORY_PATH = "/ev-yasam"
# The listing order shifts between requests (24-card pages dropped a product
# on 2026-09-29); one large page returns the whole section at once.
PAGE_SIZE = 500
MIN_COVERAGE = 0.98
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_PARTS = Path(__file__).resolve().parent.parts
_ROOT = _PARTS.index("InflationItems")
OUT_DIR = Path(*_PARTS[:_ROOT + 1], "Datas", *_PARTS[_ROOT + 2:])

# Groceries such as coffee show a per-weight unit price ("TL/kg"); home
# goods show none or a per-piece one ("TL/adet").
FOOD_UNIT_RE = re.compile(r"/\s*\d*\s*(kg|g|gr)$", re.IGNORECASE)
NON_GOODS_RE = re.compile(r"hediye (kartı|çeki)|gift ?card", re.IGNORECASE)


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
        "Accept": "application/json",
        "Accept-Language": "tr-TR,tr;q=0.9",
    })
    return session


def read_robots(session):
    robots = urllib.robotparser.RobotFileParser()
    response = session.get(f"{BASE_URL}/robots.txt", timeout=30)
    response.raise_for_status()
    robots.parse(response.text.splitlines())
    return robots


def fetch_page(session, page, delay):
    time.sleep(delay + random.uniform(1, 3))
    params = {"path": CATEGORY_PATH, "site": "TR", "page": page,
              "pageSize": PAGE_SIZE}
    response = session.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def exclusion_reason(product):
    if NON_GOODS_RE.search(product["title"]):
        return "non-goods"
    if FOOD_UNIT_RE.search(product["price"].get("baseLabel") or ""):
        return "food"
    return None


def get_csv_path():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return OUT_DIR / f"tchibo_ev_yasam_{date}.csv"


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
    if not robots.can_fetch(USER_AGENT, API_URL):
        print("robots.txt disallows the product API; CSV not written.")
        sys.exit(1)
    delay = robots.crawl_delay(USER_AGENT) or 0
    print(f"robots.txt Crawl-delay: {delay or 'none'}")

    # Each listing card is one article: size or colour variants of a product
    # share the product id but have their own name, price and article_id.
    products = {}
    total, pages, page = 0, 1, 1
    while page <= pages:
        try:
            data = fetch_page(session, page, delay)
            items = data["items"]
            total = data["metadata"]["numFound"]
            page_size = data["metadata"]["pageSize"]
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Page {page} failed after retries: {e!r}; CSV not written.")
            sys.exit(1)
        pages = math.ceil(total / page_size) if page_size else 0
        if not items:
            print(f"Page {page}/{pages} returned no products")
        for item in items:
            query = parse_qs(urlparse(item["productViewUrl"]).query)
            article_id = query.get("article_id", [str(item["id"])])[0]
            products.setdefault(article_id, item)
        print(f"Page {page}/{pages}: {len(items)} items, "
              f"unique {len(products)}/{total}")
        page += 1

    rows, no_price = [], []
    excluded = {"food": [], "non-goods": []}
    for item in products.values():
        name = " ".join(item["title"].split())
        reason = exclusion_reason(item)
        price = item["price"]
        if reason:
            excluded[reason].append(name)
        elif price.get("currencyCode") != "TRY" or not price.get("current"):
            no_price.append(name)
        else:
            # "current" is in kuruş and already the reduced price on sale.
            rows.append([name, price["current"] / 100])

    for reason, names in excluded.items():
        print(f"Excluded as {reason}: {len(names)} {names}")
    print(f"Without a valid price: {len(no_price)} {no_price}")

    covered = len(rows) + sum(len(names) for names in excluded.values())
    coverage = covered / total if total else 0
    print(f"Coverage: {covered}/{total} ({coverage:.1%}), "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial catalogue must
    # not produce one.
    if coverage < MIN_COVERAGE:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} products -> {csv_path}")


if __name__ == "__main__":
    main()
