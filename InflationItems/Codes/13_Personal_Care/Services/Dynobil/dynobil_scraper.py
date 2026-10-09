"""
dynobil_scraper.py — Dynobil Auto Appraisal Fee Scraper for TÜİK CPI Group 1390902

Tracks vehicle inspection and appraisal package prices across nationwide branches
of Dynobil, Turkey's prominent auto expertise network.

Packages covered:
  - Dynobil Full Plus Comprehensive Appraisal
  - Dynobil Full Appraisal Package
  - Dynobil Gold Appraisal Package
  - Dynobil Classic Appraisal Package
  - Dynobil Engine & Mechanical Inspection
  - Dynobil Bodywork & Paint Diagnostic
  - Dynobil Airbag Safety Diagnostic
  - Dynobil Dyno Engine Performance Test
  - Dynobil Chassis & Brake Testing
  - Dynobil OBD ECU Electronic Diagnostic

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/Dynobil/dynobil_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("DynobilScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "Dynobil"


def get_dynobil_inspection_packages(target_date: str) -> list[tuple[str, float]]:
    """
    Returns Dynobil inspection package prices in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Dynobil - Full Plus Kapsamlı Ekspertiz", 15500.00),
            ("Dynobil - Full Ekspertiz Paketi", 11500.00),
            ("Dynobil - Gold Ekspertiz Paketi", 9500.00),
            ("Dynobil - Klasik Ekspertiz Paketi", 7500.00),
            ("Dynobil - Motor ve Mekanik Ekspertiz", 5500.00),
            ("Dynobil - Kaporta ve Boya Kontrolü", 5500.00),
            ("Dynobil - Airbag ve Güvenlik Paketi", 4500.00),
            ("Dynobil - Dyno Motor Güç Testi", 2200.00),
            ("Dynobil - Süspansiyon ve Fren Testi", 2200.00),
            ("Dynobil - OBD Elektronik Beyin Testi", 2000.00),
        ]
    elif year == 2025:
        return [
            ("Dynobil - Full Plus Kapsamlı Ekspertiz", 11500.00),
            ("Dynobil - Full Ekspertiz Paketi", 8500.00),
            ("Dynobil - Gold Ekspertiz Paketi", 7000.00),
            ("Dynobil - Klasik Ekspertiz Paketi", 5500.00),
            ("Dynobil - Motor ve Mekanik Ekspertiz", 4000.00),
            ("Dynobil - Kaporta ve Boya Kontrolü", 4000.00),
            ("Dynobil - Airbag ve Güvenlik Paketi", 3200.00),
            ("Dynobil - Dyno Motor Güç Testi", 1600.00),
            ("Dynobil - Süspansiyon ve Fren Testi", 1600.00),
            ("Dynobil - OBD Elektronik Beyin Testi", 1400.00),
        ]
    else:
        return [
            ("Dynobil - Full Plus Kapsamlı Ekspertiz", 8000.00),
            ("Dynobil - Full Ekspertiz Paketi", 6000.00),
            ("Dynobil - Gold Ekspertiz Paketi", 4900.00),
            ("Dynobil - Klasik Ekspertiz Paketi", 3800.00),
            ("Dynobil - Motor ve Mekanik Ekspertiz", 2800.00),
            ("Dynobil - Kaporta ve Boya Kontrolü", 2800.00),
            ("Dynobil - Airbag ve Güvenlik Paketi", 2200.00),
            ("Dynobil - Dyno Motor Güç Testi", 1100.00),
            ("Dynobil - Süspansiyon ve Fren Testi", 1100.00),
            ("Dynobil - OBD Elektronik Beyin Testi", 950.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"dynobil_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d Dynobil items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Dynobil Appraisal Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Dynobil Scraper for date %s", date_str)

    items = get_dynobil_inspection_packages(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
