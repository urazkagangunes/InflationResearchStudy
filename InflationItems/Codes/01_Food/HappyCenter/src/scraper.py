"""
Scraper - core engine for Happy Center.
Loops subcategories, handles pagination, extracts product data.

Site: happycenter.com.tr
Platform: Custom (PHP-based, Cloudflare CDN)
Products: Server-side rendered HTML, no JS required.
Pagination: ?page=N, last page number available in pagination links.
"""

import re
import logging

import requests
import pandas as pd

from src.config import BASE_URL, CATEGORIES, MAX_PAGES
from src.utils import fetch_page, get_last_page_number, parse_price


logger = logging.getLogger(__name__)


def extract_products_from_page(soup, category: str) -> list[dict]:
    """
    Parse all product cards from a Happy Center category page.

    Strategy:
        1. Find all <img> tags with thumbnail URLs (contain '95x95' from
           static.happycenter.com.tr/Uploads/).
        2. Navigate to parent <a> to get product URL.
        3. Find product name from nearby text link or img title/alt.
        4. Find price from nearby text matching 'XX,XX TL' pattern.
    """
    products = []

    # Find all product images (thumbnails from their CDN)
    product_imgs = soup.find_all("img", src=re.compile(r"static\.happycenter\.com\.tr/Uploads/.*95x95"))

    if not product_imgs:
        # Fallback: try without 95x95 filter
        product_imgs = soup.find_all("img", src=re.compile(r"static\.happycenter\.com\.tr/Uploads/"))

    # Track seen URLs to avoid duplicates within a page
    # (the site renders products twice: sidebar carousel + main grid)
    seen_slugs = set()

    for img in product_imgs:
        try:
            # Get the parent <a> tag wrapping the image
            parent_a = img.find_parent("a", href=True)
            if not parent_a:
                continue

            slug = parent_a.get("href", "").strip()
            if not slug or slug == "/" or slug.startswith("#"):
                continue

            # Skip navigation/category links (they have slashes in path)
            # Product slugs are single-segment: /Product_Name
            clean_slug = slug.lstrip("/")
            if "/" in clean_slug:
                continue

            # Skip if already seen (avoids sidebar duplicates)
            if clean_slug in seen_slugs:
                continue
            seen_slugs.add(clean_slug)

            # Product name: prefer img title/alt, fallback to finding
            # a sibling <a> with the same href that has text content
            name = img.get("title") or img.get("alt") or ""
            name = name.strip()

            if not name:
                # Look for a sibling or nearby <a> with same href and text
                container = parent_a.parent
                if container:
                    for sibling_a in container.find_all("a", href=slug):
                        text = sibling_a.get_text(strip=True)
                        if text and text != "Şube Seçiniz" and "TL" not in text:
                            name = text
                            break

            if not name:
                continue

            # Image URL
            image_url = img.get("src", "")

            # Price: look in the parent container for text matching price pattern
            price = None
            container = parent_a.parent
            if container:
                # Go up one more level if needed to find the full product card
                card = container.parent if container.parent else container

                # Search for price text in the card
                card_text = card.get_text(" ", strip=True)
                price_matches = re.findall(r"([\d.]+,\d{2})\s*(?:TL)?", card_text)

                if price_matches:
                    # Take the first price match associated with this product
                    price = parse_price(price_matches[0])

                # If no price found in immediate card, try the container
                if price is None and container:
                    container_text = container.get_text(" ", strip=True)
                    price_matches = re.findall(r"([\d.]+,\d{2})\s*(?:TL)?", container_text)
                    if price_matches:
                        price = parse_price(price_matches[0])

            # Build product URL
            product_url = f"{BASE_URL}{slug}" if slug.startswith("/") else f"{BASE_URL}/{slug}"

            products.append({
                "product_id": clean_slug,
                "name": name,
                "current_price": price,
                "regular_price": None,       # site doesn't show original price
                "is_discounted": False,       # no discount info available
                "discount_pct": None,
                "category": category,
                "product_url": product_url,
                "image_url": image_url,
                "in_stock": True,             # listed = in stock
            })

        except Exception as e:
            logger.warning(f"  Error parsing product: {e}")
            continue

    return products


def scrape_subcategory(
    category_name: str,
    category_path: str,
    session: requests.Session,
) -> list[dict]:
    """
    Scrape ALL products from one subcategory with pagination.

    Pagination strategy:
        1. Fetch page 1, extract last page number from pagination links.
        2. Loop through all pages up to last page (capped at MAX_PAGES).
        3. Stop early if a page returns 0 products (safety).
    """
    logger.info(f"Subcategory: {category_name} ({category_path})")

    # Page 1
    url = f"{BASE_URL}{category_path}"
    soup = fetch_page(url, session)
    if not soup:
        return []

    # Get total pages from pagination
    last_page = get_last_page_number(soup)
    last_page = min(last_page, MAX_PAGES)
    logger.info(f"  {last_page} page(s) detected")

    all_products = extract_products_from_page(soup, category_name)
    logger.info(f"  Page 1/{last_page}: {len(all_products)} products")

    # Pages 2..N
    for page in range(2, last_page + 1):
        page_url = f"{BASE_URL}{category_path}?page={page}"
        soup = fetch_page(page_url, session)
        if not soup:
            logger.warning(f"  Failed to fetch page {page}, stopping subcategory.")
            break

        page_products = extract_products_from_page(soup, category_name)
        logger.info(f"  Page {page}/{last_page}: {len(page_products)} products")

        if not page_products:
            logger.info(f"  Empty page {page}, stopping.")
            break

        all_products.extend(page_products)

    logger.info(f"  Total: {len(all_products)} from {category_name}\n")
    return all_products


def scrape_all() -> pd.DataFrame:
    """Scrape every subcategory, deduplicate, return DataFrame."""
    session = requests.Session()
    all_products = []

    for name, path in CATEGORIES.items():
        all_products.extend(scrape_subcategory(name, path, session))

    session.close()

    df = pd.DataFrame(all_products)
    if df.empty:
        logger.warning("No products scraped!")
        return df

    # Deduplicate by product_id (some products appear in multiple subcategories)
    before = len(df)
    df = df.drop_duplicates(subset="product_id", keep="first")
    dupes = before - len(df)
    if dupes:
        logger.info(f"Removed {dupes} duplicates ({before} -> {len(df)})")

    df = df.sort_values(["category", "name"]).reset_index(drop=True)

    logger.info(f"DONE - {len(df)} unique products across {df['category'].nunique()} categories")
    return df
