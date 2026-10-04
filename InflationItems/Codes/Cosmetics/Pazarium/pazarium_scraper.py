import requests
import pandas as pd
import time
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
BASE_URL = "https://www.pazarium.com.tr"
# Pazarium has a dedicated Cosmetics category: /kozmetik (around 950+ products).
CATEGORY_URL = f"{BASE_URL}/kozmetik"

MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2  # seconds

# Output directory: InflationItems/Datas/Cosmetics/Pazarium
current_script_path = os.path.abspath(__file__)
base_project_dir = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(current_script_path)
        )
    )
)
data_dir = os.path.join(base_project_dir, "Datas", "Cosmetics", "Pazarium")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(
    data_dir, f"pazarium_{datetime.now().strftime('%Y-%m-%d')}.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}

session = requests.Session()
session.headers.update(HEADERS)

# -----------------------------------------------------------------------------
# REGEX / HELPERS
# -----------------------------------------------------------------------------
# Price format: "1.234,56 TL" or "99,90 TL"
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL")

# Pattern to capture total items count from page text
TOTAL_RE = re.compile(r"Toplam\s+(\d[\d.,]*)\s+ürün", re.IGNORECASE)

# Non-product single-segment paths to filter out
NON_PRODUCT_PATHS = {
    "", "anasayfa", "sepet", "uye-girisi-sayfasi", "uye-alisveris-listesi",
    "uye-kayit", "uye-sifre-hatirlat", "siparis-takip",
    "kozmetik", "giyim", "erkek-giyim", "tesettur-giyim", "pijama-takimi",
    "ic-giyim", "basortusu", "pantolon-etek", "tesettur-dis-giyim",
    "indirim-tesettur-giyim", "cok-satanlar", "yeni-sezon-tesettur-giyim",
}


def parse_price(text: str) -> float | None:
    """'1.234,56 TL' -> 1234.56. Returns None if no price pattern found."""
    m = PRICE_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def fetch_page(page_num: int) -> str | None:
    """Download HTML for the given page number with retry support."""
    url = f"{CATEGORY_URL}?pg={page_num}"
    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * attempt)
    print(f"[ERROR] Failed to fetch page {page_num} ({RETRY_COUNT} attempts): {last_err}")
    return None


# -----------------------------------------------------------------------------
# PARSING
# -----------------------------------------------------------------------------
def parse_products(html: str, page_num: int) -> list[dict]:
    """Parse product cards from HTML content."""
    soup = BeautifulSoup(html, "lxml")
    products: list[dict] = []
    seen_urls: set[str] = set()

    for img in soup.find_all("img"):
        # 1) Locate enclosing <a> tag -> product URL
        parent_a = img.find_parent("a")
        if not parent_a:
            continue

        href = parent_a.get("href", "") or ""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        full_url = urljoin(BASE_URL, href)
        if not full_url.startswith(BASE_URL):
            continue

        # Check path — product URLs are single segment
        path = full_url[len(BASE_URL):].lstrip("/")
        path = path.split("?", 1)[0].split("#", 1)[0]
        if "/" in path:  # Internal paths like /Data/..., /srv/... are not products
            continue
        if path in NON_PRODUCT_PATHS:
            continue

        if full_url in seen_urls:
            continue

        # 2) Find enclosing container containing price
        container = parent_a
        price = None
        for _ in range(5):
            if container is None or container.name in ("body", "html"):
                break
            price = parse_price(container.get_text(" ", strip=True))
            if price is not None:
                break
            container = container.parent

        if price is None:
            continue

        # 3) Stock check: skip sold out products
        if container.select_one(".out-of-stock") is not None:
            continue
        if "Tükendi" in container.get_text(" ", strip=True):
            continue

        # 4) Product name and subcategory
        alt = (img.get("alt") or "").strip()
        name = alt
        subcategory = ""
        if " - " in alt:
            parts = alt.rsplit(" - ", 1)
            name = parts[0].strip()
            subcategory = parts[1].strip()

        if not name:
            link_text = parent_a.get_text(" ", strip=True)
            if link_text and not PRICE_RE.search(link_text):
                name = link_text

        products.append({
            "name": name,
            "subcategory": subcategory,
            "price": price,
            "url": full_url,
        })
        seen_urls.add(full_url)

    return products


