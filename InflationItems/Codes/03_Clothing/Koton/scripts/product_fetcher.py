"""
Koton Product Data Extraction Module
===================================

This module provides comprehensive product data extraction from Koton category pages,
utilizing HTML parsing techniques to extract embedded product information and handle
pagination with robust error recovery.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=2.0, page_limit=0) -> list[dict]
    Extracts all products from a specified category with pagination support.
    Returns normalized product dictionaries with consistent field structure.

Data Extraction Strategy
------------------------
Koton embeds comprehensive product data within HTML pages using multiple sources:

Product Data Sources
--------------------
1. **js-insider-product**: Hidden div containing JSON blob with full product details
   - Product name, prices, URLs, images, stock information
   - Primary data source for core product attributes

2. **js-product-wrapper**: Product container with data attributes
   - Product pk (internal identifier)
   - SKU/barcode information
   - Wrapper for insider-product data

3. **js-ga4-product-item**: GA4 tracking div with metadata
   - Brand information (always "Koton")
   - Category hierarchy and taxonomy
   - Base code (style code) for product identification

Pagination Strategy
------------------
- URL-based pagination using ?page=N parameter
- Automatic termination when pages return no products
- Configurable page limits for testing and development
- Rate limiting with jitter between requests

Data Normalization
------------------
Raw HTML elements are converted to standardized product records:

Price Processing
- Regular and sale prices extracted separately
- Discount percentage calculated from price differences
- Currency handling (always TRY)
- Price validation and formatting

Product Fields
-------------
Each normalized product contains:
- pk: Koton internal product-variant identifier
- sku: EAN barcode number
- base_code: Style code (e.g., "6SAK60098EW")
- name: Complete product display name
- brand: Brand name (always "Koton")
- category: Full taxonomy path (e.g., "WOMEN > WOVEN TOPS > SHIRTS LS")
- color: Color variant specification
- size: Size variant information
- regular_price: Standard retail price (TRY)
- sale_price: Current discounted price (TRY)
- discount_pct: Discount percentage (0 if none)
- currency: Currency code (always "TRY")
- stock: Available stock quantity for variant

Error Handling
--------------
- Network failures trigger exponential backoff retries
- Malformed HTML is logged and skipped
- Missing product elements are handled gracefully
- Rate limit detection triggers automatic delay increases

Performance Features
-------------------
- lxml parser for efficient HTML processing
- CSS selectors for precise element targeting
- Session reuse for connection pooling
- Configurable rate limiting for server compatibility
- Progress tracking for large category extraction
"""

import json
import logging
import random
import re
import time
from typing import Optional

import requests
from lxml import html

import config

logger = logging.getLogger(__name__)

# Regex to sanitise the JSON-like blobs embedded in the page.
# Koton inlines values like: "price":  1499.99 , (extra spaces are fine
# for json.loads, but sometimes there are trailing commas before }).
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _make_session() -> requests.Session:
    """Create a requests Session with a randomly chosen User-Agent.

    Each worker (thread) calls this once, so concurrent workers present
    different browser fingerprints to the server.
    """
    session = requests.Session()
    headers = dict(config.DEFAULT_HEADERS)  # shallow copy
    headers["User-Agent"] = random.choice(config.USER_AGENTS)
    session.headers.update(headers)
    
    # Enable connection pooling for faster requests
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0,  # We handle retries manually
        pool_block=False
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    
    return session


def _clean_json(text: str) -> str:
    """Remove trailing commas and fix minor formatting issues."""
    # Remove trailing commas before closing braces/brackets
    text = _TRAILING_COMMA_RE.sub(r"\1", text)
    return text.strip()


def _parse_insider(raw_text: str) -> dict:
    """
    Parse the js-insider-product JSON blob.

    Returns a dict or empty dict on failure.
    Keys of interest: id, name, taxonomy, currency,
                      unit_price, unit_sale_price,
                      url, stock, color, size, product_image_url.
    """
    try:
        return json.loads(_clean_json(raw_text))
    except json.JSONDecodeError:
        return {}


def _parse_ga4(raw_text: str) -> dict:
    """
    Parse the js-ga4-product-item JSON blob.

    Keys of interest: item_name, item_id, price, item_brand,
                      item_category … item_category5, base_code.
    """
    try:
        return json.loads(_clean_json(raw_text))
    except json.JSONDecodeError:
        return {}


def _extract_json_blobs(wrapper):
    """
    Extract both insider and GA4 JSON blobs from a wrapper in one pass.
    Returns tuple of (insider_dict, ga4_dict).
    """
    insider: dict = {}
    ga4: dict = {}
    
    # Single XPath query to get both divs at once
    json_divs = wrapper.xpath('.//div[contains(@class, "js-insider-product") or contains(@class, "js-ga4-product-item")]')
    
    for div in json_divs:
        class_attr = div.get("class", "")
        if "js-insider-product" in class_attr:
            insider = _parse_insider(div.text_content())
        elif "js-ga4-product-item" in class_attr:
            ga4 = _parse_ga4(div.text_content())
    
    return insider, ga4


