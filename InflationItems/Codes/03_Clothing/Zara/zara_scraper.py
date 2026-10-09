import os
import csv
import time
import re
import requests
import json
import shutil
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import undetected_chromedriver as uc


WOMEN_URLS = [
    "https://www.zara.com/tr/tr/kadin-ceketler-l1114.html?v1=2417772",
    "https://www.zara.com/tr/tr/kadin-dish-giyim-l1184.html?v1=2419032",
    "https://www.zara.com/tr/tr/kadin-blazerlar-l1055.html?v1=2420942",
    "https://www.zara.com/tr/tr/kadin-elbiseler-l1066.html?v1=2420896",
    "https://www.zara.com/tr/tr/kadin-gemlekler-l1217.html?v1=2420369",
    "https://www.zara.com/tr/tr/kadin-est-giyim-l1322.html?v1=2419940",
    "https://www.zara.com/tr/tr/kadin-hirka-kazak-l8322.html?v1=2419844",
    "https://www.zara.com/tr/tr/kadin-tishertler-l1362.html?v1=2420417",
    "https://www.zara.com/tr/tr/kadin-pantolonlar-l1335.html?v1=2420795",
    "https://www.zara.com/tr/tr/kadin-kot-pantolonlar-l1119.html?v1=2419185",
    "https://www.zara.com/tr/tr/kadin-etekler-l1299.html?v1=2420454",
    "https://www.zara.com/tr/tr/kadin-body-l1057.html?v1=2420490",
    "https://www.zara.com/tr/tr/kadin-pantolonlar-shortlar-l1355.html?v1=2420480",
    "https://www.zara.com/tr/tr/kadin-deri-l1174.html?v1=2418883",
    "https://www.zara.com/tr/tr/kadin-esh-desenli-takimlar-l1061.html?v1=2420285",
    "https://www.zara.com/tr/tr/kadin-sweatshirtler-l1320.html?v1=2467841",
    "https://www.zara.com/tr/tr/kadin-ic-camasiri-l4021.html?v1=2419807",
]

MEN_URLS = [
    "https://www.zara.com/tr/tr/erkek-tum-urunler-l7465.html?v1=2443335",
]

RESET_SELENIUM_PROFILE = True
SCROLL_PAUSE_SEC = 1.8
SCROLL_MAX_NO_CHANGE = 10
MAX_ITEMS_PER_CATEGORY = None


def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SeleniumProfile")
    if RESET_SELENIUM_PROFILE and os.path.exists(profile_path):
        shutil.rmtree(profile_path, ignore_errors=True)
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def slug_to_category(url: str) -> str:
    path = urlparse(url).path
    slug = path.split("/")[-1].replace(".html", "")
    parts = [p for p in slug.split("-") if p]
    return parts[-1] if parts else slug


def parse_price_to_int(text: str):
    if not text:
        return None
    cleaned = text.replace("TL", "").replace("₺", "").replace("\xa0", " ").strip()
    cleaned = cleaned.replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.split(",")[0]
    else:
        cleaned = cleaned.replace(".", "")
    digits = re.sub(r"[^\d]", "", cleaned)
    return int(digits) if digits else None


def price_from_api(value):
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("current") or value.get("price")
    try:
        num = int(value)
    except Exception:
        try:
            num = int(float(value))
        except Exception:
            return None
    if num >= 1000:
        return num // 100
    return num


def _category_from_text(value: str) -> str:
    cleaned = value.replace("_", " ").replace("/", " ").strip()
    if re.search(r"\b\d+\s*ML\b", cleaned, flags=re.IGNORECASE):
        return "Parfüm"
    if cleaned.upper().endswith("OZ)"):
        return "Parfüm"
    parts = [p for p in re.split(r"[\s\-]+", cleaned) if p]
    if not parts:
        return cleaned
    if parts[-1].casefold() == "ayakkabısı":
        return "Ayakkabı"
    while parts and re.fullmatch(r"\d{1,3}", parts[-1]):
        parts.pop()
        if len(parts) <= 1:
            break
    if len(parts) >= 2 and parts[-2].upper() == "LIMITED" and parts[-1].upper() == "EDITION":
        if len(parts) >= 3:
            return parts[-3]
        return parts[0]
    if len(parts) >= 3 and parts[-3].upper() == "LIMITED" and parts[-2].upper() == "EDITION":
        return parts[-4] if len(parts) >= 4 else parts[0]
    if parts and parts[-1].upper() == "COLLECTION":
        if len(parts) >= 3:
            return parts[-3]
        return parts[0]
    return parts[-1]


