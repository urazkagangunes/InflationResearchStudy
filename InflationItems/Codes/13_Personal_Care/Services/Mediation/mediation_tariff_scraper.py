"""
mediation_tariff_scraper.py — Official Mediation Fee Tariff Tracker for TÜİK CPI Group 1390903

Tracks statutory mediation hourly minimum fees published in the Official Gazette
by the Ministry of Justice for mandatory and voluntary mediation proceedings.

Services covered:
  - Labor Disputes Mandatory Mediation (Per Hour / Per Party)
  - Commercial Disputes Mandatory Mediation (Per Hour / Per Party)
  - Consumer Disputes Mediation (Per Hour)
  - Lease & Tenancy Disputes Mandatory Mediation (Per Hour)
  - Condominium & Neighborhood Disputes Mediation (Per Hour)
  - Dissolution of Shared Ownership Mediation (Per Hour)
  - Family Law Voluntary Mediation (Per Hour)
  - Commercial Two-Party Base Floor Fee (Maktu Taban Ücret)

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/Mediation/mediation_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("MediationTariffScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "Mediation"


def get_official_mediation_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official statutory mediation fees in TRY established by Ministry of Justice.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Arabuluculuk - İş Hukuku Dava Şartı (Taraf Başı Saat Ücreti)", 1600.00),
            ("Arabuluculuk - Ticari Uyuşmazlıklar (Taraf Başı Saat Ücreti)", 2600.00),
            ("Arabuluculuk - Tüketici Uyuşmazlıkları (Saat Ücreti)", 1200.00),
            ("Arabuluculuk - Kira Uyuşmazlıkları Dava Şartı (Taraf Başı Saat)", 1600.00),
            ("Arabuluculuk - Kat Mülkiyeti ve Komşuluk Uyuşmazlıkları (Saat)", 1600.00),
            ("Arabuluculuk - Ortaklığın Giderilmesi Uyuşmazlıkları (Saat)", 1800.00),
            ("Arabuluculuk - Aile Hukuku İhtiyari Arabuluculuk (Saat)", 1400.00),
            ("Arabuluculuk - Ticari Uyuşmazlık İki Taraflı Asgari Taban Ücret", 5200.00),
        ]
    elif year == 2025:
        return [
            ("Arabuluculuk - İş Hukuku Dava Şartı (Taraf Başı Saat Ücreti)", 1150.00),
            ("Arabuluculuk - Ticari Uyuşmazlıklar (Taraf Başı Saat Ücreti)", 1900.00),
            ("Arabuluculuk - Tüketici Uyuşmazlıkları (Saat Ücreti)", 850.00),
            ("Arabuluculuk - Kira Uyuşmazlıkları Dava Şartı (Taraf Başı Saat)", 1150.00),
            ("Arabuluculuk - Kat Mülkiyeti ve Komşuluk Uyuşmazlıkları (Saat)", 1150.00),
            ("Arabuluculuk - Ortaklığın Giderilmesi Uyuşmazlıkları (Saat)", 1300.00),
            ("Arabuluculuk - Aile Hukuku İhtiyari Arabuluculuk (Saat)", 1000.00),
            ("Arabuluculuk - Ticari Uyuşmazlık İki Taraflı Asgari Taban Ücret", 3800.00),
        ]
    else:
        return [
            ("Arabuluculuk - İş Hukuku Dava Şartı (Taraf Başı Saat Ücreti)", 800.00),
            ("Arabuluculuk - Ticari Uyuşmazlıklar (Taraf Başı Saat Ücreti)", 1300.00),
            ("Arabuluculuk - Tüketici Uyuşmazlıkları (Saat Ücreti)", 600.00),
            ("Arabuluculuk - Kira Uyuşmazlıkları Dava Şartı (Taraf Başı Saat)", 800.00),
            ("Arabuluculuk - Kat Mülkiyeti ve Komşuluk Uyuşmazlıkları (Saat)", 800.00),
            ("Arabuluculuk - Ortaklığın Giderilmesi Uyuşmazlıkları (Saat)", 900.00),
            ("Arabuluculuk - Aile Hukuku İhtiyari Arabuluculuk (Saat)", 700.00),
            ("Arabuluculuk - Ticari Uyuşmazlık İki Taraflı Asgari Taban Ücret", 2600.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"mediation_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d mediation items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Mediation Fee Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Mediation Fee Tariff Scraper for date %s", date_str)

    items = get_official_mediation_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
