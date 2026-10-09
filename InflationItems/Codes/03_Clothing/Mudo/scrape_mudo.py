import os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. DIRECTORY SETUP
# ==========================================
current_script_path = os.path.abspath(__file__)
base_project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))
data_dir = os.path.join(base_project_dir, "Datas", "ClothingStores", "Mudo")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(data_dir, f"mudo_clothing_{datetime.now().strftime('%Y-%m-%d')}.csv")

# ==========================================
# 2. CONFIGURATION
# ==========================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

CATEGORIES = {
    "Kadin Giyim": "https://www.mudo.com.tr/kadin-giyim/",
    "Erkek Giyim":  "https://www.mudo.com.tr/erkek-giyim/"
}

MAX_WORKERS     = 5    # Concurrent page fetches per category
REQUEST_TIMEOUT = 15   # Seconds before giving up on a request
DELAY_BETWEEN   = 0.5  # Seconds between requests
MAX_PROBE_PAGES = 100  # Upper bound for binary page search (1772 items / 24 per page ≈ 74 pages)

# ==========================================
# ⚙️  CSS SELECTORS
# ==========================================
DIAGNOSTIC_MODE  = False   # Set True to print first card's raw HTML

SELECTOR_CARD          = ".product-item"
SELECTOR_NAME          = "a.product-item__name"
SELECTOR_PRICE_CURRENT = ".product-item__price pz-price:not(.-retail)"  # sale / current price
SELECTOR_PRICE_RETAIL  = ".product-item__price pz-price.-retail"        # original (crossed-out) price
SELECTOR_DISCOUNT      = ".product-item__bottom > span"                  # e.g. "%53"


# ==========================================
# 3. HELPERS
# ==========================================
def make_session() -> requests.Session:
    """Creates a reusable session with shared headers."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_page(session: requests.Session, url: str, page: int):
    """Fetches a single paginated URL. Returns (page, soup) or (page, None) on error."""
    paged_url = f"{url}?page={page}"
    try:
        resp = session.get(paged_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return page, BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"  ! Error fetching page {page} ({paged_url}): {e}")
        return page, None


def parse_cards(soup: BeautifulSoup, category_name: str) -> list[dict]:
    """Extracts product dicts from a parsed page."""
    cards = soup.select(SELECTOR_CARD)
    if not cards:
        return []

    if DIAGNOSTIC_MODE:
        print("\n========== DIAGNOSTIC: first product card HTML ==========")
        print(cards[0].prettify())
        print("=========================================================\n")

    results = []
    for card in cards:
        try:
            # Name
            name_el = card.select_one(SELECTOR_NAME)
            name    = name_el.text.strip() if name_el else "N/A"

            # Current (sale) price — fall back to data-price attribute on the card
            price_el = card.select_one(SELECTOR_PRICE_CURRENT)
            if price_el:
                price = price_el.text.strip()
            else:
                raw = card.get("data-price", "N/A")
                price = f"{raw} TL" if raw != "N/A" else "N/A"

            # Original retail price — for non-discounted items, same as current price
            retail_el    = card.select_one(SELECTOR_PRICE_RETAIL)
            retail_price = retail_el.text.strip() if retail_el else price

            # Discount badge e.g. "%53"
            discount_el = card.select_one(SELECTOR_DISCOUNT)
            discount    = discount_el.text.strip() if discount_el else ""

            results.append({
                "Category":       category_name,
                "Name":           name,
                "Price":          price,
                "Original Price": retail_price,
                "Discount":       discount,
            })
        except Exception as e:
            print(f"  ! Error parsing a card: {e}")

    return results


# ==========================================
# 4. SCRAPING LOGIC
# ==========================================
def probe_last_page(session: requests.Session, base_url: str) -> int:
    """
    Probes to find the last valid page number using binary search (fast).
    Falls back to sequential scan up to MAX_PROBE_PAGES if the site
    doesn't signal an empty page clearly.
    """
    lo, hi = 1, MAX_PROBE_PAGES

    # Quick check: does page 2 even exist?
    _, soup = fetch_page(session, base_url, 2)
    if soup is None or not soup.select(SELECTOR_CARD):
        return 1  # Single-page category

    while lo < hi:
        mid = (lo + hi + 1) // 2
        _, soup = fetch_page(session, base_url, mid)
        if soup and soup.select(SELECTOR_CARD):
            lo = mid
        else:
            hi = mid - 1
        time.sleep(DELAY_BETWEEN)

    return lo


def scrape_category(category_name: str, base_url: str) -> list[dict]:
    print(f"\n[{category_name}] Detecting page count...")
    session      = make_session()
    last_page    = probe_last_page(session, base_url)
    print(f"[{category_name}] Found {last_page} page(s). Fetching concurrently...")

    pages_to_fetch = list(range(1, last_page + 1))
    page_soups     = {}  # page_num -> soup

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_page, session, base_url, p): p for p in pages_to_fetch}
        for future in as_completed(futures):
            page_num, soup = future.result()
            if soup:
                page_soups[page_num] = soup

    all_products = []
    for page_num in sorted(page_soups):
        products = parse_cards(page_soups[page_num], category_name)
        all_products.extend(products)
        print(f"  -> Page {page_num}: {len(products)} products")

    print(f"[{category_name}] Total: {len(all_products)} products")
    return all_products


# ==========================================
# 5. MAIN
# ==========================================
def main():
    all_products = []

    # Scrape categories sequentially (pages within each are concurrent)
    for cat_name, url in CATEGORIES.items():
        all_products.extend(scrape_category(cat_name, url))

    if not all_products:
        print("\n❌ No products scraped.")
        print("   Tips:")
        print("   1. Set DIAGNOSTIC_MODE = True and re-run to inspect the raw HTML.")
        print("   2. If the page content looks empty/skeletal, the site may be")
        print("      JavaScript-rendered — consider switching to Playwright:")
        print("      pip install playwright && playwright install chromium")
        return

    df = pd.DataFrame(all_products)[["Category", "Name", "Price", "Original Price", "Discount"]]  # no Date column
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n✅ Saved {len(all_products)} products → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