def get_total_count_and_page1(html: str):
    """Extract total product count and page 1 items."""
    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text(" ", strip=True)

    m = TOTAL_RE.search(page_text)
    total_products = None
    if m:
        total_products = int(m.group(1).replace(".", "").replace(",", ""))

    page1_products = parse_products(html, 1)
    per_page = len(page1_products) if page1_products else 0
    return total_products, per_page, page1_products


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("=" * 70)
    print(f"Pazarium Cosmetics Scraper  |  {today_str}")
    print(f"Target URL: {CATEGORY_URL}")
    print(f"Output File: {OUTPUT_FILE}")
    print("=" * 70)

    # --- Step 1: Page 1 and total count ---
    print("[1/3] Downloading page 1 to determine total product count...")
    html1 = fetch_page(1)
    if not html1:
        print("[FATAL] Could not retrieve page 1, exiting.")
        return

    total_products, per_page, page1_products = get_total_count_and_page1(html1)
    print(f"   -> Items per page: {per_page}")
    if total_products is not None:
        print(f"   -> Total items reported by website: {total_products}")
    else:
        print("   -> Total count not found, will scrape sequentially until empty.")

    all_products: list[dict] = list(page1_products)
    seen_urls: set[str] = {p["url"] for p in all_products}

    # --- Step 2: Remaining pages ---
    if total_products is not None and per_page > 0:
        total_pages = (total_products + per_page - 1) // per_page
        print(f"[2/3] Calculated total pages: {total_pages}")
        remaining = list(range(2, total_pages + 1))

        if remaining:
            print(f"   -> Downloading {len(remaining)} pages in parallel (workers={MAX_WORKERS})...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_page = {
                    executor.submit(fetch_page, p): p for p in remaining
                }
                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    html = future.result()
                    if not html:
                        continue
                    new_products = parse_products(html, page)
                    added = 0
                    for prod in new_products:
                        if prod["url"] not in seen_urls:
                            all_products.append(prod)
                            seen_urls.add(prod["url"])
                            added += 1
                    print(f"   [Page {page:>3}] {len(new_products)} products found, {added} new")
    else:
        print("[2/3] Sequential pagination fallback...")
        page = 2
        empty_streak = 0
        while empty_streak < 2:
            html = fetch_page(page)
            if not html:
                empty_streak += 1
                page += 1
                continue
            new_products = parse_products(html, page)
            added = 0
            for prod in new_products:
                if prod["url"] not in seen_urls:
                    all_products.append(prod)
                    seen_urls.add(prod["url"])
                    added += 1
            print(f"   [Page {page:>3}] {len(new_products)} products found, {added} new")
            empty_streak = empty_streak + 1 if added == 0 else 0
            page += 1

    # --- Step 3: Write to CSV ---
    if not all_products:
        print("[FATAL] No products extracted. Page template might have changed.")
        return

    df = pd.DataFrame(all_products)

    # Standard column order: product_name, price, subcategory
    df = df.rename(columns={"name": "product_name"})
    df = df[["product_name", "price", "subcategory"]]
    df = df.sort_values(["subcategory", "product_name"]).reset_index(drop=True)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    elapsed = time.time() - t0
    print("=" * 70)
    print(f"[3/3] COMPLETED")
    print(f"   Total products: {len(df)}")
    print(f"   Output file: {OUTPUT_FILE}")
    print(f"   Elapsed time: {elapsed:.1f} s")
    print("=" * 70)


if __name__ == "__main__":
    main()