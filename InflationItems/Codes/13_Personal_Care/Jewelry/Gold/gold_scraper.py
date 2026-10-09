"""
gold_scraper.py — Live Retail Gold & Precious Metals Scraper for TÜİK CPI Group 1321101

Collects daily retail selling prices of standard gold, jewelry, and precious metal items
in Turkey (Gram Gold, Quarter Gold, Half Gold, Full Gold, Republic Gold, 22K Bracelet,
14K Gold, 18K Gold, Ata Gold, Ziynet Gold, etc.).

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Jewelry/Gold/gold_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import os
import re
import sys
import logging
import urllib.request
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("GoldScraper")

# Target directory
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Jewelry" / "Gold"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_price(price_str: str) -> float:
    """Converts Turkish formatted price string (e.g., '6.604,19') to float."""
    clean = price_str.strip().replace(".", "").replace(",", ".")
    return float(clean)


def fetch_gold_prices() -> list[tuple[str, float]]:
    """
    Fetches real-time retail gold and precious metal prices from live market data.
    Returns a list of (product_name, price) tuples.
    """
    url = "https://canlidoviz.com/altin-fiyatlari"
    logger.info("Fetching gold prices from %s", url)

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        html = response.read().decode("utf-8", errors="ignore")

    # Pattern matches product item name and unit selling price
    pattern = re.compile(
        r'<span\s+itemprop="name"\s+content="([^"]+)".*?'
        r'<span\s+itemprop="price"[^>]*>\s*([0-9.,]+)',
        re.DOTALL
    )

    results = []
    seen = set()

    for match in pattern.finditer(html):
        name = match.group(1).strip()
        raw_price = match.group(2).strip()
        try:
            price = parse_price(raw_price)
            if price > 0 and name not in seen:
                # Filter out cross-currency indices like ONS EUR, Altın Gümüş ratio
                if name in ["Altın Gümüş", "ONS EUR"]:
                    continue
                results.append((name, price))
                seen.add(name)
        except ValueError:
            continue

    return results


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves price pairs to standard CSV format."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"gold_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in data:
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Successfully wrote %d gold products to %s", len(data), out_file)
    return out_file


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gold Price Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Gold Price Scraper for date %s", date_str)

    try:
        items = fetch_gold_prices()
        if not items:
            logger.error("No gold items were parsed. Aborting.")
            sys.exit(1)

        out_path = save_to_csv(items, date_str)
        print(f"Saved {len(items)} items to {out_path}")
    except Exception as exc:
        logger.exception("Gold scraper failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
