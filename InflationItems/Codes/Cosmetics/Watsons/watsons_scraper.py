import os
import time
import csv
import json
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from camoufox.sync_api import Camoufox

# --- File paths ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
DATAS_DIR = os.path.join(_PROJECT_ROOT, "InflationItems", "Datas", "Cosmetics", "Watsons")
os.makedirs(DATAS_DIR, exist_ok=True)
MASTER_DB_PATH = os.path.join(DATAS_DIR, "watsons_master_db.json")
SITEMAP_CACHE_PATH = os.path.join(DATAS_DIR, "sitemap_cache.json")


def get_cookies():
    print("🔄 Opening browser with Camoufox (Akamai Bypass)...")
    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        page.goto("https://www.watsons.com.tr/", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        cookies = {c['name']: c['value'] for c in page.context.cookies()}
        return cookies


def run_poc_scraper():
    print("⏳ Loading cache and database files...")

    # 1. Load sitemap cache
    if not os.path.exists(SITEMAP_CACHE_PATH):
        print("❌ sitemap_cache.json not found! Please download the sitemap first.")
        return

    with open(SITEMAP_CACHE_PATH, "r", encoding="utf-8") as f:
        sitemap_data = json.load(f)

    master_db = {}
    if os.path.exists(MASTER_DB_PATH):
        with open(MASTER_DB_PATH, "r", encoding="utf-8") as f:
            master_db = json.load(f)

    today_str = datetime.now().strftime("%Y-%m-%d")
    csv_file = os.path.join(DATAS_DIR, f"{today_str}_watsons_fiyatlar.csv")

    total_items = len(sitemap_data)
    print(f"🚀 Watsons scraper started! Total {total_items} items to process.\n")

    # Fetch cookies and initialize HTTP session
    session_cookies = get_cookies()
    client = requests.Session(impersonate="chrome")

    scraped = 0
    skipped = 0

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=['product_name', 'price', 'url'])
        writer.writeheader()

        for idx, (url, sitemap_date) in enumerate(sitemap_data.items(), start=1):

            # --- Cache hit (skip scraping) ---
            if url in master_db and master_db[url].get('lastmod') == sitemap_date:
                item = master_db[url]
                writer.writerow({'product_name': item['name'], 'price': item['price'], 'url': url})
                skipped += 1

                if skipped % 100 == 0:
                    print(f"⏩ [FAST PASS] {skipped} items copied from Master DB...")
                continue

            # --- New or modified product (scrape) ---
            try:
                res = client.get(url, cookies=session_cookies, timeout=10)

                if res.status_code == 403:
                    print("\n⛔ 403 Forbidden received! Refreshing session cookies...")
                    session_cookies = get_cookies()
                    time.sleep(2)
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                name, price = "N/A", "N/A"

                for script in soup.find_all('script', type='application/ld+json'):
                    if script.string and url in script.string:
                        data = json.loads(script.string)
                        for entry in data.get('@graph', []):
                            if entry.get('@type') == 'Product':
                                name = entry.get('name', 'N/A')
                                break

                price_el = soup.select_one('span.price__default-value')
                if price_el:
                    price = price_el.text.strip()

                print(f"✅ [SCRAPED] {name[:40]}... -> {price}")

                # Update database
                master_db[url] = {"lastmod": sitemap_date, "name": name, "price": price}
                writer.writerow({'product_name': name, 'price': price, 'url': url})
                scraped += 1
                f.flush()

                if scraped % 10 == 0:
                    with open(MASTER_DB_PATH, "w", encoding="utf-8") as db_f:
                        json.dump(master_db, db_f, indent=4, ensure_ascii=False)

                time.sleep(0.3)

            except Exception as e:
                print(f"❌ [ERROR] {url.split('/')[-1]}: {e}")

    # Save final database state
    with open(MASTER_DB_PATH, "w", encoding="utf-8") as db_f:
        json.dump(master_db, db_f, indent=4, ensure_ascii=False)

    print(f"\n🎉 Scraping finished:")
    print(f"   -> Total cached items skipped: {skipped}")
    print(f"   -> Total new items scraped: {scraped}")
    print(f"   -> Output file: {csv_file}")


if __name__ == "__main__":
    run_poc_scraper()
