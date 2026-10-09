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

BASE_URL = "https://www.vestel.com.tr"
# HTML fragment behind the listing's infinite scroll; one large page returns
# a whole category, so no browser is needed.
LIST_URL = f"{BASE_URL}/product/getfilteredproductlistpaged"
PAGE_SIZE = 1000
MIN_COVERAGE = 0.98
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Listing categories and the TÜİK 2026 basket items (COICOP 05) they cover.
# Hoods, fans, water dispensers, water heaters and bundle sets are left out
# because the basket has no item for them.
CATEGORIES = [
    ("buzdolabi", 13),                     # 531101 refrigerator
    ("derin-dondurucular", 15),            # 531103 deep freezer
    ("bulasik-makineleri", 11),            # 531106 dishwasher
    ("ankastre-bulasik-makineleri", 28),   # 531106
    ("camasir-makineleri", 14),            # 531201 washing machine
    ("kurutma-makineleri", 16),            # 531202 dryer
    ("firinlar", 2031),                    # 531108 ovens and cookers
    ("ankastre-firinlar", 30),             # 531108
    ("ankastre-mikrodalga-firinlar", 31),  # 531108
    ("tum-ocaklar", 1996),                 # 531108
    ("klimalar", 40),                      # 531301 air conditioner
    ("isiticilar", 39),                    # 531303 heater
]

# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_PARTS = Path(__file__).resolve().parent.parts
_ROOT = _PARTS.index("InflationItems")
OUT_DIR = Path(*_PARTS[:_ROOT + 1], "Datas", *_PARTS[_ROOT + 2:])

CARD_SPLIT_RE = re.compile(r'(?=<li class="product-list-item-wrap)')
ID_RE = re.compile(r'data-id="(\d+)"')
NAME_RE = re.compile(r'class="product-title[^"]*"[^>]*>\s*<span>([^<]+)</span>')
# The card's main price; the separate "Vestel Üyelerine Özel" price needs an
# account, so the price any buyer pays is the one kept.
PRICE_RE = re.compile(r'<span class="discounted[^"]*">\s*([\d.,]+)')
TOTAL_RE = re.compile(r'data-total="(\d+)"')


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


def get(session, url, delay, **kwargs):
    time.sleep(delay + random.uniform(1, 3))
    response = session.get(url, timeout=60, **kwargs)
    response.raise_for_status()
    return response.text


def site_total(session, slug, category_id, delay):
    page = get(session, f"{BASE_URL}/{slug}-c-{category_id}", delay)
    match = TOTAL_RE.search(page)
    if not match:
        raise ValueError(f"no product count on {slug}-c-{category_id}")
    return int(match.group(1))


def parse_price(text):
    integer, _, fraction = text.partition(",")
    value = Decimal(integer.replace(".", "") + "." + (fraction or "0"))
    return value if value > 0 else None


def parse_cards(fragment):
    cards = []
    for block in CARD_SPLIT_RE.split(fragment)[1:]:
        product_id = ID_RE.search(block)
        name = NAME_RE.search(block)
        price = PRICE_RE.search(block)
        if not product_id:
            continue
        cards.append({
            "id": product_id.group(1),
            "product_name": " ".join(html.unescape(name.group(1)).split()) if name else "",
            "price": parse_price(price.group(1)) if price else None,
        })
    return cards


def fetch_category(session, category_id, delay):
    cards, page = [], 1
    while True:
        params = {
            "categoryID": category_id,
            "page": page,
            "dropListingPageSize": PAGE_SIZE,
            # A fixed order keeps page boundaries stable if a category ever
            # needs more than one page.
            "orderOption": "CommentCount",
            "isPartners": "false",
        }
        fragment = get(session, LIST_URL, delay, params=params,
                       headers={"X-Requested-With": "XMLHttpRequest"})
        batch = parse_cards(fragment)
        cards.extend(batch)
        if len(batch) < PAGE_SIZE:
            return cards
        page += 1


def get_csv_path():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return OUT_DIR / f"vestel_{date}.csv"


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
    if not robots.can_fetch(USER_AGENT, LIST_URL):
        print("robots.txt disallows the listing endpoint; CSV not written.")
        sys.exit(1)
    delay = robots.crawl_delay(USER_AGENT) or 0
    print(f"robots.txt Crawl-delay: {delay or 'none'}")

    products, short = {}, []
    for slug, category_id in CATEGORIES:
        try:
            total = site_total(session, slug, category_id, delay)
            cards = fetch_category(session, category_id, delay)
        except (requests.RequestException, ValueError) as e:
            print(f"{slug}: failed after retries: {e!r}; CSV not written.")
            sys.exit(1)
        unique = {card["id"]: card for card in cards}
        print(f"  {slug}: {len(unique)}/{total}")
        if total and len(unique) / total < MIN_COVERAGE:
            short.append(slug)
        for product_id, card in unique.items():
            products.setdefault(product_id, card)

    no_price = [p for p in products.values() if p["price"] is None or not p["product_name"]]
    rows = [(p["product_name"], f"{p['price']:.2f}")
            for p in products.values() if p["price"] is not None and p["product_name"]]
    print(f"Products: {len(products)}, written: {len(rows)}, "
          f"without name or price: {len(no_price)}, "
          f"short categories: {short or 'none'}, "
          f"duration: {time.time() - started:.0f}s")
    # The runner counts any CSV as success, so a partial listing must not produce one.
    if short or not rows:
        print("Coverage below minimum; CSV not written.")
        sys.exit(1)

    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} products -> {csv_path}")


if __name__ == "__main__":
    main()
