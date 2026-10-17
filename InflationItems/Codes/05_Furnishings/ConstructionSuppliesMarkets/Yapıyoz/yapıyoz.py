import csv
import os
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "coicop").is_dir())))
import coicop  # noqa: E402


BASE_URL = "https://www.yapiyoz.net/"
# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...); the file used to land in the working directory.
_PARTS = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
_ROOT = _PARTS.index("InflationItems")
DATA_DIR = os.sep.join(_PARTS[:_ROOT + 1] + ["Datas"] + _PARTS[_ROOT + 2:])
CSV_FILE = os.path.join(DATA_DIR, f"yapiyoz_{datetime.now().strftime('%Y-%m-%d')}.csv")

SPACE_RE = re.compile(r"\s+")
PRICE_RE = re.compile(r"(\d[\d\.\,]*)\s*TL", re.IGNORECASE)


def clean_text(text: str) -> str:
    if not text:
        return ""
    return SPACE_RE.sub(" ", text).strip()


def parse_price(text: str):
    if not text:
        return None

    text = clean_text(text)

    match = PRICE_RE.search(text)
    if not match:
        return None

    value = match.group(1)

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def wait_for_page(driver, seconds=20):
    WebDriverWait(driver, seconds).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def get_soup(driver, url: str) -> BeautifulSoup:
    driver.get(url)
    wait_for_page(driver, 30)
    time.sleep(random.uniform(2.0, 3.5))
    return BeautifulSoup(driver.page_source, "html.parser")


def normalize_url(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def get_category_links(driver):
    soup = get_soup(driver, BASE_URL)
    links = set()

    for a in soup.select('a[href*="/kategori/"]'):
        href = a.get("href")
        if not href:
            continue
        full = normalize_url(urljoin(BASE_URL, href))
        if full.startswith(BASE_URL.rstrip("/")):
            links.add(full)

    return sorted(links)


def get_product_links_from_category(driver, category_url: str):
    visited_pages = set()
    # product link -> the (sub)category page it was first listed on
    product_links = {}
    queue = [category_url]

    while queue:
        url = queue.pop(0)
        url = normalize_url(url)

        if url in visited_pages:
            continue
        visited_pages.add(url)

        print(f"[KATEGORI] {url}")

        try:
            soup = get_soup(driver, url)
        except Exception as e:
            print(f"  [ERR] Kategori açılamadı: {e}")
            continue

        
        for a in soup.select('a[href*="/urun/"]'):
            href = a.get("href")
            if not href:
                continue
            full = normalize_url(urljoin(BASE_URL, href))
            if full.startswith(BASE_URL.rstrip("/")):
                product_links.setdefault(full, url)

       
        for a in soup.select("a[href]"):
            href = a.get("href")
            if not href:
                continue

            full = normalize_url(urljoin(url, href))

            if not full.startswith(BASE_URL.rstrip("/")):
                continue

            if full == url:
                continue

            
            # Filter links (?marka=...) list a subset of the same products and
            # multiplied the browser page loads; only plain subcategories are followed.
            if (
                "/kategori/" in full
                and "?" not in full
                and full.startswith(category_url.rstrip("/"))
                and full not in visited_pages
            ):
                queue.append(full)

          
            if (
                "/kategori/" in full
                and ("page=" in full or "sayfa=" in full or "/page/" in full)
                and full not in visited_pages
            ):
                queue.append(full)

        print(f"  -> Şu ana kadar {len(product_links)} ürün linki bulundu")
        time.sleep(random.uniform(1.0, 2.0))

    return product_links


def extract_product_name(soup: BeautifulSoup) -> str:
    selectors = [
        "h1.product_title",
        "h1.product-title",
        "h1.entry-title",
        "div.product-detail h1",
        "h1",
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                return text

    return ""


def extract_product_price(soup: BeautifulSoup):
    selectors = [
        ".product-price-current",
        ".indirimliFiyat",
        ".sale-price",
        ".product-price .discount-price",
        ".price",
        ".fiyat",
        ".urunFiyat",
    ]

    for sel in selectors:
        for el in soup.select(sel):
            price = parse_price(el.get_text(" ", strip=True))
            if price is not None:
                return price

 
    full_text = clean_text(soup.get_text(" ", strip=True))
    return parse_price(full_text)


def scrape_product(driver, product_url: str):
    try:
        soup = get_soup(driver, product_url)
    except Exception as e:
        print(f"  [ERR] Ürün açılamadı: {product_url} -> {e}")
        return None

    title = extract_product_name(soup)
    price = extract_product_price(soup)

    if not title or price is None:
        print(f"  [FAIL] Okunamadı: {product_url}")
        return None

    return title, price


def main():
    driver = None
    try:
        driver = get_driver()

        print("[*] Kategoriler toplanıyor...")
        categories = get_category_links(driver)
        print(f"[+] {len(categories)} kategori bulundu")

        link_category = {}

        for i, cat in enumerate(categories, start=1):
            print(f"\n[{i}/{len(categories)}] Kategori taranıyor")
            links = get_product_links_from_category(driver, cat)
            for link, page in links.items():
                link_category.setdefault(link, page)

        all_product_links = sorted(link_category)
        print(f"\n[+] Toplam benzersiz ürün linki: {len(all_product_links)}")

        rows = []
        seen = set()

        for i, product_url in enumerate(all_product_links, start=1):
            print(f"[URUN {i}/{len(all_product_links)}] {product_url}")
            result = scrape_product(driver, product_url)

            if not result:
                continue

            name, price = result
            key = (name, f"{price:.2f}")

            if key in seen:
                continue
            seen.add(key)

            rows.append(coicop.row(name, f"{price:.2f}", link_category[product_url], "Yapıyoz"))

            print(f"  [OK] {name} -> {price:.2f}")
            time.sleep(random.uniform(0.8, 1.8))

        if not rows:
            print("[HATA] Hiç ürün okunamadı, CSV yazılmadı.")
            sys.exit(1)

        # Written once at the end with the header the central inflation script
        # reads; the old rows (timestamp, 0, name, price) had no header.
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(coicop.FIELDS)
            writer.writerows(rows)

        print(f"\n[BİTTİ] {len(rows)} kayıt yazıldı -> {CSV_FILE}")

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
