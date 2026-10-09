"""
Samsung Category Discovery Module
=================================

Returns the list of Samsung Türkiye top-level categories that the
product fetcher will iterate through.

Public Interface
----------------
fetch_categories(session=None) -> list[dict]
    Returns the curated list of categories defined in
    :data:`config.TOP_LEVEL_CATEGORIES`, augmented with a live
    ``product_count`` probe obtained from the pfv2 JSON endpoint.
    Each dict has the shape::

        {
          "id":            "smartphones",          # url-safe slug
          "type":          "01010000",             # pfCategoryTypeCode
          "name":          "Smartphones",
          "landing_path":  "/tr/smartphones/all-smartphones/",
          "parent_id":     None,                   # always None
          "parent_name":   None,
          "product_count": 44,                     # None if probe failed
        }

Discovery Strategy
------------------
Samsung Türkiye's navigation tree exposes an "all-<segment>" landing page
for each top-level category.  Each of those pages carries a hidden input
``pfCategoryTypeCode`` whose 8-digit value is the only identifier the
public pfv2 endpoint consumes.  We keep the curated mapping in
``config.py`` (see the module docstring there for how the codes were
harvested) and just augment each entry with a live "totalRecord" count.

Sub-category pages (e.g. ``/tr/smartphones/galaxy-s/``) are strict
subsets of their parent, so scraping only the "all" pages guarantees
full coverage without duplicating SKUs.
"""

import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Return a fresh ``requests.Session`` pre-loaded with default headers."""
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _probe_total_count(
    session: requests.Session,
    type_code: str,
) -> Optional[int]:
    """Return the ``totalRecord`` count for a category via a cheap pfv2 probe.

    Sends a ``num=1`` request and reads ``totalRecord`` off the
    ``common`` section of the response.  Returns ``None`` when every
    retry attempt fails (network error / non-200 response / malformed
    payload).

    Note
    ----
    ``totalRecord`` counts product *families* (e.g. "Galaxy S25"),
    not SKUs — each family typically has several colour / capacity
    variants.  We report it verbatim because it's what the Samsung
    site itself shows next to the category header and is cheapest
    to obtain.
    """
    params = {
        "type":             str(type_code),
        "siteCode":         config.SITE_CODE,
        "start":            1,
        "num":              1,
        "sort":             config.DEFAULT_SORT,
        "onlyFilterInfoYN": "N",
    }
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(
                config.PRODUCT_FINDER_URL, params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json() or {}
            rd = (data.get("response") or {}).get("resultData")
            if not rd:
                return None
            total = (rd.get("common") or {}).get("totalRecord")
            try:
                return int(total) if total is not None else 0
            except (TypeError, ValueError):
                return 0
        except (requests.RequestException, ValueError) as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "Failed to probe totalRecord for type=%s: %s",
                    type_code, exc,
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
    """Return the list of Samsung Türkiye top-level categories to scrape.

    Reads :data:`config.TOP_LEVEL_CATEGORIES` (curated) and augments
    each entry with a live ``product_count`` obtained from the pfv2
    endpoint, following the same approach as the Rossmann / Vivense
    scrapers.

    Args
    ----
    session : requests.Session, optional
        Shared session to reuse.  A new session is created when
        ``None``.

    Returns
    -------
    list[dict]
        One dict per category with keys ``id``, ``type``, ``name``,
        ``landing_path``, ``parent_id``, ``parent_name`` and
        ``product_count``.
    """
    if session is None:
        session = _make_session()

    categories: list[dict] = []
    for top in config.TOP_LEVEL_CATEGORIES:
        count = _probe_total_count(session, top["type"])
        logger.info(
            "Category '%s' (type=%s) → %s product families",
            top["name"], top["type"],
            "?" if count is None else count,
        )
        categories.append(
            {
                "id":            top["id"],
                "type":          top["type"],
                "name":          top["name"],
                "landing_path":  top["landing_path"],
                "parent_id":     None,
                "parent_name":   None,
                "product_count": count,
            }
        )
        # Tiny pause between probes to be polite to the API.
        time.sleep(0.2)

    logger.info("Total scrapable categories: %d", len(categories))
    return categories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for c in fetch_categories():
        print(f"{c['type']:<10} {c['id']:<22} {c['product_count']:<6} {c['name']}")
