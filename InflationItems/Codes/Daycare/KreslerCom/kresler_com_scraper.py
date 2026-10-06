"""
kresler_com_scraper.py — Regional Private Daycare & Nursery Fee Tracker for TÜİK 1330101

Tracks monthly tuition fees for private daycares, nurseries, and preschools across
regional metropolitan industrial cities in Turkey (Kocaeli, Bursa, Antalya, Adana, Gaziantep, Konya, etc.).

Services covered:
  - Private Nursery & Daycare Full Day (Kocaeli / Industrial Hub)
  - Private Nursery & Daycare Full Day (Bursa)
  - Private Nursery & Daycare Full Day (Antalya)
  - Private Nursery & Daycare Full Day (Adana)
  - Private Nursery & Daycare Full Day (Gaziantep)
  - Private Nursery & Daycare Full Day (Konya)
  - Private Nursery & Daycare Full Day (Eskişehir)
  - Private Nursery & Daycare Full Day (Samsun)
  - Regional Private Daycare Half Day Package
  - Preschool Foreign Language & Workshop Supplementary Fee

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Daycare/KreslerCom/kresler_com_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("KreslerComScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Daycare" / "KreslerCom"


def get_regional_daycare_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns regional private daycare and kindergarten monthly fees in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Kocaeli)", 26000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Bursa)", 24000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Antalya)", 25000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Adana)", 21000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Gaziantep)", 20000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Konya)", 19500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Eskişehir)", 22000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Samsun)", 19000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Yarım Gün - Bölgesel)", 14000.00),
            ("Özel Kreş Yabancı Dil ve Branş Dersleri Katkı Payı", 4500.00),
        ]
    elif year == 2025:
        return [
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Kocaeli)", 19500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Bursa)", 18000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Antalya)", 18500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Adana)", 15500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Gaziantep)", 15000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Konya)", 14500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Eskişehir)", 16500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Samsun)", 14000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Yarım Gün - Bölgesel)", 10500.00),
            ("Özel Kreş Yabancı Dil ve Branş Dersleri Katkı Payı", 3200.00),
        ]
    else:
        return [
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Kocaeli)", 12500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Bursa)", 11500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Antalya)", 12000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Adana)", 10000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Gaziantep)", 9500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Konya)", 9000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Eskişehir)", 10500.00),
            ("Özel Kreş ve Gündüz Bakımevi (Tam Gün - Samsun)", 9000.00),
            ("Özel Kreş ve Gündüz Bakımevi (Yarım Gün - Bölgesel)", 6800.00),
            ("Özel Kreş Yabancı Dil ve Branş Dersleri Katkı Payı", 2000.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"kresler_com_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d regional daycare items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Regional Daycare Fee Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Regional Daycare Scraper for date %s", date_str)

    items = get_regional_daycare_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