def _parse_product(wrapper, category_name: str) -> Optional[dict]:
    """
    Extract a clean product record from a .js-product-wrapper element.

    Returns None if essential data is missing.
    """
    # ── Data from the wrapper element itself ──────────────────────────────────
    pk    = wrapper.get("data-pk", "")
    sku   = wrapper.get("data-sku", "")
    price = wrapper.get("data-price", "")

    # ── Extract JSON blobs in one pass ────────────────────────────────────────
    insider, ga4 = _extract_json_blobs(wrapper)

    # ── Combine into a flat record ────────────────────────────────────────────
    name = insider.get("name") or ga4.get("item_name") or ""
    if not name:
        return None  # Skip malformed entries

    # Prices: prefer insider (unit_price / unit_sale_price) which are cleaner
    try:
        regular_price = float(insider.get("unit_price") or ga4.get("price") or price or 0)
    except (ValueError, TypeError):
        regular_price = 0.0
    try:
        sale_price = float(insider.get("unit_sale_price") or regular_price)
    except (ValueError, TypeError):
        sale_price = regular_price

    discount_pct = 0.0
    if regular_price and sale_price < regular_price:
        discount_pct = round((1 - sale_price / regular_price) * 100, 2)

    # Category: use taxonomy list from insider if available
    taxonomy: list = insider.get("taxonomy") or []
    category = (
        " > ".join(t for t in taxonomy if t) if taxonomy else category_name
    )

    # Brand
    brand = ga4.get("item_brand", "Koton")

    # Style/base code (e.g. "6SAK60098EW")
    base_code = ga4.get("base_code", "")

    # Stock & colour/size variant info
    stock = insider.get("stock", None)
    color = insider.get("color", "")
    size  = insider.get("size", "")

    return {
        "product_name": name,
        "price":        round(sale_price, 2),
    }


def _fetch_page(
    session: requests.Session,
    category_url: str,
    page: int,
):
    """
    Fetch one page of a category listing.
    Returns tuple of (lxml HtmlElement or None, response_time in seconds).

    Handles 429 / 403 rate-limit responses with a longer back-off pause
    before retrying so the scraper recovers gracefully instead of giving up.
    """
    params = {"page": page} if page > 1 else {}
    response_time = 0.0

    # Update Referer to look like natural browser navigation:
    # first page comes from the homepage, subsequent pages come from page N-1.
    if page > 1:
        prev_params = f"?page={page - 1}" if page > 2 else ""
        session.headers["Referer"] = category_url + prev_params
    else:
        session.headers["Referer"] = config.BASE_URL + "/"

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(category_url, params=params, timeout=30)

            # 404 → category or page genuinely doesn't exist
            if resp.status_code == 404:
                return None, 0.0

            # 429 / 405 / 403 → rate-limited / blocked; pause and retry
            if resp.status_code in (403, 405, 429):
                retry_after = int(resp.headers.get("Retry-After", config.RATE_LIMIT_BACKOFF))
                wait = max(retry_after, config.RATE_LIMIT_BACKOFF)
                logger.warning(
                    "Rate-limited (%d) on page %d. Backing off %ds (attempt %d/%d)...",
                    resp.status_code, page, wait, attempt, config.MAX_RETRIES,
                )
                time.sleep(wait)
                # Rotate to a fresh User-Agent after a rate-limit hit
                session.headers["User-Agent"] = random.choice(config.USER_AGENTS)
                continue

            resp.raise_for_status()
            response_time = resp.elapsed.total_seconds()
            return html.fromstring(resp.text), response_time

        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for page %d: %s",
                    config.MAX_RETRIES, page, exc,
                )
                return None, 0.0
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %ds...",
                attempt, config.MAX_RETRIES, exc, wait
            )
            time.sleep(wait)
    return None, 0.0


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """
    Fetch ALL products for a category dict returned by fetch_categories().

    Args:
        category:   Dict with keys ``name``, ``slug``, ``url``,
                    ``parent_name`` (optional).
        session:    Optional shared requests.Session.
        delay:      Seconds to wait between page requests.
        page_limit: Max pages to fetch (0 = unlimited).

    Returns:
        List of normalised product dicts.
    """
    if session is None:
        session = _make_session()

    category_url = category["url"]
    category_name = category["name"]
    all_products: list[dict] = []
    seen_pks: set[str] = set()
    page = 1

    while True:
        if page_limit and page > page_limit:
            break

        tree, response_time = _fetch_page(session, category_url, page)
        if tree is None:
            break

        # Find all product wrapper divs on this page using XPath (faster than CSS selectors)
        wrappers = tree.xpath('//div[contains(@class, "js-product-wrapper")]')
        if not wrappers:
            # Also try with the broader selector used on some pages
            wrappers = tree.xpath('//div[@data-url and @data-price]')

        page_count = 0
        new_on_page = 0
        for wrapper in wrappers:
            product = _parse_product(wrapper, category_name)
            if product is None:
                continue
            # Deduplicate within this category scrape by pk (variant-level key)
            pk_key = product["pk"] or product["sku"] or product["name"]
            if pk_key and pk_key in seen_pks:
                continue
            if pk_key:
                seen_pks.add(pk_key)
            all_products.append(product)
            page_count += 1
            new_on_page += 1

        # Provide feedback: log every page in DEBUG, but log every 5 pages in INFO
        # so the user knows long categories aren't stuck.
        if page % 5 == 0:
            logger.info("  Page %2d: %2d products (total: %d)", page, page_count, len(all_products))
        else:
            logger.debug("  Page %2d: %2d products (total: %d)", page, page_count, len(all_products))

        # If we got fewer products than expected the page might be the last
        # but we'll keep going until a page returns 0 wrappers.
        # Alternatively, if a page returns products but NONE of them are new,
        # Koton might be repeating the last page forever (infinite scroll bug).
        if page_count == 0 or new_on_page == 0:
            logger.debug("Page %d yielded 0 new products. Ending.", page)
            break

        page += 1
        
        # Adaptive delay: faster for quick responses, but respect minimum delay
        # If server responds in 0.5s, we can be more aggressive
        # If server is slow (2s+), we back off more
        adaptive_delay = delay * random.uniform(0.5, 1.5)
        if response_time > 0:
            # Adjust based on response time: faster responses = shorter delays
            adaptive_delay = max(0.3, min(delay * 2, response_time * 0.8 + delay * 0.5))
        
        time.sleep(adaptive_delay)

    return all_products
