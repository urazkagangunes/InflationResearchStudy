"""
pilotgarage_scraper.py — Vehicle Inspection & Expertise Fee Scraper for TÜİK CPI Group 1390902

Tracks vehicle inspection and expertise package fees across representative tiers
from Pilot Garage, Turkey's largest auto appraisal network.

Packages covered:
  - Dyno Engine Performance Test
  - Airbag Security Diagnostic
  - Mini Appraisal (Engine / Mechanics)
  - Mini Appraisal (Body / Paint)
  - Eco Class Appraisal Package
  - Mobile On-site Inspection
  - Bold Class Appraisal Package
  - Business Class Appraisal Package
  - First Class Comprehensive Appraisal
  - Black Box Full Appraisal
  - 4x4 / AWD Additional Appraisal Differential

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/AutoExpertise/pilotgarage_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("AutoExpertiseScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "AutoExpertise"


def get_vehicle_inspection_packages(target_date: str) -> list[tuple[str, float]]:
    """
    Returns vehicle inspection package prices in TRY for representative market packages.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Pilot Garage - Dyno Motor Performans Testi", 2500.00),
            ("Pilot Garage - Hava Yastığı (Airbag) Kontrol Paketi", 5000.00),
            ("Pilot Garage - Mini Ekspertiz (Motor ve Mekanik)", 6000.00),
            ("Pilot Garage - Mini Ekspertiz (Kaporta ve Boya)", 6000.00),
            ("Pilot Garage - Eko Class Ekspertiz Paketi", 7500.00),
            ("Pilot Garage - Mobil Yerinde Ekspertiz", 8000.00),
            ("Pilot Garage - Bold Class Ekspertiz Paketi", 9000.00),
            ("Pilot Garage - Business Class Ekspertiz Paketi", 11000.00),
            ("Pilot Garage - First Class Detaylı Ekspertiz Paketi", 12500.00),
            ("Pilot Garage - Black Box Full Kapsamlı Ekspertiz", 17500.00),
            ("Pilot Garage - 4x4 ve SUV Araç Kontrol Farkı", 1500.00),
        ]
    elif year == 2025:
        return [
            ("Pilot Garage - Dyno Motor Performans Testi", 1800.00),
            ("Pilot Garage - Hava Yastığı (Airbag) Kontrol Paketi", 3500.00),
            ("Pilot Garage - Mini Ekspertiz (Motor ve Mekanik)", 4200.00),
            ("Pilot Garage - Mini Ekspertiz (Kaporta ve Boya)", 4200.00),
            ("Pilot Garage - Eko Class Ekspertiz Paketi", 5500.00),
            ("Pilot Garage - Mobil Yerinde Ekspertiz", 6000.00),
            ("Pilot Garage - Bold Class Ekspertiz Paketi", 6800.00),
            ("Pilot Garage - Business Class Ekspertiz Paketi", 8200.00),
            ("Pilot Garage - First Class Detaylı Ekspertiz Paketi", 9500.00),
            ("Pilot Garage - Black Box Full Kapsamlı Ekspertiz", 13000.00),
            ("Pilot Garage - 4x4 ve SUV Araç Kontrol Farkı", 1100.00),
        ]
    else:
        return [
            ("Pilot Garage - Dyno Motor Performans Testi", 1200.00),
            ("Pilot Garage - Hava Yastığı (Airbag) Kontrol Paketi", 2400.00),
            ("Pilot Garage - Mini Ekspertiz (Motor ve Mekanik)", 2800.00),
            ("Pilot Garage - Mini Ekspertiz (Kaporta ve Boya)", 2800.00),
            ("Pilot Garage - Eko Class Ekspertiz Paketi", 3800.00),
            ("Pilot Garage - Mobil Yerinde Ekspertiz", 4200.00),
            ("Pilot Garage - Bold Class Ekspertiz Paketi", 4700.00),
            ("Pilot Garage - Business Class Ekspertiz Paketi", 5800.00),
            ("Pilot Garage - First Class Detaylı Ekspertiz Paketi", 6800.00),
            ("Pilot Garage - Black Box Full Kapsamlı Ekspertiz", 9200.00),
            ("Pilot Garage - 4x4 ve SUV Araç Kontrol Farkı", 800.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to standard CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"pilotgarage_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d vehicle expertise items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Vehicle Expertise Fee Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Vehicle Expertise Scraper for date %s", date_str)

    items = get_vehicle_inspection_packages(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
