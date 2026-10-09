"""Category discovery for the Golden Rose scraper."""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _category_priority(name: str) -> int:
    return config.TOP_LEVEL_PRIORITY.get(name, 999)


def parse_categories_from_html(
    html: str,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Parse top-level navigation categories from the Golden Rose homepage."""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one("nav#main-menu")
    if nav is None:
        raise RuntimeError("Golden Rose main menu could not be found.")

    categories: list[dict] = []
    seen: set[str] = set()

    for link in nav.select("a.menu-first-title"):
        name = _clean_text(link.get_text(" ", strip=True))
        href = (link.get("href") or "").strip()
        if not name or not href:
            continue

        if not include_promotional and name in config.PROMOTIONAL_CATEGORY_NAMES:
            continue

        url = urljoin(config.HOME_URL, href)
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)

        slug = url.rstrip("/").split("/")[-1]
        categories.append(
            {
                "id": slug,
                "name": name,
                "url": url,
                "priority": _category_priority(name),
                "is_promotional": name in config.PROMOTIONAL_CATEGORY_NAMES,
            }
        )

    if not categories:
        raise RuntimeError("No Golden Rose top-level categories were discovered.")

    categories.sort(key=lambda item: (item["priority"], item["name"].casefold()))
    return categories


def fetch_categories(
    session: Optional[requests.Session] = None,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Fetch and parse Golden Rose top-level catalog categories."""
    if session is None:
        session = _make_session()

    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(config.HOME_URL, timeout=30)
            response.raise_for_status()
            categories = parse_categories_from_html(
                response.text,
                include_promotional=include_promotional,
            )
            logger.info("Discovered %d top-level Golden Rose categories.", len(categories))
            return categories
        except requests.RequestException as exc:
            last_error = exc
            if attempt == config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BACKOFF * attempt)

    raise RuntimeError(f"Golden Rose homepage could not be fetched: {last_error}")
