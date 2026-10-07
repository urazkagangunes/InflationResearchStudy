import csv
import html
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

BASE_URL = "https://onlinekombi.com"
# The combi boiler listing, TÜİK 2026 basket item 531306 (COICOP 05). The
# store sells several brands itself; Bauhaus, the first choice, blocks
# scripted requests (decision of 2026-10-07).
CATEGORY_URL = f"{BASE_URL}/kombi/"
MIN_COVERAGE = 0.98
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "OnlineKombi"

CARD_SPLIT_RE = re.compile(r'(?=data-productid=)')
ID_RE = re.compile(r'data-productid="?([0-9a-f]+)')
NAME_RE = re.compile(r'class="?title"?>([^<]+)</a>')
# Discounted cards also show the old price; "actual-price" is the one paid.
PRICE_RE = re.compile(r'class="actual-price price">\s*₺?\s*([\d.,]+)')
TOTAL_RE = re.compile(r'class="?items-total"?>\s*(\d+)')
PAGE_SIZE_RE = re.compile(r'class="items-page-size[^"]*">\s*(\d+)')
BRAND_RE = re.compile(r'href="/([a-z]+-kombi)/"')
NON_BRAND = {"elektrikli-kombi", "yogusmali-kombi"}


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


def fetch_page(session, url, delay):
    time.sleep(delay + random.uniform(2, 4))
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def parse_price(text):
    integer, _, fraction = text.partition(",")
    value = Decimal(integer.replace(".", "") + "." + (fraction or "0"))
    return value if value > 0 else None


def parse_cards(page):
    cards = []
    for block in CARD_SPLIT_RE.split(page)[1:]:
        product_id = ID_RE.search(block)
        name = NAME_RE.search(block)
        price = PRICE_RE.search(block)
        if not product_id or not name:
            continue
        cards.append({
            "id": product_id.group(1),
            "product_name": " ".join(html.unescape(name.group(1)).split()),
            "price": parse_price(price.group(1)) if price else None,
        })
    return cards


def get_csv_path():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return OUT_DIR / f"onlinekombi_{date}.csv"


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
    if not robots.can_fetch(USER_AGENT, CATEGORY_URL):
        print("robots.txt disallows the listing; CSV not written.")
        sys.exit(1)
    delay = robots.crawl_delay(USER_AGENT) or 0
    print(f"robots.txt Crawl-delay: {delay or 'none'}")

    # robots.txt disallows every URL with a query, paging included; the brand
    # listings without parameters each fit on one page and together cover all.
    try:
        first = fetch_page(session, CATEGORY_URL, delay)
        total = int(TOTAL_RE.search(first).group(1))
        page_size = int(PAGE_SIZE_RE.search(first).group(1))
        products = {card["id"]: card for card in parse_cards(first)}
        brands = sorted(set(BRAND_RE.findall(first)) - NON_BRAND)
        for brand in brands:
            url = f"{BASE_URL}/{brand}/"
            if not robots.can_fetch(USER_AGENT, url):
                continue
            page = fetch_page(session, url, delay)
            brand_total = TOTAL_RE.search(page)
            cards = parse_cards(page)
            print(f"  {brand}: {len(cards)}/{brand_total.group(1) if brand_total else 0}")
            if brand_total and int(brand_total.group(1)) > page_size:
                print(f"{brand} needs more than one page; CSV not written.")
                sys.exit(1)
            for card in cards:
                products.setdefault(card["id"], card)
    except (requests.RequestException, AttributeError, ValueError) as e:
        print(f"Listing failed: {e!r}; CSV not written.")
        sys.exit(1)

    rows = [(p["product_name"], f"{p['price']:.2f}")
            for p in products.values() if p["price"]]
    coverage = len(products) / total if total else 0
    print(f"Products: {len(products)}/{total} ({coverage:.1%}), written: {len(rows)}, "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial listing must not produce one.
    if coverage < MIN_COVERAGE or not rows:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} products -> {csv_path}")


if __name__ == "__main__":
    main()
