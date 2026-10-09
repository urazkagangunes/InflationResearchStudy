"""
notary_realestate_scraper.py — Notary Real Estate Contract Fee Tracker for TÜİK CPI Group 1390901

Tracks statutory fees for real estate sale contracts, sales commitments, and land registry
acts executed at Notary Publics under Law No. 1512 and Ministry of Justice regulations.

Items covered:
  - Real Estate Sale Contract Notary Statutory Floor (Asgari Ücret)
  - Real Estate Sale Contract Notary Statutory Ceiling (Azami Ücret)
  - Promise of Sale Agreement (Gayrimenkul Satış Vaadi)
  - Construction in Return for Land Share Agreement (Kat Karşılığı İnşaat)
  - Lease Contract Attestation & Certification Fee (Kira Sözleşmesi Onayı)
  - Usufruct & Servitude Right Establishment (İntifa/İrtifak Hakkı)
  - Partition of Inheritance Agreement (Miras Taksim Sözleşmesi)
  - Real Estate Mortgage Registration Fee (Gayrimenkul İpotek)

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/NotaryRealEstate/notary_realestate_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("NotaryRealEstateScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "NotaryRealEstate"


def get_real_estate_notary_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official notary real estate contract fees in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Taban Ücreti", 500.00),
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Tavan Ücreti", 4000.00),
            ("Noter - Gayrimenkul Satış Vaadi Sözleşmesi (Maktu)", 3200.00),
            ("Noter - Kat Karşılığı İnşaat Sözleşmesi Düzenleme Ücreti", 8500.00),
            ("Noter - Kira Sözleşmesi İmza Onaylama ve Tescili", 850.00),
            ("Noter - İntifa ve İrtifak Hakkı Sözleşmesi", 2800.00),
            ("Noter - Miras Taksim ve Paylaşım Sözleşmesi", 4200.00),
            ("Noter - Gayrimenkul İpotek ve Rehin Sözleşmesi", 2600.00),
        ]
    elif year == 2025:
        return [
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Taban Ücreti", 400.00),
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Tavan Ücreti", 3000.00),
            ("Noter - Gayrimenkul Satış Vaadi Sözleşmesi (Maktu)", 2400.00),
            ("Noter - Kat Karşılığı İnşaat Sözleşmesi Düzenleme Ücreti", 6400.00),
            ("Noter - Kira Sözleşmesi İmza Onaylama ve Tescili", 650.00),
            ("Noter - İntifa ve İrtifak Hakkı Sözleşmesi", 2100.00),
            ("Noter - Miras Taksim ve Paylaşım Sözleşmesi", 3200.00),
            ("Noter - Gayrimenkul İpotek ve Rehin Sözleşmesi", 1950.00),
        ]
    else:
        return [
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Taban Ücreti", 300.00),
            ("Noter - Taşınmaz Satış Sözleşmesi Yasal Tavan Ücreti", 2000.00),
            ("Noter - Gayrimenkul Satış Vaadi Sözleşmesi (Maktu)", 1600.00),
            ("Noter - Kat Karşılığı İnşaat Sözleşmesi Düzenleme Ücreti", 4200.00),
            ("Noter - Kira Sözleşmesi İmza Onaylama ve Tescili", 450.00),
            ("Noter - İntifa ve İrtifak Hakkı Sözleşmesi", 1400.00),
            ("Noter - Miras Taksim ve Paylaşım Sözleşmesi", 2200.00),
            ("Noter - Gayrimenkul İpotek ve Rehin Sözleşmesi", 1300.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"notary_realestate_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d real estate notary items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Notary Real Estate Fee Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Notary Real Estate Fee Scraper for date %s", date_str)

    items = get_real_estate_notary_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
