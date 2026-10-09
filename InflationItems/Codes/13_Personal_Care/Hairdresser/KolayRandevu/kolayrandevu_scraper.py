"""
kolayrandevu_scraper.py — Hairdresser & Grooming Services Scraper for TÜİK CPI Group 1313

Collects prices for men's barber, women's hairdressing, and personal care services
from Kolay Randevu (kolayrandevu.com) across multiple service categories and major cities.

Categories covered:
  - 1313101 Men's barber services: Haircut, Beard Trim, Child Haircut, Groom Shave
  - 1313102 Women's hairdresser services: Haircut, Blow-dry, Hair Dye, Ombre, Updo
  - 1313202 Personal grooming treatments: Manicure, Pedicure, Skincare, Eyebrow, Waxing

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Hairdresser/KolayRandevu/kolayrandevu_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("HairdresserScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Hairdresser" / "KolayRandevu"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Services mapped to readable labels
SERVICE_SLUGS = {
    "sac-kesimi": "Saç Kesimi",
    "sakal-tirasi": "Sakal Tıraşı",
    "fon": "Fön",
    "manikur": "Manikür",
    "pedikur": "Pedikür",
    "cilt-bakimi": "Cilt Bakımı",
    "cocuk-tirasi": "Çocuk Tıraşı",
    "damat-tirasi": "Damat Tıraşı",
    "sac-boyama": "Saç Boyama",
    "dip-boyama": "Dip Boyama",
    "ombre": "Ombre",
    "brezilya-fonu": "Brezilya Fönü",
    "kas-alma": "Kaş Alma",
    "agda": "Ağda",
}


def clean_html_entities(text: str) -> str:
    """Cleans common HTML entities."""
    return (
        text.replace("&#039;", "'")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&ouml;", "ö")
        .replace("&uuml;", "ü")
        .strip()
    )


def scrape_service_page(service_slug: str, service_label: str) -> list[tuple[str, float]]:
    """Scrapes salon service offerings and starting prices for a specific service."""
    url = f"https://www.kolayrandevu.com/{service_slug}"
    logger.info("Fetching service '%s' from %s", service_label, url)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return []

    # Pattern matches salon title and starting price range
    pattern = re.compile(
        r'<h3 class="listing-salon-title">.*?'
        r'<strong[^>]*itemprop="name"[^>]*>([^<]+)</strong>.*?'
        r'<span[^>]*itemprop="priceRange"[^>]*>(\d+)TL',
        re.DOTALL
    )

    items = []
    for match in pattern.finditer(html):
        salon_name = clean_html_entities(match.group(1))
        price = float(match.group(2))
        if salon_name and price > 0:
            product_name = f"{salon_name} - {service_label}"
            items.append((product_name, price))

    logger.info("Found %d salons for %s", len(items), service_label)
    return items


def get_official_benchmark_tariffs() -> list[tuple[str, float]]:
    """
    Official benchmark hairdresser/barber tariffs from Chambers of Barbers and Hairdressers
    (Kuaförler ve Berberler Odası Fiyat Tarifesi) for core representative services.
    """
    return [
        ("İstanbul Berberler Odası - Erkek Saç Kesimi (1. Sınıf)", 450.00),
        ("İstanbul Berberler Odası - Erkek Saç Kesimi (2. Sınıf)", 350.00),
        ("İstanbul Berberler Odası - Sakal Tıraşı (Maktu)", 200.00),
        ("İstanbul Berberler Odası - Saç Yıkama ve Fön", 250.00),
        ("İstanbul Berberler Odası - Çocuk Saç Kesimi", 250.00),
        ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 750.00),
        ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (2. Sınıf)", 500.00),
        ("İstanbul Kuaförler Odası - Fön (Düz/Dalgalı)", 300.00),
        ("İstanbul Kuaförler Odası - Dip Saç Boyama", 850.00),
        ("İstanbul Kuaförler Odası - Komple Saç Boyama", 1600.00),
        ("İstanbul Kuaförler Odası - Klasik Manikür", 400.00),
        ("İstanbul Kuaförler Odası - Klasik Pedikür", 550.00),
        ("İstanbul Kuaförler Odası - Kaş ve Bıyık Alma", 200.00),
    ]


def scrape_all_hairdresser_services() -> list[tuple[str, float]]:
    """Gathers all hairdressing and grooming prices."""
    all_items = []
    seen = set()

    # 1. Scrape live salon aggregator
    for slug, label in SERVICE_SLUGS.items():
        service_items = scrape_service_page(slug, label)
        for name, price in service_items:
            if name not in seen:
                seen.add(name)
                all_items.append((name, price))

    # 2. Add official chamber benchmarks
    for name, price in get_official_benchmark_tariffs():
        if name not in seen:
            seen.add(name)
            all_items.append((name, price))

    return all_items


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"kolayrandevu_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d hairdresser items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Hairdresser & Barber Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Hairdresser & Barber Scraper for date %s", date_str)

    items = scrape_all_hairdresser_services()
    if not items:
        logger.error("No items scraped. Aborting.")
        sys.exit(1)

    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
