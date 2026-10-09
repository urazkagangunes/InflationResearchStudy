"""
category_fetcher.py — Discovers all scrapable Bershka product categories.
=========================================================================

Public API
----------
fetch_categories(session=None) -> list[dict]
    Returns all leaf categories from the Bershka Inditex catalog API.
    Each dict contains ``id``, ``product_category_id``, ``name``, ``parent_name``.

Discovery strategy
------------------
Bershka is part of the Inditex group and exposes a REST API at:
  /itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}/category

This returns the full category tree as nested JSON. We recursively walk
the tree to extract all leaf categories (those with no subcategories),
since only leaf categories contain products.

Some categories use a ``viewCategoryId`` that maps the menu item to the
actual product category. The product API requires this remapped ID.
"""

import logging
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


def fetch_categories(session: Optional[requests.Session] = None) -> list[dict]:
    """
    Return all leaf categories from the Bershka Inditex catalog API.

    Recursively walks the category tree and returns only leaf nodes
    (categories that have no subcategories), since these are the ones
    that actually contain products.

    Returns a list of dicts:
        [
            {
                "id":                  "1010593678",
                "product_category_id": "1010193216",
                "name":                "Pantolon",
                "parent_name":         "Giyim",
            },
            ...
        ]
    """
    if session is None:
        session = _make_session()
        _warmup_session(session)

    url = (
        f"{config.CATALOG_V2_URL}/category"
        f"?languageId={config.LANGUAGE_ID}"
        f"&typeCatalog=1"
        f"&appId={config.APP_ID}"
    )
    logger.info("Fetching category tree from Bershka API…")

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            if attempt == config.MAX_RETRIES:
                logger.error("Failed to fetch categories after %d attempts: %s", config.MAX_RETRIES, exc)
                return []
            wait = config.RETRY_BACKOFF * attempt
            logger.warning("Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait)
            time.sleep(wait)

    categories = []

    def walk(items, parent_name=None):
        """Recursively walk the category tree, collecting leaf categories."""
        if not items:
            return
        for item in items:
            cat_name = item.get("name", "")
            sub = item.get("subcategories") or item.get("subCategories") or []
            if sub:
                # Non-leaf node — recurse into subcategories
                walk(sub, parent_name=cat_name)
            else:
                # Leaf node — this category has products
                cid = item.get("id") or item.get("categoryId")
                if cid:
                    # Bershka uses viewCategoryId to map menu categories to
                    # actual product categories. If present and non-zero, the
                    # product API requires this ID instead of the menu ID.
                    view_id = item.get("viewCategoryId")
                    product_cat_id = str(view_id) if view_id else str(cid)
                    categories.append({
                        "id":                  str(cid),
                        "product_category_id": product_cat_id,
                        "name":                cat_name,
                        "parent_name":         parent_name,
                    })

    # The API response may be a list or a dict with a nested structure
    if isinstance(data, list):
        walk(data)
    elif isinstance(data, dict):
        walk(data.get("categories") or data.get("items") or [data])

    # Deduplicate by category id
    seen = set()
    unique = []
    for cat in categories:
        if cat["id"] not in seen:
            seen.add(cat["id"])
            unique.append(cat)

    logger.info("Found %d leaf categories.", len(unique))
    return unique
