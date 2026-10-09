import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://jysk.com.tr"
# Search API behind the site's filtered listings (outlet, campaigns); it
# returns the whole catalogue with totals, so no browser is needed.
SEARCH_URL = f"{BASE_URL}/api/search"
PAGE_SIZE = 96  # API maximum
MIN_COVERAGE = 0.98
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "Datas", "JYSK")
FIELDS = ["product_name", "price"]

PRICE_RE = re.compile(r"(\d[\d.]*),(\d{2})")


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


def search(session, filters, page=1, limit=PAGE_SIZE):
    params = {
        "allow_empty_query": "true",
        "type": "product",
        "query": "",
        "filters": json.dumps(filters, ensure_ascii=False),
        # The API answers 503 when no facet is requested.
        "facets": "category_name",
        "page": page,
        "limit": limit,
        # A fixed sort keeps page boundaries stable while paging.
        "sort": "alphabetical",
    }
    time.sleep(random.uniform(1, 3))
    response = session.get(SEARCH_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_all_pages(session, filters):
    products, page = [], 1
    while True:
        data = search(session, filters, page)
        products.extend(data["data"])
        if not data["data"] or page >= data["totalPages"]:
            return products
        page += 1


def parse_price(text):
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    return Decimal(match.group(1).replace(".", "") + "." + match.group(2))


def format_price(value):
    return f"{value:.2f}".replace(".", ",") if value is not None else ""


def to_row(product, category):
    price = product["price"]
    # Multi-buy offers ("2 adeti ...") leave "value" empty; the customer
    # buying one unit pays the single piece price.
    current = parse_price(price.get("value")) or parse_price(
        price.get("singlePiecePrice"))
    before = parse_price(price.get("beforePrice"))
    list_price = before if product.get("showDiscount") and before else current

    title = " ".join(product["title"].split())
    series = " ".join((product.get("series") or "").split())
    return {
        # Series prefix keeps names identical to earlier files.
        "product_name": f"{series} {title}" if series else title,
        "price": format_price(current),
        "list_price": format_price(list_price),
        "product_id": product["wssId"],
        "url": BASE_URL + product["url"],
        "category": category,
        "online_sales": int(bool(product.get("onlineSales"))),
    }


def get_csv_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return os.path.join(OUT_DIR, f"jysk_prices_{date}.csv")


def write_csv(rows, csv_path):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    sys.stdout.reconfigure(errors="replace")
    started = time.time()
    session = make_session()

    overview = search(session, {}, limit=1)
    total = overview["totalCount"]
    categories = [
        (option["filter"], option["count"])
        for option in overview["facets"]["category_name"]["options"]
    ]
    print(f"Site total: {total} products in {len(categories)} categories")

    rows = {}
    short = []
    for name, expected in categories:
        products = fetch_all_pages(session, {"category_name": {"0": name}})
        for product in products:
            rows.setdefault(product["wssId"], to_row(product, name))
        unique = len({p["wssId"] for p in products})
        print(f"  {name}: {unique}/{expected}")
        if unique < expected:
            short.append(name)

    if len(rows) < total:
        print("Category totals do not cover the catalogue, paging unfiltered")
        for product in fetch_all_pages(session, {}):
            rows.setdefault(product["wssId"], to_row(product, ""))

    output = [row for row in rows.values() if row["price"]]
    coverage = len(output) / total if total else 0
    print(f"Coverage: {len(output)}/{total} ({coverage:.1%}), "
          f"short categories: {short or 'none'}, "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial catalogue must not produce one.
    if coverage < MIN_COVERAGE:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(output, csv_path)
    print(f"Written: {len(output)} products -> {csv_path}")


if __name__ == "__main__":
    main()
