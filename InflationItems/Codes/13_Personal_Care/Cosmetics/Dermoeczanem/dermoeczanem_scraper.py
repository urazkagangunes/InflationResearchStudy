"""
dermoeczanem_scraper.py — Dermoeczanem Daily Product Price Scraper

Crawls dermoeczanem.com categories with ?pg=N pagination.
HTML-based, does not require a browser.
"""

import csv
import logging
import os
import re
import sys
import time
import urllib.request
from bs4 import BeautifulSoup
from datetime import date
from pathlib import Path

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / ".git").exists()), Path(__file__).resolve().parents[5])
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Cosmetics" / "Dermoeczanem"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.dermoeczanem.com"

CATEGORIES = [
    {"name": "Skin Care", "slug": "cilt-bakimi"},
    {"name": "Sun Care", "slug": "gunes-urunleri"},
    {"name": "Hair Care", "slug": "sac-bakimi"},
    {"name": "Body Care", "slug": "vucut-bakimi"},
    {"name": "Makeup", "slug": "makyaj"},
    {"name": "Oral Care", "slug": "agiz-ve-dis-sagligi"},
    {"name": "Mother and Baby", "slug": "anne-ve-bebek"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_price(text: str) -> float | None:
    if not text:
        return None
    matches = re.findall(r"([\d]{1,3}(?:\.[\d]{3})*,\d{2})\s*TL", text)
    if not matches:
        matches = re.findall(r"([\d]{1,3}(?:\.[\d]{3})*,\d{2})", text)
    if not matches:
        return None
    try:
        val = float(matches[-1].replace(".", "").replace(",", "."))
        return val if val > 0 else None
    except ValueError:
        return None


def fetch_soup(url: str) -> BeautifulSoup | None:
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                return BeautifulSoup(html, "html.parser")
        except Exception:
            time.sleep(1.5)
    return None


def get_max_page(soup: BeautifulSoup) -> int:
    max_p = 1
    for a in soup.select("a[href*='pg=']"):
        m = re.search(r"pg=(\d+)", a.get("href", ""))
        if m:
            max_p = max(max_p, int(m.group(1)))
    return max_p


def scrape_category(cat: dict) -> list[dict]:
    name = cat["name"]
    slug = cat["slug"]
    url = f"{BASE_URL}/{slug}"
    logger.info(f"▶ Category: {name}")

    first_soup = fetch_soup(url)
    if not first_soup:
        logger.warning(f"  {name} first page could not be loaded.")
        return []

    max_pages = get_max_page(first_soup)
    logger.info(f"  Total pages: {max_pages}")

    items = []
    seen = set()

    for p in range(1, max_pages + 1):
        soup = first_soup if p == 1 else fetch_soup(f"{url}?pg={p}")
        if not soup:
            continue

        cards = soup.select(".product-item, .showcase, .product-card")
        if not cards:
            break

        for c in cards:
            title_el = c.select_one("a[title], .product-title, .title")
            title = title_el.get("title") or title_el.get_text(strip=True) if title_el else ""
            if not title or title in seen:
                continue

            price_el = c.select_one(".current-price, .product-price, [class*='price']")
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = parse_price(price_text)
            if price is None:
                continue

            seen.add(title)
            items.append({
                "product_name": title,
                "price": price,
                "category": name,
            })

        if p % 10 == 0 or p == max_pages:
            logger.info(f"  Page {p}/{max_pages}: total {len(items)} products")

        time.sleep(0.4)

    return items


def main():
    today = str(date.today())
    csv_path = OUT_DIR / f"dermoeczanem_{today}.csv"

    if csv_path.exists():
        logger.info(f"⛔ File already exists for today: {csv_path}")
        return

    logger.info(f"🚀 Dermoeczanem scraper started ({today})")
    all_products = []
    global_seen = set()

    for cat in CATEGORIES:
        cat_items = scrape_category(cat)
        for it in cat_items:
            if it["product_name"] not in global_seen:
                global_seen.add(it["product_name"])
                all_products.append(it)

    if not all_products:
        logger.warning("❌ No products collected.")
        return

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price", "category"])
        writer.writeheader()
        writer.writerows(all_products)

    logger.info(f"✅ {len(all_products)} products saved → {csv_path}")


if __name__ == "__main__":
    main()
