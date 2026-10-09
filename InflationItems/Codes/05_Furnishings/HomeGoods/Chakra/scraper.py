import csv
import os
import random
import sys
import time
from datetime import datetime

import requests

BASE_URL = "https://www.chakra.com.tr"

# Every home-goods top category, plus the home-goods subtrees of the mixed
# "Bebek & Çocuk" and "Kozmetik" menus; clothing and personal care are out.
CATEGORIES = [
    "mobilya",
    "yatak-odasi",
    "ev-dekorasyonu",
    "banyo",
    "sofra-mutfak",
    "bebek-cocuk/bebek-cocuk-odasi",
    "kozmetik/oda-kokusu",
    "kozmetik/camasir-kokusu",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    # Category pages answer XHR requests with the listing as JSON
    # (pagination, prices and stock), the same data the page renders.
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

FIELDS = ["product_name", "price"]
MAX_ATTEMPTS = 5
MIN_COVERAGE = 0.98


def polite_sleep():
    time.sleep(random.uniform(1, 3))


def fetch_page(session, url, page):
    params = {"page": page} if page > 1 else None
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            if response.status_code != 429 and response.status_code < 500:
                response.raise_for_status()
            error = f"HTTP {response.status_code}"
        except requests.HTTPError:
            raise
        except (requests.RequestException, ValueError) as exc:
            error = exc
        if attempt == MAX_ATTEMPTS:
            break
        wait = 5 * 2 ** (attempt - 1) + random.uniform(0, 2)
        print(f"  {url} page {page}: {error}; "
              f"retry {attempt}/{MAX_ATTEMPTS} in {wait:.0f}s")
        time.sleep(wait)
    raise RuntimeError(
        f"{url} page {page} failed after {MAX_ATTEMPTS} attempts: {error}")


def parse_price(value):
    # The JSON carries plain decimals ("36960", "249.99"), not "1.299,90".
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return value if price > 0 else None


def scrape_category(session, category, seen_ids):
    url = f"{BASE_URL}/{category}/"
    rows = []
    category_ids = set()
    page = 1
    num_pages = 1
    total_count = None
    skipped = 0

    while page <= num_pages:
        data = fetch_page(session, url, page)
        pagination = data["pagination"]
        # Out-of-range page numbers are answered with page 1, not an error.
        if pagination["current_page"] != page:
            print(f"WARNING: {category} page {page} answered as "
                  f"page {pagination['current_page']}")
            break
        num_pages = pagination["num_pages"]
        total_count = pagination["total_count"]
        products = data["products"]
        print(f"  {category} page {page}/{num_pages}: "
              f"{len(products)} products")
        if not products:
            break

        for product in products:
            product_id = product.get("sku") or str(product["pk"])
            category_ids.add(product_id)
            price = parse_price(product.get("price"))
            if price is None:
                skipped += 1
                continue
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            rows.append({
                "product_name": product["name"].strip(),
                "price": price,
            })

        page += 1
        if page <= num_pages:
            polite_sleep()

    print(
        f"{category}: site count {total_count}, "
        f"unique in listing {len(category_ids)}, new rows {len(rows)}, "
        f"skipped without price {skipped}"
    )
    # The runner counts any CSV as success, so a partial catalogue must not produce one.
    if total_count and len(category_ids) < MIN_COVERAGE * total_count:
        raise RuntimeError(
            f"{category}: {len(category_ids)} of {total_count} products listed; "
            f"CSV not written")
    if total_count is not None and len(category_ids) < total_count:
        print(f"WARNING: {category} returned fewer products "
              f"than the site count")
    return rows


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    seen_ids = set()
    all_rows = []

    for index, category in enumerate(CATEGORIES):
        if index:
            polite_sleep()
        all_rows.extend(scrape_category(session, category, seen_ids))

    if not all_rows:
        print("No products collected; CSV not written.")
        sys.exit(1)

    # The script lives in InflationItems/Codes/HomeGoods/Chakra, so the repo root is four levels up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_dir = os.path.join(repo_root, "InflationItems", "Datas", "HomeGoods", "Chakra")
    os.makedirs(output_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(output_dir, f"chakra_all_categories_{date_str}.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} unique products to {filepath}")


if __name__ == "__main__":
    main()
