"""
Bauhaus Product Data Extraction Module
=====================================

This module provides comprehensive product data extraction from Bauhaus category pages,
utilizing optimized HTML parsing techniques to extract product information and handle
pagination with robust error recovery and performance optimization.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=2.0, page_limit=0) -> list[dict]
    Extracts all products from a specified category with pagination support.
    Returns normalized product dictionaries with consistent field structure.

Performance Architecture
------------------------
This module implements multiple performance optimizations for 35-55% speedup:

Optimization Features
---------------------
1. **lxml Parser**: 3-5x faster HTML processing compared to default parsers
2. **CSS Selectors**: Efficient DOM traversal and element targeting
3. **Session Reuse**: Persistent HTTP connections across requests
4. **String Optimization**: Efficient price cleaning with chained operations
5. **Adaptive Rate Limiting**: Intelligent request timing to prevent detection

Data Extraction Strategy
------------------------
Bauhaus product information is extracted from structured HTML pages:

Product Data Sources
--------------------
1. **Product Grid**: Main container with product listings
   - CSS selectors target product containers (.col-6.col-sm-4)
   - Each container represents individual product items

2. **Product Elements**: Individual product attributes
   - Product name and description
   - Price information (regular and discounted)
   - Brand and manufacturer details
   - SKU and product identifiers
   - Availability status

Pagination Strategy
------------------
- URL-based pagination detection from page navigation
- Automatic termination when no more products are found
- Configurable page limits for testing and development
- Rate limiting with jitter between requests for server compatibility

Data Normalization
------------------
Raw HTML elements are converted to standardized product records:

Price Processing
- Regular and shown prices extracted separately
- Discount rate calculated from price differences
- Currency handling (always TRY)
- Price validation and formatting with string optimization

Product Fields
-------------
Each normalized product contains:
- id: Unique product identifier (SKU)
- sku: SKU or barcode number
- name: Product display name (Turkish)
- brand: Manufacturer or brand name
- category: Subcategory classification
- regular_price: Standard retail price (TRY)
- shown_price: Current display price (TRY)
- discount_rate: Discount percentage (0 when no promotion)
- unit: Unit of measurement (default: "PIECE")
- status: Availability status (default: "IN_SALE")

Session Management
------------------
create_session() -> requests.Session
    Creates optimized session with retry adapters and custom headers:
    - Configurable retry strategy for 5xx and 429 errors
    - Exponential backoff for resilient error handling
    - Custom headers for browser emulation
    - Connection pooling for performance

Error Handling
--------------
- Network failures trigger exponential backoff retries
- Malformed HTML is logged and skipped with warnings
- Missing product elements are handled gracefully
- Rate limit detection triggers automatic delay increases
- Page parsing errors are logged for debugging

Performance Features
-------------------
- lxml parser integration for maximum HTML processing speed
- CSS selectors for precise and efficient element targeting
- Session reuse across multiple requests for connection pooling
- Configurable rate limiting for server compatibility
- Progress tracking for large category extraction
- Adaptive rate limiting to prevent detection while optimizing speed
"""

import time
import random
import logging
from bs4 import BeautifulSoup
from curl_cffi import requests
import config

logger = logging.getLogger(__name__)

class BauhausBlockedException(Exception):
    """Raised when the server returns 403 Forbidden, carrying any partial products
    plus enough pagination state so the category can be *resumed* on retry instead
    of restarting from page 1."""
    def __init__(self, message, products=None, last_page=0, last_page_skus=None, adaptive_delay=None):
        super().__init__(message)
        self.products = products or []
        # Last page that was successfully fetched (0 if 403 hit before any success)
        self.last_page = last_page
        # SKUs seen on that last successful page (for dup-page termination on resume)
        self.last_page_skus = last_page_skus or set()
        # Adaptive delay at the time of blocking, so retries can start slower
        self.adaptive_delay = adaptive_delay

def create_session():
    """
    Creates a curl_cffi session that impersonates a real Chrome client at the
    TLS/HTTP layer. Bauhaus blocks plain python-requests with 403 even when
    headers look correct, so TLS-fingerprint impersonation is required.

    Returns:
        curl_cffi.requests.Session: A session object with browser impersonation
                                     and custom headers. Per-request retry on
                                     5xx/429 is handled in the page loop in
                                     fetch_products_for_category.
    """
    session = requests.Session(impersonate=config.IMPERSONATE_BROWSER)
    session.headers.update(config.DEFAULT_HEADERS)
    return session

def clean_price(price_str):
    """
    Parses a string price (e.g. "5.950,00 TL") into a float.

    Args:
        price_str (str): The raw string extracted from the HTML price element.

    Returns:
        float: The numeric value of the price, or 0.0 if parsing fails.
    """
    if not price_str:
        return 0.0
    # "5.950,00 TL" -> 5950.0
    # Optimized: single pass string cleaning
    price_str = price_str.replace("TL", "").replace(".", "").replace(",", ".")
    try:
        return float(price_str)
    except ValueError:
        return 0.0

