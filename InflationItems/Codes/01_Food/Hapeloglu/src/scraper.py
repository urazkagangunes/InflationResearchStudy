"""
Scraper - core engine.
Loops categories, handles pagination, extracts product data.
"""

import logging
import threading

import pandas as pd

from src.config import BASE_URL, PRODUCTS_PER_PAGE, CATEGORIES
from src.utils import create_session, fetch_page, parse_price


logger = logging.getLogger(__name__)


def extract_products_from_page(soup, category: str) -> list[dict]:
    """Parse all .productItem cards from a single page."""
    products = []

    for item in soup.select(".productItem"):
        name_el = item.select_one(".productName")
        price_el = item.select_one(".discountPriceSpan")
        regular_el = item.select_one(".regularPriceSpan")
        link_el = item.select_one("a.detailLink")
        img_el = item.select_one(".productImage img")

        name = name_el.get_text(strip=True) if name_el else None
        current_price = parse_price(price_el.get_text(strip=True)) if price_el else None
        regular_price = parse_price(regular_el.get_text(strip=True)) if regular_el else None
        product_id = link_el.get("data-id") if link_el else None
        product_url = link_el.get("href", "") if link_el else ""
        image_url = (img_el.get("data-original") or img_el.get("src")) if img_el else None
        out_of_stock = bool(item.select_one(".outOfStock, .tukendi, [class*='tukendi']"))

        if name and product_id:
            is_discounted = (
                regular_price is not None
                and current_price is not None
                and regular_price > current_price
            )
            products.append({
                "product_id": product_id,
                "name": name,
                "current_price": current_price,
                "regular_price": regular_price,
                "is_discounted": is_discounted,
                "discount_pct": (
                    round((1 - current_price / regular_price) * 100, 1)
                    if is_discounted else None
                ),
                "category": category,
                "product_url": f"{BASE_URL}{product_url}" if product_url else None,
                "image_url": image_url,
                "in_stock": not out_of_stock,
            })

    return products


def scrape_category(category_name: str, category_slug: str, session) -> list[dict]:
    """
    Scrape ALL products from one category (with pagination).

    Pagination strategy:
        The "X Ürün" total count is JS-rendered and absent from raw HTML.
        Instead we paginate by detection:
         - Stop when a page returns fewer than PRODUCTS_PER_PAGE items.
         - Also stop if product IDs start repeating (the site wraps
           page N+1 back to page 1 instead of returning empty).
         - Safety cap at 50 pages (~4000 products) to avoid infinite loops.
    """
    logger.info(f"Category: {category_name} ({category_slug})")

    seen_ids: set[str] = set()
    all_products: list[dict] = []
    page = 1
    MAX_PAGES = 50  # safety cap

    while page <= MAX_PAGES:
        url = f"{BASE_URL}{category_slug}" + (f"?sayfa={page}" if page > 1 else "")
        soup = fetch_page(url, session)
        if not soup:
            break

        page_products = extract_products_from_page(soup, category_name)
        logger.info(f"  Page {page}: {len(page_products)} items")

        if not page_products:
            break

        # Check for wrap-around: if first product already seen, we've looped
        first_id = page_products[0]["product_id"]
        if first_id in seen_ids:
            logger.info(f"  Wrap-around detected at page {page}, stopping.")
            break

        # Add new products and track IDs
        for p in page_products:
            seen_ids.add(p["product_id"])
        all_products.extend(page_products)

        # Last page: fewer products than a full page
        if len(page_products) < PRODUCTS_PER_PAGE:
            break

        page += 1

    logger.info(f"  Total: {len(all_products)} items from {category_name} ({page} pages)")
    return all_products


def scrape_all() -> pd.DataFrame:
    """Scrape every category, deduplicate, return DataFrame."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.config import DEFAULT_WORKERS
    
    session = create_session()
    all_products = []
    total_cats = len(CATEGORIES)
    completed_count = [0]
    count_lock = threading.Lock()

    # Use ThreadPoolExecutor for parallel category scraping
    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as executor:
        future_to_cat = {
            executor.submit(scrape_category, name, slug, session): name 
            for name, slug in CATEGORIES.items()
        }
        
        for future in as_completed(future_to_cat):
            cat_name = future_to_cat[future]
            try:
                results = future.result()
                all_products.extend(results)
                with count_lock:
                    completed_count[0] += 1
                    logger.info(f"[PROGRESS] [{completed_count[0]}/{total_cats}] {cat_name} | +{len(results)} items")
                    logger.info(f"[ITEMS] {len(all_products)} items collected so far")
            except Exception as exc:
                logger.error(f"Category {cat_name} generated an exception: {exc}")

    session.close()

    df = pd.DataFrame(all_products)
    if df.empty:
        logger.warning("No products scraped!")
        return df

    before = len(df)
    df = df.drop_duplicates(subset="product_id", keep="first")
    dupes = before - len(df)
    if dupes:
        logger.info(f"Removed {dupes} duplicate items ({before} -> {len(df)})")

    df = df.sort_values(["category", "name"]).reset_index(drop=True)
    logger.info(f"[DONE] {len(df)} items across {df['category'].nunique()} categories")
    return df