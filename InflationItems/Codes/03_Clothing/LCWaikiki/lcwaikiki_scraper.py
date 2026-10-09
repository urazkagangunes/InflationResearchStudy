import csv
import time
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


# ── Configuration ──────────────────────────────────────────────────────────────

SEARCH_TARGETS = {
    "erkek": "https://www.lcw.com/arama?q=erkek",
    "kadin": "https://www.lcw.com/arama?q=kadin",
}

TARGET_COUNT   = 3000    # stop after this many unique products per category
OUTPUT_FILE    = f"LCWaikiki_{datetime.now().strftime("%Y-%m-%d")}.csv"

PAGE_LOAD_WAIT = 12      # seconds to wait for first product card
SCROLL_PAUSE   = 2.5     # seconds between scroll steps
MAX_SCROLLS    = 300     # absolute scroll safety cap
MAX_PAGES      = 100     # max pagination pages to try
REQUEST_DELAY  = 1.5     # seconds between page/scroll requests

# Pagination param candidates to probe (tried in order)
PAGINATION_PARAMS = ["pg", "page", "sayfa", "p"]


# ── Browser ────────────────────────────────────────────────────────────────────

def build_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_price(raw: str) -> str:
    """'1.299,99 TL' -> '1299.99'"""
    raw = re.sub(r'[^\d,.]', '', raw.strip())
    raw = raw.replace('.', '').replace(',', '.')
    try:
        float(raw)
        return raw
    except ValueError:
        return raw


def dismiss_overlays(driver: webdriver.Chrome) -> None:
    for sel in [
        "button#onetrust-accept-btn-handler",
        "button.cookie-accept",
        "button[data-testid='modal-close']",
        "button.close",
        "div.modal-close",
    ]:
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click()
            time.sleep(0.4)
        except Exception:
            pass


def wait_for_cards(driver: webdriver.Chrome) -> bool:
    """Wait until at least one product card is present. Returns True/False."""
    try:
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.product-card-info__content")
            )
        )
        return True
    except Exception:
        return False


def count_cards(driver: webdriver.Chrome) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, "div.product-card-info__content"))


def extract_products(page_source: str, category: str) -> list[dict]:
    soup = BeautifulSoup(page_source, "html.parser")
    products = []
    for card in soup.select("div.product-card-info__content"):
        brand_el = card.select_one(".product-brand")
        desc_el  = card.select_one(".product-description")
        parts = []
        if brand_el and brand_el.get_text(strip=True):
            parts.append(brand_el.get_text(strip=True))
        if desc_el and desc_el.get_text(strip=True):
            parts.append(desc_el.get_text(strip=True))
        name = " - ".join(parts) if parts else "N/A"

        price_raw = ""
        basket_el  = card.select_one(".price-in-cart")
        current_el = card.select_one(".current-price")
        if basket_el and basket_el.get_text(strip=True):
            price_raw = basket_el.get_text(strip=True)
        elif current_el:
            price_raw = current_el.get_text(strip=True)

        price = parse_price(price_raw) if price_raw else ""
        if name != "N/A" or price:
            products.append({"name": name, "price_tl": price})
    return products


# ── Strategy 1: URL Pagination ─────────────────────────────────────────────────

def detect_pagination_param(driver: webdriver.Chrome, base_url: str) -> str | None:
    """
    Probe ?pg=2, ?page=2, etc.
    A param 'works' if page 2 loads different cards than page 1.
    Returns the working param name, or None.
    """
    print("  Probing pagination params...", end=" ")

    # Get fingerprint of page 1 (first 3 product names)
    driver.get(base_url)
    if not wait_for_cards(driver):
        return None
    dismiss_overlays(driver)
    soup1 = BeautifulSoup(driver.page_source, "html.parser")
    cards1 = [c.get_text(strip=True)[:40]
              for c in soup1.select("div.product-card-info__content")[:5]]

    for param in PAGINATION_PARAMS:
        url_p2 = f"{base_url}&{param}=2"
        driver.get(url_p2)
        has_cards = wait_for_cards(driver)
        if not has_cards:
            continue
        soup2 = BeautifulSoup(driver.page_source, "html.parser")
        cards2 = [c.get_text(strip=True)[:40]
                  for c in soup2.select("div.product-card-info__content")[:5]]
        if cards2 and cards2 != cards1:
            print(f"found '?{param}='")
            return param

    print("none found — will use scroll fallback")
    return None


