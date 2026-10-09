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
# Script lives at: InflationItems/Codes/ConstructionSuppliesMarkets/SanatYapiOnline/
# So go up 4 levels to reach the project root (same as mudo scraper)
base_project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))
data_dir = os.path.join(base_project_dir, "Datas", "ConstructionSuppliesMarkets", "SanatYapiOnline")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(data_dir, f"sanatyapionline_{datetime.now().strftime('%Y-%m-%d')}.csv")

# ==========================================
# 2. CONFIGURATION
# ==========================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Top-level categories extracted from the site navigation
CATEGORIES = {
    "Bianca Stella":                    "https://www.sanatyapionline.com/kategori/bianca-stella",
    "Boya ve Aksesuarları":             "https://www.sanatyapionline.com/kategori/boya-ve-aksesuarlari",
    "İnşaat Ve İzolasyon":              "https://www.sanatyapionline.com/kategori/insaat-ve-izolasyon",
    "Elektrik":                         "https://www.sanatyapionline.com/kategori/elektrik-aydinlatma",
    "Banyo":                            "https://www.sanatyapionline.com/kategori/banyo",
    "Bahçe Aletleri":                   "https://www.sanatyapionline.com/kategori/bahce-aletleri",
    "El Aletleri":                      "https://www.sanatyapionline.com/kategori/el-aletleri",
    "Hırdavat":                         "https://www.sanatyapionline.com/kategori/hirdavat",
    "Hobi Malzemeleri":                 "https://www.sanatyapionline.com/kategori/hobi-malzemeleri",
    "Kamp Malzemeleri":                 "https://www.sanatyapionline.com/kategori/kamp-malzemeleri",
    "Kaynak Malzemeleri":               "https://www.sanatyapionline.com/kategori/kaynak-malzemeleri",
    "Oto Bakım ve Tamir Ekipmanları":   "https://www.sanatyapionline.com/kategori/oto-bakim-ve-tamir-ekipmanlari",
}

MAX_WORKERS     = 4    # Categories scraped in parallel (keep ≤5 to stay polite)
REQUEST_TIMEOUT = 15   # Seconds before giving up on a request
DELAY_BETWEEN   = 0.3  # Seconds between retries on failure (no longer used between pages)
MAX_PROBE_PAGES = 150  # Upper bound on pages per category (fallback only)

# ==========================================
# 3. CSS SELECTORS
# ==========================================
DIAGNOSTIC_MODE = False   # Set True to print first card's raw HTML for debugging

# Primary selectors updated based on the new site structure
SELECTOR_CARD          = ".showcase-page-product"       # Each product card wrapper
SELECTOR_NAME          = ".showcase-title a"            # Product name link
SELECTOR_PRICE_CURRENT = ".showcase-price-new"          # Sale / current price
SELECTOR_PRICE_RETAIL  = ".showcase-price-old"          # Original (crossed-out) price

# Fallback selectors for older templates (combined your previous primary and alt selectors)
SELECTOR_CARD_ALT          = "ul.productList > li, .product-item, .showcase"
SELECTOR_NAME_ALT          = "a.productName, .product-item__name, .urunAdi, h3.name a"
SELECTOR_PRICE_CURRENT_ALT = "span.productNewPrice, .newPrice, .indirimli-fiyat, [class*='new-price']"
SELECTOR_PRICE_RETAIL_ALT  = "span.productPrice, .oldPrice, .eski-fiyat, [class*='old-price']"


