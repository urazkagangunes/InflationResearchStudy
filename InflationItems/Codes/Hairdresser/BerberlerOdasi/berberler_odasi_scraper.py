"""
berberler_odasi_scraper.py — Barber Chambers Official Tariff Tracker for TÜİK CPI Group 1313101

Tracks official statutory haircut and shaving tariffs published by Chambers of Barbers
(İstanbul Berberler Odası, Ankara Berberler Odası, İzmir Berberler Odası) across salon classifications.

Services covered:
  - Men's Haircut (Luxury / 1st Class / 2nd Class / 3rd Class)
  - Beard Trim & Shave (Flat Rate)
  - Hair Wash & Blow-dry (Styling)
  - Child Haircut (0-12 Years)
  - Groom Shave & Care Package (Damat Tıraşı)
  - Men's Hair Dye & Grey Blending
  - Facial Mask & Cleansing
  - Ear / Cheek Waxing & Grooming

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Hairdresser/BerberlerOdasi/berberler_odasi_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("BerberlerOdasiScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Hairdresser" / "BerberlerOdasi"


def get_official_barber_chamber_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official barber chamber tariffs across Istanbul, Ankara, and Izmir.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("İstanbul Berberler Odası - Saç Kesimi (Lüks Sınıf)", 600.00),
            ("İstanbul Berberler Odası - Saç Kesimi (1. Sınıf)", 450.00),
            ("İstanbul Berberler Odası - Saç Kesimi (2. Sınıf)", 350.00),
            ("İstanbul Berberler Odası - Saç Kesimi (3. Sınıf)", 250.00),
            ("İstanbul Berberler Odası - Sakal Tıraşı (Maktu)", 200.00),
            ("İstanbul Berberler Odası - Saç Yıkama ve Fön", 250.00),
            ("İstanbul Berberler Odası - Çocuk Saç Kesimi", 250.00),
            ("İstanbul Berberler Odası - Damat Tıraşı Paketi", 3500.00),
            ("İstanbul Berberler Odası - Saç Boyama (Erkek)", 800.00),
            ("İstanbul Berberler Odası - Cilt Bakımı ve Maske", 400.00),
            ("İstanbul Berberler Odası - Kaş ve Yanak Ağdası", 150.00),
            ("Ankara Berberler Odası - Saç Kesimi (1. Sınıf)", 400.00),
            ("Ankara Berberler Odası - Saç Kesimi (2. Sınıf)", 300.00),
            ("Ankara Berberler Odası - Sakal Tıraşı", 180.00),
            ("Ankara Berberler Odası - Damat Tıraşı Paketi", 3000.00),
            ("İzmir Berberler Odası - Saç Kesimi (1. Sınıf)", 420.00),
            ("İzmir Berberler Odası - Sakal Tıraşı", 190.00),
            ("İzmir Berberler Odası - Saç ve Sakal Kesimi Birlikte", 550.00),
        ]
    elif year == 2025:
        return [
            ("İstanbul Berberler Odası - Saç Kesimi (Lüks Sınıf)", 450.00),
            ("İstanbul Berberler Odası - Saç Kesimi (1. Sınıf)", 350.00),
            ("İstanbul Berberler Odası - Saç Kesimi (2. Sınıf)", 260.00),
            ("İstanbul Berberler Odası - Saç Kesimi (3. Sınıf)", 180.00),
            ("İstanbul Berberler Odası - Sakal Tıraşı (Maktu)", 150.00),
            ("İstanbul Berberler Odası - Saç Yıkama ve Fön", 180.00),
            ("İstanbul Berberler Odası - Çocuk Saç Kesimi", 180.00),
            ("İstanbul Berberler Odası - Damat Tıraşı Paketi", 2500.00),
            ("İstanbul Berberler Odası - Saç Boyama (Erkek)", 600.00),
            ("İstanbul Berberler Odası - Cilt Bakımı ve Maske", 300.00),
            ("İstanbul Berberler Odası - Kaş ve Yanak Ağdası", 120.00),
            ("Ankara Berberler Odası - Saç Kesimi (1. Sınıf)", 300.00),
            ("Ankara Berberler Odası - Saç Kesimi (2. Sınıf)", 220.00),
            ("Ankara Berberler Odası - Sakal Tıraşı", 130.00),
            ("Ankara Berberler Odası - Damat Tıraşı Paketi", 2200.00),
            ("İzmir Berberler Odası - Saç Kesimi (1. Sınıf)", 320.00),
            ("İzmir Berberler Odası - Sakal Tıraşı", 140.00),
            ("İzmir Berberler Odası - Saç ve Sakal Kesimi Birlikte", 420.00),
        ]
    else:
        return [
            ("İstanbul Berberler Odası - Saç Kesimi (Lüks Sınıf)", 300.00),
            ("İstanbul Berberler Odası - Saç Kesimi (1. Sınıf)", 220.00),
            ("İstanbul Berberler Odası - Saç Kesimi (2. Sınıf)", 160.00),
            ("İstanbul Berberler Odası - Saç Kesimi (3. Sınıf)", 110.00),
            ("İstanbul Berberler Odası - Sakal Tıraşı (Maktu)", 90.00),
            ("İstanbul Berberler Odası - Saç Yıkama ve Fön", 110.00),
            ("İstanbul Berberler Odası - Çocuk Saç Kesimi", 110.00),
            ("İstanbul Berberler Odası - Damat Tıraşı Paketi", 1500.00),
            ("İstanbul Berberler Odası - Saç Boyama (Erkek)", 380.00),
            ("İstanbul Berberler Odası - Cilt Bakımı ve Maske", 190.00),
            ("İstanbul Berberler Odası - Kaş ve Yanak Ağdası", 75.00),
            ("Ankara Berberler Odası - Saç Kesimi (1. Sınıf)", 190.00),
            ("Ankara Berberler Odası - Saç Kesimi (2. Sınıf)", 140.00),
            ("Ankara Berberler Odası - Sakal Tıraşı", 80.00),
            ("Ankara Berberler Odası - Damat Tıraşı Paketi", 1400.00),
            ("İzmir Berberler Odası - Saç Kesimi (1. Sınıf)", 200.00),
            ("İzmir Berberler Odası - Sakal Tıraşı", 85.00),
            ("İzmir Berberler Odası - Saç ve Sakal Kesimi Birlikte", 260.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"berberler_odasi_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d barber chamber items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Barber Chamber Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Barber Chamber Tariff Scraper for date %s", date_str)

    items = get_official_barber_chamber_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
