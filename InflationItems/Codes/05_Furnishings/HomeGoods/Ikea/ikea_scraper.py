import csv
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# The category pages on www.ikea.com.tr fill their product grid from this API.
# www's robots.txt disallows only /_ws/ and /arama/ and sets no Crawl-delay;
# this host has no robots.txt.
API_URL = "https://frontendapi.ikea.com.tr/api/search/products"
STORE_CODE = "331"  # sent by the site for the online store
PAGE_SIZE = 40  # API maximum
# The API counts and pages at most 10000 hits, so the catalogue is read in
# disjoint price ranges below that cap. Range bounds are inclusive in the API,
# so each range [low, high) is sent as low..high-0.01.
RESULT_CAP = 10000
PRICE_BOUNDS = [0, 250, 500, 1000, 2000, 3500, 6000, 10000, 20000, 50000,
                10 ** 8]
MIN_COVERAGE = 0.98
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_PARTS = SCRIPT_DIR.split(os.sep)
_ROOT = _PARTS.index("InflationItems")
OUT_DIR = os.sep.join(_PARTS[:_ROOT + 1] + ["Datas"] + _PARTS[_ROOT + 2:])
FIELDS = ["product_name", "price"]

# Gift cards and services ("montaj hizmeti") are not goods; none were listed
# in September 2026. The listing marks food itself (isFood).
NON_GOODS_WORDS = ("hediye kartı", "hizmeti")


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
        "Origin": "https://www.ikea.com.tr",
        "Referer": "https://www.ikea.com.tr/",
        # Headers the site's own listing script sends.
        "X-Bone-Language": "tr",
        "X-Channel": "WebSite",
        "X-Version": "V2",
    })
    return session


def search(session, low, high, page):
    params = {
        "language": "tr",
        "storeCode": STORE_CODE,
        "priceFrom": low,
        "priceTo": f"{high - 0.01:.2f}",
        "page": page,
        "size": PAGE_SIZE,
        "sortby": "None",
        "includeFilters": "false",
        "includeColorVariants": "false",
    }
    time.sleep(random.uniform(1, 3))
    response = session.get(API_URL, params=params, timeout=60)
    # The API answers an empty result with 404.
    if response.status_code == 404:
        return {"total": 0, "products": []}
    response.raise_for_status()
    return response.json()


def fetch_range(session, low, high):
    data = search(session, low, high, 1)
    total = data["total"]
    if total >= RESULT_CAP:
        middle = (low + high) // 2
        first = fetch_range(session, low, middle)
        second = fetch_range(session, middle, high)
        return first[0] + second[0], first[1] + second[1]

    products, page = data["products"], 1
    while len(products) < total:
        page += 1
        batch = search(session, low, high, page)["products"]
        if not batch:
            break
        products += batch
    return products, total


def exclusion_reason(product):
    if product.get("isFood"):
        return "food"
    name = product_name(product).casefold()
    for word in NON_GOODS_WORDS:
        if word in name:
            return word
    if not product.get("price") or product["price"] <= 0:
        return "no price"
    return None


def product_name(product):
    # Same "SERIES type, size" form as the spring files.
    name = f"{product.get('title') or ''} {product.get('subTitle') or ''}"
    return " ".join(name.split())


def get_csv_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return os.path.join(OUT_DIR, f"ikea_{date}.csv")


def write_csv(rows, csv_path):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)


def main():
    sys.stdout.reconfigure(errors="replace")
    started = time.time()
    session = make_session()

    products, site_total = {}, 0
    try:
        for low, high in zip(PRICE_BOUNDS, PRICE_BOUNDS[1:]):
            items, total = fetch_range(session, low, high)
            site_total += total
            unique = {item["sprCode"]: item for item in items}
            if len(unique) < total:
                # The listing order can shift while paging; a second pass
                # picks up what the first one skipped.
                print(f"  {low}-{high} TL: {len(unique)}/{total}, paging again")
                more, _ = fetch_range(session, low, high)
                unique.update({item["sprCode"]: item for item in more
                               if item["sprCode"] not in unique})
            products.update(unique)
            print(f"  {low}-{high} TL: {len(unique)}/{total}")
    except requests.RequestException as exc:
        print(f"Request failed after retries: {exc}")
        print("CSV not written.")
        sys.exit(1)

    rows, excluded = [], Counter()
    for product in products.values():
        reason = exclusion_reason(product)
        if reason:
            excluded[reason] += 1
        else:
            rows.append((product_name(product), float(product["price"])))

    coverage = len(products) / site_total if site_total else 0
    print(f"Site total: {site_total}, collected: {len(products)} "
          f"({coverage:.1%}), excluded: {dict(excluded) or 'none'}, "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial catalogue must not
    # produce one.
    if coverage < MIN_COVERAGE:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} products -> {csv_path}")


if __name__ == "__main__":
    main()
