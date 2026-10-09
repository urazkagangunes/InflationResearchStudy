import os
import re
import time
import random
import pandas as pd
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_PATH = r"C:\Users\SEDA\Desktop\AvvaChromeProfile"
OUTPUT_FOLDER = r"C:\Users\SEDA\OneDrive - ozyegin.edu.tr\Desktop\ai201\Avva\Datas\ClothingStores\Avva"

CATEGORY_URLS = [
    "https://www.avva.com.tr/erkek-ev-ve-ic-giyim",
    "https://www.avva.com.tr/erkek-canta-valiz",
    "https://www.avva.com.tr/erkek-saat",
    "https://www.avva.com.tr/erkek-aksesuar",
    "https://www.avva.com.tr/erkek-sort",
    "https://www.avva.com.tr/erkek-ayakkabi",
    "https://www.avva.com.tr/erkek-esofman-alti",
    "https://www.avva.com.tr/erkek-ceket",
    "https://www.avva.com.tr/takim-elbise",
    "https://www.avva.com.tr/erkek-esofman-takimi",
    "https://www.avva.com.tr/erkek-kazak",
    "https://www.avva.com.tr/polar",
    "https://www.avva.com.tr/erkek-sweatshirt",
    "https://www.avva.com.tr/erkek-pantolon",
    "https://www.avva.com.tr/erkek-triko-t-shirt",
    "https://www.avva.com.tr/erkek-t-shirt",
    "https://www.avva.com.tr/erkek-gomlek/gomlek-ceket",
    "https://www.avva.com.tr/erkek-mont",
]

MAX_PAGE = 5


def clean_price(text):
    if not text:
        return None
    text = text.replace("TL", "").replace("₺", "").strip()
    text = text.replace(".", "").replace(",", ".")
    text = re.sub(r"[^\d.]", "", text)
    try:
        return float(text) if text else None
    except:
        return None


def get_category_name_from_url(url):
    return url.rstrip("/").split("/")[-1]


def build_browser():
    co = ChromiumOptions()
    co.set_browser_path(CHROME_PATH)
    co.set_user_data_path(USER_DATA_PATH)
    co.set_paths(local_port=9333)
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--start-maximized")
    co.set_argument("--no-first-run")
    co.set_argument("--no-default-browser-check")
    return ChromiumPage(co)


def human_scroll(page):
    try:
        page.scroll.to_half()
        time.sleep(1)
        page.scroll.to_bottom()
        time.sleep(2)
    except:
        pass


def extract_products_from_text(page_text, category_name):
    if not page_text:
        return []

    text = page_text.replace("\r", "")
    results = []
    seen = set()

    pattern = re.compile(
        r"AVVA\s+"
        r"(?P<name>.+?)\s+"
        r"(?P<price1>\d{1,3}(?:\.\d{3})*,\d{2})\s*TL\s*KDV Dahil"
        r"(?:\s+(?P<price2>\d{1,3}(?:\.\d{3})*,\d{2})\s*TL\s*KDV Dahil)?"
        r".{0,300}?"
        r"Ürünü İncele",
        re.DOTALL
    )

    for m in pattern.finditer(text):
        name = " ".join(m.group("name").split())

        p1 = clean_price(m.group("price1"))
        p2 = clean_price(m.group("price2")) if m.group("price2") else None
        valid_prices = [p for p in [p1, p2] if p is not None]
        price = min(valid_prices) if valid_prices else None

        if not name or price is None:
            continue

        key = (category_name, name, price)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "Category": category_name,
            "Product_Name": name,
            "Price": price,
        })

    return results


def scrape_avva():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    page = build_browser()
    results = []

    try:
        for category_url in CATEGORY_URLS:
            category_name = get_category_name_from_url(category_url)
            print(f"\n[INFO] Category: {category_name}")

            seen_in_category = set()

            for page_num in range(1, MAX_PAGE + 1):
                url = f"{category_url}?pg={page_num}"
                print(f"[INFO] Opening: {url}")

                try:
                    page.get(url, timeout=40)
                    time.sleep(random.uniform(3, 5))
                    human_scroll(page)
                    time.sleep(random.uniform(1.5, 2.5))
                except Exception as e:
                    print(f"[WARN] Could not open page: {e}")
                    continue

                body = page.ele('tag:body')
                page_text = body.text if body else ""

                page_rows = extract_products_from_text(page_text, category_name)

                # only keep genuinely new products for this category
                new_rows = []
                for row in page_rows:
                    key = (row["Category"], row["Product_Name"], row["Price"])
                    if key not in seen_in_category:
                        seen_in_category.add(key)
                        new_rows.append(row)

                print(f"[INFO] Extracted {len(new_rows)} new products from page {page_num}")
                results.extend(new_rows)

                # if page added nothing new, stop this category
                if len(new_rows) == 0:
                    print(f"[INFO] No new products on page {page_num}, stopping category.")
                    break

                time.sleep(random.uniform(3.0, 7.5))

        if results:
            df = pd.DataFrame(results)
            df.drop_duplicates(subset=["Category", "Product_Name", "Price"], inplace=True)

            out_path = os.path.join(
                OUTPUT_FOLDER,
                f"avva_{datetime.now().strftime('%Y-%m-%d')}.csv"
            )
            df.to_csv(out_path, index=False, encoding="utf-8-sig")

            print(f"\n[SUCCESS] Saved {len(df)} rows")
            print(out_path)
        else:
            print("\n[INFO] No data collected")

    finally:
        try:
            page.quit()
        except:
            pass


if __name__ == "__main__":
    scrape_avva()
