"""Category discovery for the Karaca scraper."""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _main_category_priority(name: str) -> int:
    return config.MAIN_CATEGORY_PRIORITY.get(name, 999)


def _normalise_url(href: str) -> str:
    url = urljoin(config.HOME_URL, href)
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def _is_listing(node: dict, depth: int) -> bool:
    if not node.get("webUrl"):
        return False
    link_type = node.get("linkType") or ""
    # Sub-menu entries of the web menu often carry no link type but still
    # point at product listings; landing and brand pages are typed.
    return link_type == config.PLP_LINK_TYPE or (depth > 0 and not link_type)


def _walk(node: dict, depth: int = 0):
    yield node, depth
    for child in node.get("children") or []:
        yield from _walk(child, depth + 1)


def parse_categories_from_menu(
    payload: dict,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Parse every product listing of Karaca's navigation menu JSON.

    The site's search only returns products assigned to the requested
    category itself, so a group listing misses products that are assigned to
    its sub-categories only (and the reverse). Every menu level is scraped
    and products are deduplicated afterwards.
    """
    items = ((payload or {}).get("data") or {}).get("items")
    if not items:
        raise RuntimeError("Karaca navigation menu is empty or has an unknown format.")

    by_url: dict[str, dict] = {}
    order = 0

    for item in items:
        main_category = _clean_text(item.get("title") or "")
        if not main_category:
            continue
        is_promotional = main_category in config.PROMOTIONAL_MAIN_CATEGORIES
        if not include_promotional and is_promotional:
            continue

        for node, depth in _walk(item):
            if not _is_listing(node, depth):
                continue
            url = _normalise_url(node["webUrl"])
            path = urlparse(url).path
            if path in config.NON_LISTING_PATHS or url in by_url:
                continue
            by_url[url] = {
                "id": path.rstrip("/").split("/")[-1],
                "name": _clean_text(node.get("title") or "") or main_category,
                "url": url,
                "main_category": main_category,
                "main_priority": _main_category_priority(main_category),
                "priority": order,
                "nav_id": str(node.get("linkId") or ""),
                "group_id": str(item.get("linkId") or ""),
                "depth": depth,
                "is_promotional": is_promotional,
            }
            order += 1

    categories = sorted(
        by_url.values(),
        key=lambda item: (item["main_priority"], item["priority"], item["name"].casefold()),
    )
    if not categories:
        raise RuntimeError("No Karaca listing categories were discovered.")
    return categories


def fetch_categories(
    session: Optional[requests.Session] = None,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Fetch and parse the Karaca listing categories of the navigation menu."""
    if session is None:
        session = _make_session()

    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(config.MENU_URL, timeout=30)
            response.raise_for_status()
            categories = parse_categories_from_menu(
                response.json(),
                include_promotional=include_promotional,
            )
            logger.info("Discovered %d Karaca navigation categories.", len(categories))
            return categories
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BACKOFF * attempt)

    raise RuntimeError(f"Karaca navigation menu could not be fetched: {last_error}")
