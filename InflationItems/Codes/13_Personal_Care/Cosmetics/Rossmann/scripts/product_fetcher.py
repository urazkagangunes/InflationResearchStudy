"""
Rossmann Product Data Extraction Module
=======================================

Fetches every product in a Rossmann category via the Magento 2 GraphQL
``products`` query and returns a list of normalised flat dictionaries
ready for CSV export / downstream inflation calculations.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=0.5, page_limit=0) -> list[dict]
    Iterates through all GraphQL pages for ``category["id"]`` and returns
    the combined product list.

Data Flow
---------
1. Build a GraphQL POST body with the ``category_id`` filter and current
   page number (``currentPage``) / ``pageSize``.
2. Parse the JSON response's ``data.products.items`` array.
3. Convert each raw item to a flat record (see ``_parse_product``).
4. Advance ``currentPage`` until ``total_pages`` is reached or a page
   returns zero items.

Product Fields (output schema)
------------------------------
- ``id``            : GraphQL UID (base64 of the Magento product id)
- ``sku``           : SKU / internal article number
- ``name``          : Product display name (Turkish)
- ``brand``         : Magento custom string attribute ``brand``
                      (falls back to the first whitespace-delimited token
                      of the product name when the attribute is empty).
- ``category``      : Name of the top-level category being scraped
- ``regular_price`` : Regular shelf price in TRY
- ``shown_price``   : Currently displayed price in TRY (after discount)
- ``discount_rate`` : Discount percentage (0 when none)
- ``unit``          : ``""`` — not exposed by the API for cosmetics
- ``status``        : ``IN_STOCK`` / ``OUT_OF_STOCK``
- ``image_url``     : Product image URL
- ``product_url``   : Full product page URL
"""

import logging
import random
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


# GraphQL document reused across pages. ``category_id`` is typed as String
# because that's what Magento's schema requires for the ``EQ`` operator.
#
# Note on the ``brand`` field: Rossmann exposes a custom string attribute
# called ``brand`` (verified via ``customAttributeMetadata``).  Magento's
# built-in ``manufacturer`` field is also present but typically returns
# null on this store.  We query ``brand`` directly so we don't have to
# infer it from category names.
_PRODUCTS_QUERY = """
query($id: String!, $pageSize: Int!, $currentPage: Int!) {
  products(
    filter: {category_id: {eq: $id}}
    pageSize: $pageSize
    currentPage: $currentPage
  ) {
    total_count
    page_info { current_page page_size total_pages }
    items {
      uid
      sku
      name
      brand
      url_key
      stock_status
      price_range {
        minimum_price {
          regular_price { value currency }
          final_price   { value currency }
          discount      { amount_off percent_off }
        }
      }
      small_image { url }
      image       { url }
    }
  }
}
""".strip()


def _make_session() -> requests.Session:
    """Return a new ``requests.Session`` pre-configured with default headers."""
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _parse_product(raw: dict, category_name: str) -> dict:
    """Convert one GraphQL product item into the flat output record."""
    price_min = (raw.get("price_range") or {}).get("minimum_price") or {}
    regular = ((price_min.get("regular_price") or {}).get("value")) or 0
    final   = ((price_min.get("final_price")   or {}).get("value")) or regular
    discount_pct = ((price_min.get("discount") or {}).get("percent_off")) or 0

    small_image = (raw.get("small_image") or {}).get("url") or ""
    big_image   = (raw.get("image")       or {}).get("url") or ""
    image_url   = small_image or big_image

    url_key = raw.get("url_key") or ""
    product_url = f"{config.BASE_URL}/{url_key}" if url_key else ""

    # ``brand`` is a Magento custom attribute (string) on Rossmann.  Fall
    # back to the first token of the product name when it is missing
    # (some imported items don't have the attribute populated).
    brand = (raw.get("brand") or "").strip()
    if not brand:
        brand = (raw.get("name") or "").strip().split(" ", 1)[0]

    return {
        "product_name": raw.get("name") or "",
        "price":        round(float(final), 2) if final else 0.0,
    }


def _fetch_page(
    session: requests.Session,
    category_id: str,
    page: int,
    page_size: int,
) -> Optional[dict]:
    """POST one ``products`` GraphQL query with retries.

    Returns the ``data.products`` dict on success or ``None`` when every
    retry attempt fails (or the API returns a GraphQL-level error).
    """
    payload = {
        "query": _PRODUCTS_QUERY,
        "variables": {
            "id":          str(category_id),
            "pageSize":    int(page_size),
            "currentPage": int(page),
        },
    }

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.post(config.GRAPHQL_URL, json=payload, timeout=30)

            if resp.status_code == 403:
                logger.warning(
                    "403 Forbidden for category %s page %d — backing off.",
                    category_id, page,
                )
                return None

            resp.raise_for_status()
            data = resp.json()

            if data.get("errors"):
                logger.warning(
                    "GraphQL errors on category %s page %d: %s",
                    category_id, page, data["errors"],
                )
                return None

            return (data.get("data") or {}).get("products") or None

        except (requests.RequestException, ValueError) as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for category %s page %d: %s",
                    config.MAX_RETRIES, category_id, page, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds...", attempt, exc, wait
            )
            time.sleep(wait)

    return None


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Return every product in ``category`` by iterating GraphQL pages.

    Args
    ----
    category : dict
        Category dict as produced by ``category_fetcher.fetch_categories``.
        Must contain at least ``id`` and ``name``.
    session : requests.Session, optional
        Shared session with the required headers. Created lazily when ``None``.
    delay : float
        Base inter-page sleep in seconds (multiplied by a uniform jitter in
        ``[config.JITTER_MIN, config.JITTER_MAX]`` for each page).
    page_limit : int
        Maximum pages to fetch per category. ``0`` (default) → unlimited.

    Returns
    -------
    list[dict]
        Normalised product records (see ``_parse_product``). An empty list
        is returned when the very first page fails.
    """
    if session is None:
        session = _make_session()

    cat_id   = category["id"]
    cat_name = category["name"]
    page_size = config.PAGE_SIZE

    all_products: list[dict] = []
    page = 1
    total_pages: Optional[int] = None

    while True:
        if page_limit and page > page_limit:
            break

        data = _fetch_page(session, cat_id, page, page_size)
        if data is None:
            break

        page_info = data.get("page_info") or {}
        if total_pages is None:
            total_pages = page_info.get("total_pages")
            total_count = data.get("total_count") or 0
            logger.debug(
                "Category '%s' → %d products across %s pages",
                cat_name, total_count, total_pages,
            )

        items = data.get("items") or []
        if not items:
            break

        for raw in items:
            all_products.append(_parse_product(raw, cat_name))

        logger.debug(
            "Category '%s' – page %d/%s → %d products (running total: %d)",
            cat_name, page, total_pages, len(items), len(all_products),
        )

        if total_pages is not None and page >= int(total_pages):
            break

        page += 1
        time.sleep(delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX))

    return all_products
