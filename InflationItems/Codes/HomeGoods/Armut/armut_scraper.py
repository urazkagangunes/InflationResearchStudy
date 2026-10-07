import csv
import json
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

BASE_URL = "https://armut.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Services for the three TÜİK 2026 basket service items in COICOP 05. No
# retailer or tariff publishes these prices; Armut's price pages are the only
# web source found (decision of 2026-10-07). Services with a few quotes a
# month (white goods repair, sofa repair) were left out as too noisy.
SERVICES = [
    ("camasir-makinesi-tamiri", 44517, "Çamaşır makinesi tamiri"),  # 533001
    ("kombi-tamiri", 459, "Kombi tamiri"),                          # 533001
    ("koltuk-yikama-temizleme", 727, "Koltuk yıkama"),              # 562901
    ("hali-yikama-temizleme", 87, "Halı yıkama"),                   # 562901
    ("ev-temizligi", 191, "Ev temizliği"),                          # 562902
]
CITIES = [
    ("istanbul", 34, "İstanbul"),
    ("ankara", 6, "Ankara"),
    ("izmir", 35, "İzmir"),
]

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Armut"

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


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


def page_url(service_slug, service_id, city_slug, city_id):
    return f"{BASE_URL}/fiyatlari/{city_slug}-{service_slug}_{service_id}_{city_id}"


def target_month(today):
    # The newest month on a page differs between requests (the same page gave
    # August and September minutes apart); two months back is always complete.
    year, month = divmod(today.year * 12 + today.month - 1 - 2, 12)
    return f"{year:04d}-{month + 1:02d}-01"


def month_price(session, url, target, delay):
    time.sleep(delay + random.uniform(2, 4))
    response = session.get(url, timeout=60)
    response.raise_for_status()
    match = NEXT_DATA_RE.search(response.text)
    if not match:
        raise ValueError(f"no page data on {url}")
    data = json.loads(match.group(1))["props"]["pageProps"]["data"]["pricePageData"]
    # The headline "Ortalama Fiyat" range is static; the monthly series is
    # computed from the quotes given that month and moves with prices.
    months = [m for m in data.get("monthlyPrices") or []
              if m.get("avgPrice") and m["month"] <= target]
    if not months:
        raise ValueError(f"no monthly price up to {target} on {url}")
    return max(months, key=lambda m: m["month"])


def get_csv_path():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return OUT_DIR / f"armut_{date}.csv"


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
    if not robots.can_fetch(USER_AGENT, page_url(*SERVICES[0][:2], *CITIES[0][:2])):
        print("robots.txt disallows the price pages; CSV not written.")
        sys.exit(1)
    delay = robots.crawl_delay(USER_AGENT) or 0
    print(f"robots.txt Crawl-delay: {delay or 'none'}")

    target = target_month(datetime.now(ZoneInfo("Europe/Istanbul")))
    print(f"Month: {target[:7]}")
    rows = []
    for service_slug, service_id, service_name in SERVICES:
        for city_slug, city_id, city_name in CITIES:
            url = page_url(service_slug, service_id, city_slug, city_id)
            try:
                month = month_price(session, url, target, delay)
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"{url}: failed: {e!r}; CSV not written.")
                sys.exit(1)
            # The month stays out of the name so that day-to-day matching
            # carries the series across month changes.
            name = f"{service_name} | {city_name} | aylık ortalama teklif"
            price = Decimal(str(month["avgPrice"])).quantize(Decimal("0.01"))
            rows.append((name, f"{price:.2f}"))
            print(f"  {name}: {price} ({month['month'][:7]}, "
                  f"{month.get('quoteCount')} quotes)")

    print(f"Written rows: {len(rows)}, duration: {time.time() - started:.0f}s")
    csv_path = get_csv_path()
    write_csv(rows, csv_path)
    print(f"Written: {len(rows)} rows -> {csv_path}")


if __name__ == "__main__":
    main()
