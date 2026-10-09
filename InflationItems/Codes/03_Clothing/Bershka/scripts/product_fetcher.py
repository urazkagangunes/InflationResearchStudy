"""
product_fetcher.py — Fetches all products for a Bershka category.
=================================================================

Public API
----------
fetch_products_for_category(category, session=None, delay=2) -> list[dict]
    Returns all product records for the given category.

How it works
------------
Bershka uses the Inditex itxrest v3 API. For each category:
  1. GET .../category/{CAT_ID}/product  → returns a list of all product IDs
  2. GET .../productsArray?productIds=X,Y,Z  → returns full product details
                                               (in batches of BATCH_SIZE)

Each product contains ``bundleProductSummaries`` which list colour/size
variants with pricing. We extract the first available price for each product.

Uses ``curl_cffi`` to impersonate Chrome's TLS fingerprint and bypass
Akamai anti-bot protection.
"""

import logging
import random
import time
from typing import Optional

from curl_cffi import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Create a curl_cffi Session that impersonates Chrome to bypass Akamai."""
    session = requests.Session(impersonate=config.BROWSER_IMPERSONATE)
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _warmup_session(session: requests.Session) -> None:
    """Visit the homepage to collect Akamai cookies before making API calls."""
    try:
        resp = session.get(f"{config.BASE_URL}/tr/", timeout=20)
        logger.debug("Session warmup: status %d, cookies: %d", resp.status_code, len(session.cookies))
    except Exception as exc:
        logger.warning("Session warmup failed: %s", exc)


def _request_with_retry(session: requests.Session, url: str, timeout: int = 20) -> Optional[dict]:
    """
    GET a URL and return parsed JSON, with retry + backoff.

    Returns None on permanent failure.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout)

            # 404 → endpoint genuinely doesn't exist
            if resp.status_code == 404:
                return None

            # 429 / 403 → rate limited or bot-blocked
            if resp.status_code in (403, 429):
                retry_after = int(resp.headers.get("Retry-After", config.RATE_LIMIT_BACKOFF))
                wait = max(retry_after, config.RATE_LIMIT_BACKOFF)
                logger.warning(
                    "Rate-limited (%d). Backing off %ds (attempt %d/%d)…",
                    resp.status_code, wait, attempt, config.MAX_RETRIES,
                )
                time.sleep(wait)
                # Re-warm the session to get fresh Akamai tokens
                _warmup_session(session)
                continue

            resp.raise_for_status()
            return resp.json()

        except Exception as exc:
            if attempt == config.MAX_RETRIES:
                logger.error("All %d attempts failed for %s: %s", config.MAX_RETRIES, url, exc)
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning("Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait)
            time.sleep(wait)

    return None


def get_product_ids_for_category(session: requests.Session, category_id: str) -> list[str]:
    """
    Fetch all product IDs belonging to a category.

    Returns a list of product ID strings, or an empty list on failure.
    """
    url = (
        f"{config.CATALOG_V3_URL}/category/{category_id}/product"
        f"?languageId={config.LANGUAGE_ID}"
        f"&showProducts=false"
        f"&showNoStock=false"
        f"&appId={config.APP_ID}"
        f"&locale=tr_TR"
    )
    data = _request_with_retry(session, url)
    if data is None:
        return []
    return [str(pid) for pid in data.get("productIds", [])]


def get_products_detail(
    session: requests.Session,
    product_ids: list[str],
    category_id: str,
) -> list[dict]:
    """
    Fetch full product details in batches of BATCH_SIZE.

    Returns raw product dicts from the Inditex API.
    """
    all_products = []
    for i in range(0, len(product_ids), config.BATCH_SIZE):
        batch = product_ids[i : i + config.BATCH_SIZE]
        ids_str = ",".join(batch)
        url = (
            f"{config.CATALOG_V3_URL}/productsArray"
            f"?languageId={config.LANGUAGE_ID}"
            f"&productIds={ids_str}"
            f"&categoryId={category_id}"
            f"&appId={config.APP_ID}"
            f"&locale=tr_TR"
        )
        data = _request_with_retry(session, url)
        if data is not None:
            batch_prods = data.get("products", [])
            all_products.extend(batch_prods)
            logger.info(f"  Page {i//config.BATCH_SIZE + 1}: {len(batch_prods)} items")
        
        # Jittered delay with floor
        import random
        sleep_time = max(config.DELAY_FLOOR, random.normalvariate(config.REQUEST_DELAY, config.REQUEST_STDEV))
        time.sleep(sleep_time)
    return all_products


def extract_product_record(product: dict, category_name: str) -> Optional[dict]:
    """
    Extract a clean product record from an Inditex product dict.

    Returns a flat dict with name, prices, etc., or None if essential data
    is missing.
    """
    if not product or not isinstance(product, dict):
        return None

    name = (product.get("name") or "").strip()
    if not name:
        return None

    product_id = str(product.get("id", ""))

    # Navigate into bundleProductSummaries → detail → colors → sizes
    # to find the first available price.
    regular_price = None
    sale_price = None
    color_name = ""

    try:
        summaries = product.get("bundleProductSummaries") or []
        if not summaries:
            return None
        detail = summaries[0].get("detail") or {}
        colors = detail.get("colors") or []

        for color in colors:
            color_name = color.get("name", "")
            for size in (color.get("sizes") or []):
                price_cents = size.get("price")
                old_price_cents = size.get("oldPrice") or price_cents
                if price_cents is not None:
                    sale_price = int(price_cents) / 100
                    regular_price = int(old_price_cents) / 100 if old_price_cents else sale_price
                    break  # Take the first available price
            if sale_price is not None:
                break
    except Exception:
        return None

    if sale_price is None:
        return None

    # Calculate discount percentage
    discount_pct = 0.0
    if regular_price and sale_price < regular_price:
        discount_pct = round((1 - sale_price / regular_price) * 100, 2)

    return {
        "product_name":  name,
        "price":         round(sale_price, 2),
        "product_id":    product_id,
        "brand":         "Bershka",
        "category":      category_name,
        "color":         color_name,
        "regular_price": round(regular_price, 2),
        "discount_pct":  discount_pct,
        "currency":      "TRY",
    }


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
) -> list[dict]:
    """
    Fetch ALL products for a category and return normalised records.

    Args:
        category:  Dict with keys ``id``, ``product_category_id``,
                   ``name``, ``parent_name``.
        session:   Optional shared curl_cffi Session.
        delay:     Seconds to wait between batch requests.

    Returns:
        List of normalised product dicts.
    """
    if session is None:
        session = _make_session()
        _warmup_session(session)

    # Use product_category_id (from viewCategoryId) for API calls,
    # falling back to the regular id if not available.
    category_id = category.get("product_category_id") or category["id"]
    category_name = category.get("name", category_id)
    parent = category.get("parent_name")
    full_category = f"{parent} > {category_name}" if parent else category_name

    # Step 1: Get all product IDs for this category
    product_ids = get_product_ids_for_category(session, category_id)
    if not product_ids:
        logger.debug("Category '%s' (%s): no product IDs found.", category_name, category_id)
        return []

    logger.debug("Category '%s': %d product IDs. Fetching details…", category_name, len(product_ids))

    # Step 2: Fetch full product details in batches
    raw_products = get_products_detail(session, product_ids, category_id)

    # Step 3: Extract clean records
    records = []
    seen_ids = set()
    for raw in raw_products:
        record = extract_product_record(raw, full_category)
        if record is None:
            continue
        # Deduplicate by product_id within this category
        pid = record["product_id"] or record["product_name"]
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        records.append(record)

    # Normal distribution sleep (mean = config.REQUEST_DELAY, stdev = 0.5)
    # Ensure delay is at least 0.1s to avoid negative values
    final_delay = max(0.3, random.normalvariate(config.REQUEST_DELAY, 0.5))
    time.sleep(final_delay)
    return records