# ==========================================
# 4. HELPERS
# ==========================================
def make_session() -> requests.Session:
    """Creates a reusable session with shared headers."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_page(session: requests.Session, target_url: str, retries: int = 3, is_ajax: bool = False):
    """Fetches a URL. Retries if rate-limited or timed out.

    Args:
        is_ajax: Set True only for AJAX/pagination requests. Regular category
                 page loads must NOT send X-Requested-With or the server returns 404.
    """
    for attempt in range(1, retries + 1):
        try:
            # Only send the XHR header for AJAX pagination endpoints, NOT for the
            # first HTML page load — sending it there causes a 404 on this site.
            extra_headers = {"X-Requested-With": "XMLHttpRequest"} if is_ajax else {}
            resp = session.get(target_url, headers=extra_headers, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 429:
                print(f"  ! [429 Too Many Requests]. Sleeping for 5s...")
                time.sleep(5)
                continue

            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")

        except requests.exceptions.RequestException as e:
            print(f"  ! Error fetching (Attempt {attempt}/{retries}): {e}")
            time.sleep(2)

    return None


def _select_first(soup: BeautifulSoup, *selectors: str):
    """Tries each CSS selector in order and returns the first match (or None)."""
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el
    return None


def _select_all(soup: BeautifulSoup, *selectors: str) -> list:
    """Tries each CSS selector in order and returns the first non-empty result list."""
    for sel in selectors:
        results = soup.select(sel)
        if results:
            return results
    return []


def parse_cards(soup: BeautifulSoup, category_name: str) -> list[dict]:
    """Extracts product dicts from a parsed page."""
    cards = _select_all(soup, SELECTOR_CARD, SELECTOR_CARD_ALT)
    if not cards:
        return []

    if DIAGNOSTIC_MODE:
        print("\n========== DIAGNOSTIC: first product card HTML ==========")
        print(cards[0].prettify())
        print("=========================================================\n")

    results = []
    for card in cards:
        try:
            # --- Name ---
            name_el = _select_first(card, SELECTOR_NAME, SELECTOR_NAME_ALT)
            name    = name_el.get_text(strip=True) if name_el else "N/A"

            # --- Current (sale) price ---
            cur_el = _select_first(card, SELECTOR_PRICE_CURRENT, SELECTOR_PRICE_CURRENT_ALT)
            if cur_el:
                current_price = cur_el.get_text(strip=True)
            else:
                # Last-resort: grab text that looks like a TL price
                current_price = _extract_tl_price(card, prefer="first")

            # --- Original (retail) price ---
            ret_el = _select_first(card, SELECTOR_PRICE_RETAIL, SELECTOR_PRICE_RETAIL_ALT)
            if ret_el:
                original_price = ret_el.get_text(strip=True)
            else:
                # If no separate original price found, it equals the current price
                original_price = current_price

            # Skip cards with no useful data (e.g. banners / spacers)
            if name == "N/A" and current_price == "N/A":
                continue

            results.append({
                "Category":       category_name,
                "Name":           name,
                "Current Price":  current_price,
                "Original Price": original_price,
            })
        except Exception as e:
            print(f"  ! Error parsing a card: {e}")

    return results


def _extract_tl_price(card: BeautifulSoup, prefer: str = "first") -> str:
    """
    Fallback: scans all text nodes for a pattern like '1.234,56 TL'.
    Returns the first or last match depending on `prefer`.
    """
    import re
    pattern = re.compile(r"[\d.,]+ TL")
    matches = pattern.findall(card.get_text(" "))
    if not matches:
        return "N/A"
    return matches[0] if prefer == "first" else matches[-1]


import math

# ==========================================
# 5. SCRAPING LOGIC
# ==========================================
PRODUCTS_PER_PAGE = 30  # Site shows 30 products per page

def page_url(base_url: str, page: int) -> str:
    """
    Builds the URL for a given page number.
    Confirmed pagination pattern: ?tp=2, ?tp=3, ... directly on the category URL.
    Page 1 is the base URL itself (no param needed).
    """
    if page == 1:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}tp={page}"


def parse_total_products(soup: BeautifulSoup) -> int | None:
    """
    Extracts the total product count from the 'Toplam N ürün' text shown on
    category pages. Returns None if the element isn't found.
    """
    import re
    # The site renders something like: <span>Toplam 77 ürün</span>
    el = soup.find(string=re.compile(r"Toplam\s+\d+\s+ürün", re.I))
    if el:
        m = re.search(r"\d+", el)
        if m:
            return int(m.group())
    # Fallback: search inside any tag text
    for tag in soup.find_all(string=re.compile(r"\d+\s*ürün", re.I)):
        m = re.search(r"(\d+)\s*ürün", tag, re.I)
        if m:
            return int(m.group(1))
    return None


def scrape_category(category_name: str, base_url: str) -> list[dict]:
    print(f"\n[{category_name}] Fetching page 1...")
    session = make_session()

    # ── Step 1: fetch page 1 to learn total product count ──────────────────
    soup1 = fetch_page(session, page_url(base_url, 1), is_ajax=False)
    if not soup1:
        print(f"  ! [{category_name}] Failed to fetch page 1.")
        return []

    products_p1 = parse_cards(soup1, category_name)
    if not products_p1:
        print(f"  ! [{category_name}] No products on page 1.")
        return []

    total = parse_total_products(soup1)
    if total:
        total_pages = math.ceil(total / PRODUCTS_PER_PAGE)
        print(f"  -> [{category_name}] {total} products across {total_pages} pages — fetching in parallel...")
    else:
        # Couldn't read total — fall back to a safe upper bound with anti-loop guard
        total_pages = MAX_PROBE_PAGES
        print(f"  -> [{category_name}] Total count not found, will probe up to {total_pages} pages.")

    all_products = list(products_p1)

    if total_pages <= 1:
        print(f"[{category_name}] Total: {len(all_products)} products")
        return all_products

    # ── Step 2: fetch all remaining pages concurrently ─────────────────────
    def fetch_one(page: int):
        soup = fetch_page(session, page_url(base_url, page), is_ajax=False)
        if not soup:
            return page, []
        return page, parse_cards(soup, category_name)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_one, p): p for p in range(2, total_pages + 1)}
        for future in as_completed(futures):
            page, products = future.result()
            if products:
                # Anti-loop guard: skip pages that duplicate page 1's first product
                if products[0]["Name"] == products_p1[0]["Name"]:
                    print(f"  -> [{category_name}] Page {page} is a repeat, skipping.")
                    continue
                all_products.extend(products)
                print(f"  -> [{category_name}] Page {page}: {len(products)} products")
            else:
                print(f"  -> [{category_name}] Page {page}: empty, skipping.")

    print(f"[{category_name}] Total: {len(all_products)} products")
    return all_products


# ==========================================
# 6. MAIN
# ==========================================
def main():
    print(f"SanatYapiOnline Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Running {MAX_WORKERS} categories in parallel...\n")

    all_products: list[dict] = []
    start = time.time()

    # Scrape all categories in parallel — each gets its own session and page loop
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(scrape_category, cat_name, url): cat_name
            for cat_name, url in CATEGORIES.items()
        }
        for future in as_completed(futures):
            cat_name = futures[future]
            try:
                products = future.result()
                all_products.extend(products)
            except Exception as e:
                print(f"  !! [{cat_name}] crashed: {e}")

    elapsed = time.time() - start
    print(f"\nFinished in {elapsed:.1f}s")

    if not all_products:
        print("\n❌ No products scraped.")
        print("   Tips:")
        print("   1. Set DIAGNOSTIC_MODE = True and re-run to inspect raw card HTML.")
        print("   2. Check if the site changed its HTML structure and update the selectors.")
        print("   3. If content looks empty/skeletal, the listing may be JS-rendered.")
        print("      Consider switching to Playwright:")
        print("      pip install playwright && playwright install chromium")
        return

    df = pd.DataFrame(all_products)[["Category", "Name", "Current Price", "Original Price"]]
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Saved {len(all_products)} products → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()