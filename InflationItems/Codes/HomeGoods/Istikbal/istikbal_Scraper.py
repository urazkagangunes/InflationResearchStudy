import os
import csv
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.istikbal.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

CATEGORIES = [
    {"name": "Oturma Odası", "url": f"{BASE_URL}/kategori/oturma-odasi"},
    {"name": "Yemek Odası", "url": f"{BASE_URL}/kategori/yemek-odasi-takimlari"},
    {"name": "Yatak Odası", "url": f"{BASE_URL}/kategori/yatak-odasi-takimlari"},
    {"name": "Yatak", "url": f"{BASE_URL}/kategori/yatak"},
    {"name": "Baza ve Başlık", "url": f"{BASE_URL}/kategori/yatak-baza"},
    {"name": "Genç ve Çocuk Odası", "url": f"{BASE_URL}/kategori/cocuk-genc-odasi-takimlari"},
    {"name": "Bahçe Mobilyası", "url": f"{BASE_URL}/kategori/bahce-mobilyalari"},
    {"name": "Tamamlayıcı Ürünler", "url": f"{BASE_URL}/kategori/tamamlayici-urunler"},
    {"name": "Online Özel", "url": f"{BASE_URL}/kategori/online-ozel"},
    {"name": "Düğün Paketi", "url": f"{BASE_URL}/kategori/dugun-paketi"},
]

# robots.txt: Crawl-delay 30.
CRAWL_DELAY = 30
MAX_RETRIES = 5
RETRY_STATUSES = {429, 500, 502, 503, 504}
CATEGORY_ATTEMPTS = 2


class IncompleteCategory(Exception):
    pass


def fetch(session, url):
    for attempt in range(MAX_RETRIES):
        time.sleep(CRAWL_DELAY)
        try:
            response = session.get(url, timeout=30)
        except requests.RequestException as exc:
            print(f"  -> {type(exc).__name__} on {url} (attempt {attempt + 1}/{MAX_RETRIES})")
        else:
            if response.status_code == 200:
                return response.text
            print(f"  -> Status {response.status_code} on {url} "
                  f"(attempt {attempt + 1}/{MAX_RETRIES})")
            if response.status_code not in RETRY_STATUSES:
                break
        time.sleep(5 * 2 ** attempt)
    raise IncompleteCategory(f"could not fetch {url}")


def parse_page(html):
    """Returns the 'Toplam N ürün' count (None if absent) and (url, name, price) per card."""
    soup = BeautifulSoup(html, "lxml")

    total = None
    count_element = soup.select_one(".record-count")
    if count_element:
        match = re.search(r"Toplam\s+(\d+)\s+ürün", count_element.get_text(" ", strip=True))
        if match:
            total = int(match.group(1))

    products = []
    for card in soup.select(".showcase"):
        link = card.select_one(".showcase-title a")
        name = card.select_one(".showcase-title h3")
        price = card.select_one(".showcase-price-new") or card.select_one(".showcase-price")
        if link is None or not link.get("href") or name is None:
            continue
        products.append((
            link["href"],
            " ".join(name.get_text().split()),
            " ".join(price.get_text().split()) if price else "",
        ))
    return total, products


def scrape_category(session, category):
    """Pages a category until all 'Toplam N ürün' products are collected, else raises."""
    total, products = parse_page(fetch(session, category["url"]))
    if total is None:
        raise IncompleteCategory(f"{category['name']}: 'Toplam N ürün' not found")

    listed = {}
    page = 1
    while True:
        new_urls = [url for url, _, _ in products if url not in listed]
        for url, name, price in products:
            listed.setdefault(url, (name, price))
        print(f"  -> Page {page}: {len(new_urls)} new, {len(listed)}/{total}")
        if len(listed) >= total or not new_urls:
            break
        page += 1
        _, products = parse_page(fetch(session, f"{category['url']}?tp={page}"))

    if len(listed) < total:
        raise IncompleteCategory(f"{category['name']}: collected {len(listed)} of {total} products")
    return listed


def scrape_istikbal():
    session = requests.Session()
    session.headers.update(HEADERS)

    all_products = []
    # A product listed under several categories is kept once, under the first one.
    seen_urls = set()

    for category in CATEGORIES:
        print(f"\n--- Scraping category: {category['name']} ---")
        for attempt in range(1, CATEGORY_ATTEMPTS + 1):
            try:
                listed = scrape_category(session, category)
                break
            except IncompleteCategory as exc:
                print(f"  -> Attempt {attempt}/{CATEGORY_ATTEMPTS} failed: {exc}")
                if attempt == CATEGORY_ATTEMPTS:
                    raise

        kept = skipped = 0
        for url, (name, price) in listed.items():
            if url in seen_urls:
                continue
            seen_urls.add(url)
            # The site briefly showed "0,00 TL" for some products (2026-09-05/06).
            if not re.search(r"[1-9]", price):
                skipped += 1
                continue
            all_products.append([name, price])
            kept += 1
        print(f"  -> Kept {kept}, skipped {skipped} without a price, "
              f"{len(listed) - kept - skipped} already in an earlier category.")

    return all_products


def save_to_csv(data):
    """Saves the scraped data to a CSV file in the specified directory structure."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    target_dir = os.path.join(base_dir, "InflationItems", "Datas", "HomeGoods", "Istikbal")

    os.makedirs(target_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"istikbal_{date_str}.csv"
    file_path = os.path.join(target_dir, filename)

    with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(['product_name', 'price'])
        writer.writerows(data)

    print(f"\nData successfully saved to: {file_path}")
    print(f"Total records collected across all categories: {len(data)}")


if __name__ == "__main__":
    print("Starting Istikbal Scraper...")
    try:
        scraped_data = scrape_istikbal()
    except IncompleteCategory as exc:
        print(f"\nRun failed, no CSV written: {exc}")
        sys.exit(1)

    if not scraped_data:
        print("No data was collected.")
        sys.exit(1)
    save_to_csv(scraped_data)