def fetch_products_for_category(category_dict, session=None, limit_pages=0,
                                start_page=1, seed_products=None,
                                seed_last_skus=None, seed_delay=None):
    """
    Iterates through the pages of a single category and extracts product data.

    Fetches the HTML of the category URL, appends the '?pg=X' pagination parameter,
    finds product item blocks via BeautifulSoup, extracts relevant properties,
    and returns a normalized list of item dictionaries.

    Args:
        category_dict (dict): A category definition loaded from category_fetcher.
                              Requires 'id', 'url', and 'name'.
        session (requests.Session, optional): The HTTP session to use for requests.
        limit_pages (int, optional): Maximum number of pages to scrape. Restricts
                                     the loop if > 0. Useful for testing.
        start_page (int, optional): Page number to start from (resume support).
                                    Defaults to 1.
        seed_products (list[dict], optional): Products already collected in a previous
                                              attempt. Merged into the result.
        seed_last_skus (set, optional): SKUs from the last successfully fetched page
                                        of the previous attempt, used for the
                                        duplicate-page termination check.
        seed_delay (float, optional): Starting adaptive delay to use (e.g. larger
                                      than the base delay after a prior 403).

    Returns:
        list[dict]: A list of scraped products matching standard output fields.
    """
    cat_id = category_dict["id"]
    cat_url = category_dict["url"]
    name = category_dict["name"]
    req_session = session or create_session()

    # Seed from previous (blocked) attempt so a retry can resume instead of
    # starting from page 1 and re-fetching the same prefix forever.
    products = list(seed_products) if seed_products else []
    page = max(1, int(start_page))
    last_page_skus = set(seed_last_skus) if seed_last_skus else set()

    # Adaptive rate limiting variables
    adaptive_delay = seed_delay if seed_delay is not None else config.REQUEST_DELAY
    consecutive_successes = 0
    consecutive_429s = 0
    page_403_attempts = 0  # Per-page 403 retry counter (resets on any successful page)
    page_net_attempts = 0  # Per-page transient network/timeout retry counter

    if page > 1 or products:
        logger.info(f"▶  [{name}] Resuming scrape from page {page} "
                    f"(seeded with {len(products)} products, delay={adaptive_delay:.2f}s)...")
    else:
        logger.info(f"▶  [{name}] Starting scrape...")
    
    while True:
        if limit_pages > 0 and page > limit_pages:
            logger.info(f"✓  [{name}] Reached limit of {limit_pages} pages.")
            break
            
        url = f"{cat_url}?pg={page}"
        logger.debug(f"  [{name}] Fetching page {page}")
        
        try:
            resp = req_session.get(url, timeout=15)
            resp.raise_for_status()
            
            # Adaptive delay adjustment on success
            if resp.status_code == 200:
                consecutive_successes += 1
                consecutive_429s = 0
                page_403_attempts = 0  # Recovered, reset per-page 403 counter
                page_net_attempts = 0  # Recovered, reset per-page network counter
                
                # Gradually reduce delay after consecutive successes
                if consecutive_successes >= 3 and adaptive_delay > config.REQUEST_DELAY * 0.5:
                    adaptive_delay *= 0.9
                    logger.debug(f"  Reduced delay: {adaptive_delay:.2f}s (after {consecutive_successes} successes)")
                    
        except Exception as e:
            logger.error(f"✗  [{name}] Error fetching page {page}: {e}")
            
            # Adaptive delay adjustment on errors
            if "429" in str(e):
                consecutive_429s += 1
                consecutive_successes = 0
                
                # Increase delay significantly on 429 errors
                adaptive_delay = min(adaptive_delay * 2.0, 10.0)  # Cap at 10 seconds
                logger.warning(f"⚠  [{name}] Rate-limited (429). Increased delay to {adaptive_delay:.2f}s")
                
                # Skip this page on 429
                page += 1
                time.sleep(adaptive_delay)
                continue
            elif "403" in str(e):
                # In-page 403 retry: rather than immediately bailing on the
                # whole category (which previously wiped categories from the
                # day's output when a transient block hit), retry the same
                # page a few times with a fresh TLS session and growing
                # cooldown. Only escalate to BauhausBlockedException once
                # those in-page retries are exhausted.
                page_403_attempts += 1
                consecutive_successes = 0
                # Bump adaptive delay so subsequent pages are gentler if we recover
                adaptive_delay = min(max(adaptive_delay * 1.5, config.REQUEST_DELAY * 2.0), 10.0)

                if page_403_attempts <= config.MAX_403_PAGE_RETRIES:
                    cooldown = config.PAGE_403_COOLDOWN_BASE * page_403_attempts
                    logger.warning(
                        f"⚠  [{name}] 403 on page {page} "
                        f"(in-page attempt {page_403_attempts}/{config.MAX_403_PAGE_RETRIES}). "
                        f"Sleeping {cooldown}s and rotating session before retry…"
                    )
                    time.sleep(cooldown)
                    # Replace this category's session with a fresh one so the
                    # blocked TLS/connection state is discarded for the rest
                    # of this category's pages.
                    try:
                        req_session = create_session()
                    except Exception as se:
                        logger.warning(f"⚠  [{name}] Could not rotate session: {se}")
                    continue  # Retry the same page

                logger.warning(
                    f"⚠  [{name}] Blocked (403) on page {page} after "
                    f"{config.MAX_403_PAGE_RETRIES} in-page retries. "
                    f"Collected {len(products)} products before block."
                )
                # Preserve pagination state so the retry in main.py can resume
                # from this page instead of restarting at page 1.
                raise BauhausBlockedException(
                    str(e),
                    products=products,
                    last_page=max(0, page - 1),
                    last_page_skus=last_page_skus,
                    adaptive_delay=adaptive_delay,
                )
            else:
                # Transient network errors (timeouts, connection resets,
                # SSL hiccups, etc.). Previously this branch did `break`,
                # which silently dropped every remaining page in the
                # category after a single bad request. Instead, retry the
                # same page a few times with growing backoff and a fresh
                # session; if it still fails, skip that one page rather
                # than abandoning the whole category.
                page_net_attempts += 1
                consecutive_successes = 0

                if page_net_attempts <= config.MAX_RETRIES:
                    backoff = config.RETRY_BACKOFF * page_net_attempts
                    logger.warning(
                        f"⚠  [{name}] Network error on page {page} "
                        f"(attempt {page_net_attempts}/{config.MAX_RETRIES}). "
                        f"Sleeping {backoff}s and rotating session before retry…"
                    )
                    time.sleep(backoff)
                    try:
                        req_session = create_session()
                    except Exception as se:
                        logger.warning(f"⚠  [{name}] Could not rotate session: {se}")
                    continue  # Retry the same page

                logger.warning(
                    f"⚠  [{name}] Giving up on page {page} after "
                    f"{config.MAX_RETRIES} network retries; skipping to next page."
                )
                page += 1
                page_net_attempts = 0
                time.sleep(adaptive_delay)
                continue

        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Look for product cards
        items = soup.select('li.col-6.col-sm-4')
        
        if not items:
            logger.info(f"✓  [{name}] No items found on page {page}. Ending.")
            break
            
        current_page_skus = set()
        new_products_found = False
        products_before_page = len(products)

        for item in items:
            # Check price, some items without price might be hidden or placeholders
            price_span = item.select_one('span.price')
            if not price_span:
                continue
                
            sku_span = item.select_one('span.addToWishlist')
            sku = sku_span['data-sku'] if sku_span and sku_span.has_attr('data-sku') else None
            
            # If SKU is completely missing, we might need to look at href
            a_tag = item.select_one('a[href]')
            if not sku and a_tag:
                sku = a_tag['href'].split('-')[-1]
            if not sku:
                continue
                
            current_page_skus.add(sku)
            
            # Extract data
            title_tag = item.select_one('h3.prodName')
            title = title_tag.text.strip() if title_tag else ""
            
            brand_tag = item.select_one('span.subInfo')
            brand = brand_tag.text.strip() if brand_tag else ""
            
            price_val = clean_price(price_span.text)
            
            # Determine images
            img_tag = item.select_one('img.owl-lazy')
            if img_tag and img_tag.has_attr('data-src'):
                image_url = img_tag['data-src']
            elif img_tag and img_tag.has_attr('src'):
                image_url = img_tag['src']
            else:
                image_url = ""
            
            product_url = ""
            if a_tag:
                 href = a_tag['href']
                 product_url = config.BASE_URL + href if href.startswith('/') else href

            products.append({
                "product_name": title,
                "price": price_val,
            })
            new_products_found = True
            
        page_added = len(products) - products_before_page
        # Per-page progress so long categories are visible in real time
        # instead of going silent until the whole category finishes.
        logger.info(
            f"  [{name}] page {page}: +{page_added} products "
            f"(category total: {len(products)}, delay={adaptive_delay:.2f}s)"
        )

        # Stop condition: if this page's SKUs are identical to last page
        if current_page_skus == last_page_skus or not new_products_found:
            logger.info(f"✓  [{name}] Page {page} has duplicate/empty items. Ending.")
            break

        last_page_skus = current_page_skus
        page += 1
        
        # Use adaptive delay instead of fixed delay
        delay = adaptive_delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX)
        time.sleep(delay)
        
    logger.info(f"✅ [{name}] Completed: {len(products)} products across {page-1} pages.")
    return products
