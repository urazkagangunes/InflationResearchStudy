"""
Vivense Category Discovery Module
=================================

Returns the list of top-level Vivense navigation categories that the
product fetcher will iterate through.

Public Interface
----------------
fetch_categories(session=None) -> list[dict]
    Returns the curated categories of ``config.TOP_LEVEL_CATEGORIES``
    followed by the category-sitemap listings.  Each dict has the shape::

        {
          "id":          "oturma-odasi-mobilyalari",
          "name":        "Oturma Odası",
          "url":         "https://www.vivense.com/oturma-odasi-mobilyalari.html",
          "parent_id":   None,
          "parent_name": None,
          "product_count": None,   # not exposed by the public site
        }

Discovery Strategy
------------------
Vivense renders all product cards directly into category HTML; there is
no public API to enumerate categories.  Rather than scraping the home-page
mega-menu (which mixes campaign / promo links with real categories), we
use a small hard-coded list of the top-level navigation buckets that map
1-to-1 to URLs of the form ``/<slug>.html``.

The top-level listings show only one member of many product families, so
every category of the site's category sitemap (``config.CATEGORY_SITEMAP_URL``,
advertised in robots.txt) is appended after the curated list.  Showroom
pages and service / fee listings are skipped.  When the sitemap cannot be
read, the curated list alone is returned and a warning is logged.

The same approach is used by the Rossmann scraper, which also relies on
a curated ``TOP_LEVEL_CATEGORIES`` list in its config module.
"""

import logging
import re
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Create a fresh ``requests.Session`` pre-loaded with default headers.

    Provided for API parity with the other category fetchers in this
    repository (e.g. Migros, Rossmann) — Vivense's curated category
    list does not actually require any HTTP calls, but the session
    parameter is kept on :func:`fetch_categories` for symmetry.

    Returns
    -------
    requests.Session
        A session with :data:`config.DEFAULT_HEADERS` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _sitemap_category_urls(session: requests.Session) -> list[str]:
    """Return the product-listing URLs of the category sitemap.

    Returns an empty list when the sitemap cannot be fetched.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(config.CATEGORY_SITEMAP_URL, timeout=30)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            logger.warning("Category sitemap attempt %d/%d failed: %s",
                           attempt, config.MAX_RETRIES, exc)
            if attempt == config.MAX_RETRIES:
                return []
            time.sleep(config.RETRY_BACKOFF * attempt)

    skip = re.compile(config.NON_GOODS_SLUG_PATTERN)
    urls = []
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text):
        path = loc.replace(config.BASE_URL, "")
        slug = path.rsplit("/", 1)[-1]
        if (not slug.endswith(".html") or "/mobilya-showroom" in path
                or skip.search(slug)):
            continue
        urls.append(loc)
    return urls


def fetch_categories(
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """Return the list of Vivense categories to scrape.

    Reads :data:`config.TOP_LEVEL_CATEGORIES` (a curated list), appends the
    category-sitemap listings not already in it and returns one dict per
    category in the canonical scraper schema.

    Args
    ----
    session : requests.Session, optional
        Session used to read the category sitemap.  Created when ``None``.

    Returns
    -------
    list[dict]
        One dict per category with keys ``id``, ``name``, ``url``,
        ``parent_id``, ``parent_name`` and ``product_count``.
    """
    if session is None:
        session = _make_session()

    categories: list[dict] = []
    for top in config.TOP_LEVEL_CATEGORIES:
        categories.append(
            {
                "id":            top["id"],
                "name":          top["name"],
                "url":           top["url"],
                "parent_id":     None,
                "parent_name":   None,
                "product_count": None,
            }
        )

    known = {c["url"] for c in categories}
    sitemap_urls = _sitemap_category_urls(session)
    if not sitemap_urls:
        logger.warning("Category sitemap unavailable; using the curated "
                       "top-level list only.")
    for url in sitemap_urls:
        if url in known:
            continue
        known.add(url)
        slug = url.rsplit("/", 1)[-1][:-len(".html")]
        categories.append(
            {
                "id":            slug,
                "name":          slug,
                "url":           url,
                "parent_id":     None,
                "parent_name":   None,
                "product_count": None,
            }
        )

    logger.info("Discovered %d Vivense categories (%d curated top-level).",
                len(categories), len(config.TOP_LEVEL_CATEGORIES))
    return categories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for c in fetch_categories():
        print(f"{c['id']:<40} {c['name']}")
