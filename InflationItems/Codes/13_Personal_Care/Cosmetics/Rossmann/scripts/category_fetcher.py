"""
Rossmann Category Discovery Module
==================================

Discovers the scrapable product taxonomy for Rossmann Türkiye via the
Magento 2 GraphQL ``categoryList`` query.

Public Interface
----------------
fetch_categories(session=None) -> list[dict]
    Returns the list of top-level categories to scrape. Each dict has::

        {
          "id":          "3",            # Magento internal category id
          "name":        "Makyaj",
          "url_key":     "makyaj",
          "parent_id":   None,           # always None for top-level entries
          "parent_name": None,
          "product_count": 2544,         # None if the probe query failed
        }

Discovery Strategy
------------------
Rossmann's category tree has two useful levels:

1. **Level 2 (navigation)**: the 7 main sections shown in the site menu
   (Makyaj, Cilt Bakımı, Kişisel Bakım, Anne & Bebek, Sağlık & Gıda,
   Temizlik, Ev & Yaşam).  These are the IDs listed in
   ``config.TOP_LEVEL_CATEGORIES``.
2. **Level 2+ campaign categories**: dozens of brand / campaign buckets
   (e.g. "Flormar Sepet Kampanyası") whose products are strict subsets
   of the navigation categories.  Scraping them would only duplicate work.

Following the same convention as the Bauhaus / Koton scrapers, we restrict
scraping to the navigation categories.  For each one we issue a cheap
``products(filter: {category_id: ...}, pageSize: 1)`` probe just to fetch
``total_count`` so we can report progress correctly.
"""

import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Return a new ``requests.Session`` pre-configured with default headers."""
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _probe_total_count(
    session: requests.Session,
    category_id: str,
) -> Optional[int]:
    """Return the ``total_count`` for a category id using a cheap GraphQL probe.

    Sends a ``pageSize: 1`` products query and reads back ``total_count``.
    Returns ``None`` if all retries are exhausted or the API rejects the query.
    """
    query = (
        "query($id: String!) {"
        "  products(filter: {category_id: {eq: $id}}, pageSize: 1, currentPage: 1) {"
        "    total_count"
        "  }"
        "}"
    )
    payload = {"query": query, "variables": {"id": str(category_id)}}

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.post(config.GRAPHQL_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data and data["errors"]:
                logger.warning(
                    "GraphQL errors while probing category %s: %s",
                    category_id, data["errors"],
                )
                return None
            return int(
                data.get("data", {}).get("products", {}).get("total_count") or 0
            )
        except (requests.RequestException, ValueError) as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "Failed to probe total_count for category %s: %s",
                    category_id, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds...", attempt, exc, wait
            )
            time.sleep(wait)
    return None


def fetch_categories(
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """Return the list of Rossmann top-level categories to scrape.

    Reads ``config.TOP_LEVEL_CATEGORIES`` (a curated, hard-coded list of
    navigation categories) and augments each entry with a live
    ``product_count`` probe from the GraphQL endpoint.

    Args
    ----
    session : requests.Session, optional
        Shared session to reuse. A new session is created when ``None``.

    Returns
    -------
    list[dict]
        One dict per category with keys ``id``, ``name``, ``url_key``,
        ``parent_id``, ``parent_name`` and ``product_count``.
    """
    if session is None:
        session = _make_session()

    categories: list[dict] = []
    for top in config.TOP_LEVEL_CATEGORIES:
        count = _probe_total_count(session, top["id"])
        logger.info(
            "Category '%s' (id=%s, url_key=%s) → %s products",
            top["name"], top["id"], top["url_key"],
            "?" if count is None else count,
        )
        categories.append(
            {
                "id":            top["id"],
                "name":          top["name"],
                "url_key":       top["url_key"],
                "parent_id":     None,
                "parent_name":   None,
                "product_count": count,
            }
        )
        # Tiny pause between probes to be polite to the API
        time.sleep(0.2)

    logger.info("Total scrapable categories: %d", len(categories))
    return categories