def _find_key_recursive(obj, key: str, max_depth: int = 4):
    if max_depth < 0:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj.get(key)
        for value in obj.values():
            found = _find_key_recursive(value, key, max_depth - 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key_recursive(item, key, max_depth - 1)
            if found is not None:
                return found
    return None


def _pick_category_from_product(prod: dict, fallback: str) -> str:
    name = prod.get("name")
    if isinstance(name, str) and name.strip():
        name_cat = _category_from_text(name)
        if name_cat == "Parfüm":
            return name_cat
    family = prod.get("familyName")
    if not family:
        detail = prod.get("detail") if isinstance(prod.get("detail"), dict) else None
        if detail:
            family = detail.get("familyName")
    if not family:
        family = _find_key_recursive(prod, "familyName")
    if isinstance(family, str) and family.strip():
        return _category_from_text(family)
    if isinstance(name, str) and name.strip():
        return _category_from_text(name)
    return fallback


def extract_products_from_json(data, category: str):
    rows = []
    seen = set()

    def handle_product(prod: dict):
        pid = prod.get("id") or prod.get("reference") or prod.get("displayReference")
        if pid in seen:
            return
        name = (prod.get("name") or "").strip()
        cat = _pick_category_from_product(prod, category)
        price_int = price_from_api(prod.get("price"))
        if not name or price_int is None:
            return
        seen.add(pid)
        rows.append({
            "Category": cat,
            "Product Name": name,
            "Price": price_int,
        })

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("type") == "Product":
                handle_product(obj)
            for key, value in obj.items():
                if key == "commercialComponents" and isinstance(value, list):
                    for comp in value:
                        if isinstance(comp, dict) and comp.get("type") == "Product":
                            handle_product(comp)
                        else:
                            walk(comp)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return rows


def _category_products_url(category_url: str):
    parsed = urlparse(category_url)
    query = dict(qc.split("=", 1) for qc in parsed.query.split("&") if "=" in qc)
    v1 = query.get("v1")
    if v1 and v1.isdigit():
        return f"https://www.zara.com/tr/tr/category/{v1}/products?ajax=true"
    m = re.search(r"/category/(\d+)/", parsed.path)
    if m:
        category_id = m.group(1)
        return f"https://www.zara.com/tr/tr/category/{category_id}/products?ajax=true"
    return "https://www.zara.com/tr/tr/products?ajax=true"


def fetch_products_json(driver, category_url: str):
    products_url = _category_products_url(category_url)
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": category_url,
    }
    resp = session.get(products_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _count_products_in_json(data) -> int:
    if not data:
        return 0
    count = 0
    if isinstance(data, dict) and "productGroups" in data:
        for group in data.get("productGroups") or []:
            for elem in group.get("elements") or []:
                for comp in elem.get("commercialComponents") or []:
                    if isinstance(comp, dict) and comp.get("type") == "Product":
                        count += 1
    return count


def fetch_products_json_via_browser(driver, category_url: str):
    products_url = _category_products_url(category_url)
    current_url = driver.current_url
    try:
        driver.get(products_url)
        time.sleep(1.2)
        html = driver.page_source or ""
        return json.loads(html)
    except Exception:
        return None
    finally:
        try:
            driver.get(current_url)
        except Exception:
            pass

def _count_product_nodes(soup: BeautifulSoup) -> int:
    return len(
        soup.select(
            "li.product-grid-product, div.product-grid-product__info-wrapper"
        )
    )


def wait_for_products(driver, max_checks=10):
    for _ in range(max_checks):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if _count_product_nodes(soup) > 0:
            return soup
        time.sleep(1.5)
    return BeautifulSoup(driver.page_source, "html.parser")


def set_view_3(driver):
    script = r"""
    (function(){
      const selectors = [
        "[data-qa-id='grid-3']",
        "[data-qa-id='grid-03']",
        "[data-view='3']",
        "[aria-label*='3']",
        "button[data-qa-action*='grid']",
        "button"
      ];
      for (const sel of selectors) {
        const nodes = Array.from(document.querySelectorAll(sel));
        for (const node of nodes) {
          const text = (node.textContent || '').trim();
          if (text === "3" || text === "03" || text === "3x" || text === "3X") {
            node.click();
            return true;
          }
        }
      }
      return false;
    })();
    """
    try:
        driver.execute_script(script)
        time.sleep(0.8)
    except Exception:
        pass


def scroll_and_collect_soup(driver, pause_sec=SCROLL_PAUSE_SEC, max_no_change=SCROLL_MAX_NO_CHANGE):
    last_count = 0
    no_change = 0
    soup = None
    while True:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            break
        time.sleep(pause_sec)
        html = driver.page_source or ""
        soup = BeautifulSoup(html, "html.parser")
        count = _count_product_nodes(soup)
        if count == last_count:
            no_change += 1
        else:
            no_change = 0
            last_count = count
        if no_change >= max_no_change:
            break
    final_html = driver.page_source or ""
    return soup or BeautifulSoup(final_html, "html.parser")


def extract_products(soup: BeautifulSoup, category: str):
    rows = []
    items = soup.select("li.product-grid-product")
    if not items:
        items = soup.select("div.product-grid-product__info-wrapper")
    for item in items:
        name_elem = item.select_one(
            "[data-qa-qualifier='product-name'], .product-grid-product-info__name, a.product-link[title], a.product-link[aria-label], a.product-link h3, h3"
        )
        name = ""
        if name_elem:
            name = (name_elem.get("title") or name_elem.get("aria-label") or name_elem.get_text(strip=True)).strip()

        price_elem = item.select_one("span.money-amount__main")
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        price_int = parse_price_to_int(price_text)

        if not name or price_int is None:
            continue

        cat = _category_from_text(name) if name else category
        rows.append({
            "Category": cat,
            "Product Name": name,
            "Price": price_int,
        })
    return rows


def dedupe_rows(rows):
    seen = set()
    result = []
    for row in rows:
        key = (row.get("Category"), row.get("Product Name"), row.get("Price"))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def limit_rows(rows, max_items):
    if max_items is None:
        return rows
    return rows[:max_items]


def main():
    driver = setup_driver()
    all_rows = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    save_dir = os.path.join(project_root, "Datas", "ClothingStores", "Zara")
    os.makedirs(save_dir, exist_ok=True)
    today_date = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(save_dir, f"zara_{today_date}.csv")
    file_exists = os.path.exists(filename)
    try:
        with open(filename, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["Category", "Product Name", "Price"])
            if not file_exists:
                writer.writeheader()
                file_exists = True

            for url in MEN_URLS + WOMEN_URLS:
                category = slug_to_category(url)
                print(f"Loading {category}: {url}")
                driver.get(url)

                soup = wait_for_products(driver)
                set_view_3(driver)
                if not soup.select("li.product-grid-product"):
                    print("No products detected. If a CAPTCHA or bot check appears, solve it in Chrome.")
                    input("After products are visible, press ENTER here...")
                    soup = wait_for_products(driver)
                    set_view_3(driver)

                data = fetch_products_json(driver, url)
                if data and _count_products_in_json(data) == 0:
                    data = fetch_products_json_via_browser(driver, url) or data
                rows_json = extract_products_from_json(
                    data,
                    category,
                ) if data else []

                soup = scroll_and_collect_soup(driver)
                rows_html = extract_products(soup, category)

                rows = dedupe_rows(rows_json + rows_html)
                rows = limit_rows(rows, MAX_ITEMS_PER_CATEGORY)
                print(f"{category} -> {len(rows)} products")

                for row in rows:
                    writer.writerow(row)
                    f.flush()
                    all_rows.append(row)
    finally:
        driver.quit()

    if not all_rows:
        print("No data scraped.")
        return

    print(f"Saved {len(all_rows)} products to {filename}")


if __name__ == "__main__":
    main()
