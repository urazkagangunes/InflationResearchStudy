"""
altinbas_scraper.py — Retail Gold Jewellery Scraper for TÜİK CPI Group 1321101

Collects retail selling prices of gold jewelry products (necklaces, bracelets, rings,
earrings, wedding bands) from Altınbaş (altinbas.com), one of Turkey's leading jewelry retail chains.

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Jewelry/Altinbas/altinbas_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("AltinbasScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Jewelry" / "Altinbas"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

import time

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

try:
    import requests as std_requests
except ImportError:
    std_requests = None

CATEGORY_URLS = [
    f"https://www.altinbas.com/altin?sayfa={p}" for p in range(1, 6)
]


def fetch_html(url: str, timeout: int = 15) -> str:
    """Fetches URL HTML using curl_cffi with Chrome impersonation, falling back to requests/urllib."""
    if curl_requests is not None:
        resp = curl_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=timeout)
        resp.raise_for_status()
        return resp.text

    if std_requests is not None:
        resp = std_requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def scrape_altinbas_products() -> list[tuple[str, float]]:
    """Scrapes gold jewelry product names and selling prices from Altınbaş catalog pages with retry logic."""
    results = []
    seen = set()

    for url in CATEGORY_URLS:
        for attempt in range(1, 4):
            logger.info("Fetching Altınbaş page (attempt %d/3): %s", attempt, url)
            try:
                html = fetch_html(url, timeout=15)

                # Parse products from data-googletag attributes
                matches = re.findall(
                    r"name:'([^']+)'.*?id:'([^']+)'.*?sale_price:'([0-9.]+)'",
                    html
                )
                if matches:
                    for name, pid, price_str in matches:
                        full_name = f"Altınbaş {name.strip()} ({pid.strip()})"
                        try:
                            price = float(price_str)
                            if price > 0 and full_name not in seen:
                                seen.add(full_name)
                                results.append((full_name, price))
                        except ValueError:
                            continue
                    break  # Success, exit retry loop
                else:
                    logger.warning("Empty matches on %s (attempt %d)", url, attempt)
                    time.sleep(3 * attempt)
            except Exception as exc:
                logger.warning("Failed to fetch %s (attempt %d): %s", url, attempt, exc)
                time.sleep(3 * attempt)

        time.sleep(2.0)  # Gentle 2-second delay between catalog pages

    logger.info("Extracted %d unique gold jewelry items from Altınbaş", len(results))
    return results


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to standard CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"altinbas_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Altınbaş Jewelry Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Altınbaş Scraper for date %s", date_str)

    items = scrape_altinbas_products()
    if not items:
        logger.error("No items scraped from Altınbaş. Aborting.")
        sys.exit(1)

    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