def scrape_via_pagination(driver: webdriver.Chrome, base_url: str,
                          param: str, category: str) -> list[dict]:
    """Iterate pages via ?{param}=N until TARGET_COUNT or no new products."""
    all_products: list[dict] = []
    seen_keys: set[tuple] = set()

    for page_num in range(1, MAX_PAGES + 1):
        url = f"{base_url}&{param}={page_num}" if page_num > 1 else base_url
        print(f"    Page {page_num:>3}: {url}", end="  ")
        driver.get(url)

        if not wait_for_cards(driver):
            print("no cards — stopping")
            break

        # Scroll a bit to trigger lazy images (but not full infinite scroll)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        page_products = extract_products(driver.page_source, category)
        new_count = 0
        for p in page_products:
            key = (p["name"], p["price_tl"])
            if key not in seen_keys:
                seen_keys.add(key)
                all_products.append(p)
                new_count += 1

        print(f"+{new_count} new  (total: {len(all_products)})")

        if new_count == 0:
            print("    No new products on this page — pagination exhausted")
            break
        if len(all_products) >= TARGET_COUNT:
            print(f"    Target of {TARGET_COUNT} reached")
            break

        time.sleep(REQUEST_DELAY)

    return all_products


# ── Strategy 2: Infinite Scroll Fallback ──────────────────────────────────────

def scrape_via_scroll(driver: webdriver.Chrome, base_url: str,
                      category: str) -> list[dict]:
    """Full infinite-scroll on a single page until TARGET_COUNT or stable."""
    print(f"  Scrolling: {base_url}")
    driver.get(base_url)

    if not wait_for_cards(driver):
        print("  No cards found after page load — skipping")
        return []

    dismiss_overlays(driver)

    prev_count = 0
    stable_rounds = 0

    for i in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        current_count = count_cards(driver)
        print(f"    scroll {i+1:>3} | cards: {current_count}", end="\r")

        if current_count == prev_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0
        prev_count = current_count

        # Early exit if we have enough DOM cards
        if current_count >= TARGET_COUNT:
            print(f"\n    DOM has {current_count} cards — target reached, stopping scroll")
            break

    print()
    products = extract_products(driver.page_source, category)
    print(f"  Extracted {len(products)} products from scroll page")
    return products


# ── Per-category orchestration ─────────────────────────────────────────────────

def scrape_category(driver: webdriver.Chrome, category: str, base_url: str) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"  Category : {category.upper()}")
    print(f"  URL      : {base_url}")
    print(f"  Target   : {TARGET_COUNT} products")
    print(f"{'='*60}")

    # First load + cookie dismissal
    driver.get(base_url)
    wait_for_cards(driver)
    dismiss_overlays(driver)

    param = detect_pagination_param(driver, base_url)

    if param:
        products = scrape_via_pagination(driver, base_url, param, category)
    else:
        products = scrape_via_scroll(driver, base_url, category)

    # Deduplicate within category
    seen: set[tuple] = set()
    unique = []
    for p in products:
        key = (p["name"], p["price_tl"])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"  => {len(unique)} unique products for '{category}' "
          f"(from {len(products)} raw)")
    return unique[:TARGET_COUNT]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    all_products: list[dict] = []
    driver = build_driver()

    try:
        for category, url in SEARCH_TARGETS.items():
            products = scrape_category(driver, category, url)
            all_products.extend(products)
    finally:
        driver.quit()


    # project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) 
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    output_path = os.path.join(
        project_root,
        "InflationItems", "Datas", "ClothingStores", "LCWaikiki",
        OUTPUT_FILE
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "price_tl"])
        writer.writeheader()
        writer.writerows(all_products)

    total = len(all_products)


if __name__ == "__main__":
    main()