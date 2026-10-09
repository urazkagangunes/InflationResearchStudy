"""
Utility functions - parsing and fetching helpers.

WHY curl_cffi instead of requests?
    hapeloglu.com sits behind Cloudflare, which fingerprints the TLS
    handshake. Python's `requests` (via urllib3) has a recognizable
    TLS signature that Cloudflare blocks, returning an empty/challenge
    page with 0 products. curl_cffi uses libcurl compiled to mimic
    Chrome's exact TLS fingerprint, so Cloudflare treats it as a
    real browser.

    pip install curl_cffi
"""

import re
import time
import logging
from typing import Optional

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

from src.config import HEADERS, MAX_RETRIES, REQUEST_DELAY


logger = logging.getLogger(__name__)


def setup_logger():
    """Configure logging for the project."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_price(price_text: str) -> Optional[float]:
    """
    Turkish price string -> float.
        '134,90 TL'    -> 134.9
        '1.250,00 TL'  -> 1250.0
    """
    if not price_text:
        return None
    cleaned = re.sub(r"(TL|KDV\s*Dahil)", "", price_text).strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        logger.warning(f"Could not parse price: '{price_text}'")
        return None


def create_session() -> curl_requests.Session:
    """
    Create a session that impersonates Chrome's TLS fingerprint.
    This is the key to bypassing Cloudflare.
    """
    return curl_requests.Session(impersonate="chrome")


def fetch_page(url: str, session: curl_requests.Session) -> Optional[BeautifulSoup]:
    """GET a page with retries and polite delay."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Normal distribution sleep (mean = config.REQUEST_DELAY, stdev = config.REQUEST_STDEV)
            # Ensure delay is at least config.REQUEST_FLOOR
            import random
            from src import config as cfg
            delay = max(cfg.REQUEST_FLOOR, random.normalvariate(cfg.REQUEST_DELAY, cfg.REQUEST_STDEV))
            time.sleep(delay)
            
            response = session.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Detect Cloudflare challenge page (safety check)
            title = soup.title
            if title and title.string and "just a moment" in title.string.lower():
                logger.warning(f"  Cloudflare challenge on attempt {attempt}")
                time.sleep(5)
                continue

            return soup

        except Exception as e:
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(cfg.RETRY_BACKOFF * attempt)

    logger.error(f"  FAILED after {MAX_RETRIES} attempts: {url}")
    return None


def get_total_product_count(soup: BeautifulSoup) -> int:
    """Extract total product count from 'X Ürün' text on page."""
    for el in soup.find_all(["span", "div", "p"]):
        text = el.get_text(strip=True)
        match = re.match(r"^(\d+)\s*Ürün", text)
        if match and len(text) < 50:
            return int(match.group(1))
    return 0
