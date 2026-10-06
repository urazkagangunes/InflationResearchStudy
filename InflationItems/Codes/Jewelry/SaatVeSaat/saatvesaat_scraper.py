"""
saatvesaat_scraper.py — Watch Price Scraper for TÜİK CPI Group 1321105 (Wristwatches)

Collects wristwatch retail prices from Saat & Saat (saatvesaat.com.tr), Turkey's largest
watch retailer, covering major brands (Casio, Fossil, Tommy Hilfiger, Lacoste, Seiko, etc.).

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Jewelry/SaatVeSaat/saatvesaat_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SaatVeSaatScraper")

# Directory setup
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Jewelry" / "SaatVeSaat"

SITEMAP_URL = "https://www.saatvesaat.com.tr/media/product_sitemap.xml"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_product_urls(limit: int = 350) -> list[str]:
    """Retrieves watch product URLs from the official product sitemap."""
    logger.info("Fetching product sitemap from %s", SITEMAP_URL)
    req = urllib.request.Request(SITEMAP_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_content = resp.read().decode("utf-8")

    urls = re.findall(r"<loc>([^<]+)</loc>", xml_content)
    logger.info("Found %d total product URLs in sitemap", len(urls))

    # Evenly sample or take first N
    if limit and limit < len(urls):
        step = max(1, len(urls) // limit)
        sampled = urls[::step][:limit]
        logger.info("Sampled %d URLs across the catalog", len(sampled))
        return sampled
    return urls


def fetch_single_watch(url: str) -> tuple[str, float] | None:
    """Fetches a single watch page and extracts name and price from JSON-LD schema."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        json_ld_blocks = re.findall(
            r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )

        for block in json_ld_blocks:
            try:
                data = json.loads(block)
                if data.get("@type") == "Product":
                    name = str(data.get("name", "")).strip()
                    offers = data.get("offers", {})
                    price = float(offers.get("price", 0))
                    if name and price > 0:
                        return name, price
            except Exception:
                continue
    except Exception:
        return None
    return None


def scrape_watches(max_items: int = 350, max_workers: int = 10) -> list[tuple[str, float]]:
    """Scrapes watch products concurrently."""
    urls = get_product_urls(limit=max_items)
    results = []
    seen = set()

    logger.info("Scraping %d watch URLs with %d worker threads...", len(urls), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_single_watch, u): u for u in urls}
        for future in as_completed(future_to_url):
            res = future.result()
            if res:
                name, price = res
                if name not in seen:
                    seen.add(name)
                    results.append((name, price))

    logger.info("Successfully extracted %d watch items", len(results))
    return results


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves products to standard CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"saatvesaat_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved data to %s", out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Saat & Saat Watch Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--max-items", type=int, default=300, help="Maximum number of items to scrape")
    parser.add_argument("--workers", type=int, default=10, help="Worker threads")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Saat & Saat scraper for %s", date_str)

    items = scrape_watches(max_items=args.max_items, max_workers=args.workers)
    if not items:
        logger.error("No items scraped. Aborting.")
        sys.exit(1)

    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} watches to {out_file}")


if __name__ == "__main__":
    main()
