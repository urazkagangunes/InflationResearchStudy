"""
Utility functions - reusable helpers for parsing and fetching.

Happy Center uses Cloudflare CDN but does NOT block Python requests,
so standard requests library works fine (no curl_cffi needed).
"""

import os
import re
import time
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.config import HEADERS, MAX_RETRIES, REQUEST_DELAY, OUTPUT_DIR


logger = logging.getLogger(__name__)


def setup_logger():
    """Configure logging: console + file output."""
    log_dir = os.path.join(OUTPUT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "scraper.log")

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

    logger.info(f"Logging to: {log_file}")


def parse_price(price_text: str) -> Optional[float]:
    """
    Turkish price string -> float.

    Examples:
        '94,25 TL'      -> 94.25
        '1.250,00 TL'   -> 1250.0
        '302,45'         -> 302.45
    """
    if not price_text:
        return None
    cleaned = re.sub(r"(TL|₺)", "", price_text).strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        logger.warning(f"Could not parse price: '{price_text}'")
        return None


def fetch_page(url: str, session: requests.Session) -> Optional[BeautifulSoup]:
    """
    GET a page with retry logic and polite delay.
    Returns parsed BeautifulSoup or None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(REQUEST_DELAY)
            response = session.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Cloudflare challenge check (unlikely but just in case)
            if soup.title and soup.title.string and "just a moment" in soup.title.string.lower():
                logger.warning(f"  Cloudflare challenge on attempt {attempt}")
                if attempt < MAX_RETRIES:
                    time.sleep(5)
                continue

            return soup

        except requests.RequestException as e:
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY * attempt)

    logger.error(f"  FAILED after {MAX_RETRIES} attempts: {url}")
    return None


def get_last_page_number(soup: BeautifulSoup) -> int:
    """
    Extract the last page number from pagination links.

    Happy Center pagination has a '» Son' (Last) link with ?page=N.
    Falls back to finding the highest ?page= value in any link.
    """
    # Strategy 1: Find the "Son" (Last) pagination link
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        if "Son" in text:
            match = re.search(r"page=(\d+)", a_tag["href"])
            if match:
                return int(match.group(1))

    # Strategy 2: Find highest page number in any pagination link
    max_page = 1
    for a_tag in soup.find_all("a", href=True):
        match = re.search(r"[?&]page=(\d+)", a_tag["href"])
        if match:
            page_num = int(match.group(1))
            if page_num > max_page:
                max_page = page_num

    return max_page
