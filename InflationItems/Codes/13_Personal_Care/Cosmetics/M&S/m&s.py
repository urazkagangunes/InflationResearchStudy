from pathlib import Path
import csv
import os
import re
import time
import random
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = next((p for p in SCRIPT_DIR.parents if (p / ".git").exists()), SCRIPT_DIR.parents[4])
OUT_DIR = os.path.join(_PROJECT_ROOT, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "M&S")
PROFILE_DIR = os.path.join(SCRIPT_DIR, "SeleniumProfile_MS")
URL = "https://www.marksandspencer.com.tr/list/?layout=4&category_ids=84"

seen = set()


def get_chrome_version_main():
    try:
        import subprocess
        for cmd in ["google-chrome --version", "google-chrome-stable --version", "chromium --version", "chromium-browser --version"]:
            try:
                res = subprocess.check_output(cmd, shell=True, text=True)
                m = re.search(r"(\d+)\.\d+\.\d+", res)
                if m:
                    return int(m.group(1))
            except Exception:
                pass
    except Exception:
        pass
    return None


def open_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--headless=new")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    v_main = get_chrome_version_main()
    if v_main:
        driver = uc.Chrome(options=opts, version_main=v_main)
    else:
        driver = uc.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver


def get_csv_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    today_str = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return os.path.join(OUT_DIR, f"ms_cosmetics_{today_str}.csv")


def clean_price(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.replace("TL", "").replace("₺", "").replace("\xa0", " ").strip()
    m = re.search(r"[\d.,]+", raw)
    return m.group(0) if m else ""


def scroll_to_bottom(driver, wait_sec=2.0, max_rounds=80):
    last_height, stable = driver.execute_script("return document.body.scrollHeight"), 0
    for _ in range(max_rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_sec)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stable += 1
            if stable >= 3:
                break
        else:
            stable, last_height = 0, new_height


def parse_products(soup):
    batch = []
    names = soup.select("a.product-item__name")
    prices = soup.select("pz-price")

    for name_el, price_el in zip(names, prices):
        name = name_el.get_text(" ", strip=True)
        price = clean_price(price_el.get_text(" ", strip=True))
        if not name or not price:
            continue
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        batch.append({"product_name": name, "price": price})
    return batch


def get_max_pages(soup):
    max_p = 1
    for a in soup.select("a[href]"):
        m = re.search(r"[?&]page=(\d+)", a.get("href", ""))
        if m:
            max_p = max(max_p, int(m.group(1)))
    for el in soup.select("li.pager-item, li.page-item, .pagination li"):
        t = el.get_text(strip=True)
        if t.isdigit():
            max_p = max(max_p, int(t))
    return max_p


def main():
    csv_path = get_csv_path()
    print("=" * 55)
    print("  M&S TR Cosmetics Scraper")
    print("=" * 55)
    print(f"  Output: {csv_path}\n")

    driver = open_driver()
    all_products = []
    page = 1

    try:
        while True:
            url = URL if page == 1 else f"{URL}&page={page}"
            print(f"  Page {page}: {url}")
            driver.get(url)
            time.sleep(8)  # Wait for JS rendering
            scroll_to_bottom(driver)
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            batch = parse_products(soup)

            if not batch:
                print("  ⚠️  No products found, stopping pagination.")
                break

            all_products.extend(batch)
            print(f"  ✅ {len(batch)} products (total: {len(all_products)})")

            max_p = get_max_pages(soup)
            if page >= max_p:
                break
            page += 1
            time.sleep(random.uniform(2, 4))

    except KeyboardInterrupt:
        print("\nScraper interrupted by user.")
    finally:
        driver.quit()
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)

    if all_products:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["product_name", "price"])
            w.writeheader()
            w.writerows(all_products)
        print(f"\n✅ {len(all_products)} products saved → {csv_path}")
    else:
        print("\n❌ No products collected.")


if __name__ == "__main__":
    main()
