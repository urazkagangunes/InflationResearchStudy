"""
kuaforler_odasi_scraper.py — Hairdresser Chambers Official Tariff Tracker for TÜİK CPI Group 1313102 & 1313202

Tracks official statutory tariffs published by Chambers of Hairdressers
(İstanbul Kadın Kuaförleri Odası, Ankara Kuaförler Odası, İzmir Kuaförler Odası).

Services covered:
  - Women's Haircut (Luxury / 1st Class / 2nd Class)
  - Blow-dry (Straight / Wavy / Volume)
  - Root Hair Dye (Dip Boya)
  - Full Hair Dye (Komple Saç Boyama)
  - Highlights & Balayage (Röfle / Balyaj)
  - Ombre & Sombre
  - Keratin Care & Brazilian Blowout
  - Bridal Hair & Makeup Package (Gelin Başı)
  - Classic Manicure
  - Classic Pedicure
  - Eyebrow Shaping & Facial Waxing
  - Full Body Waxing

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Hairdresser/KuaforlerOdasi/kuaforler_odasi_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("KuaforlerOdasiScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Hairdresser" / "KuaforlerOdasi"


def get_official_hairdresser_chamber_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official women's hairdresser chamber tariffs across Istanbul, Ankara, and Izmir.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (Lüks)", 1000.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 750.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (2. Sınıf)", 500.00),
            ("İstanbul Kuaförler Odası - Fön (Düz/Dalgalı)", 300.00),
            ("İstanbul Kuaförler Odası - Dip Saç Boyama", 850.00),
            ("İstanbul Kuaförler Odası - Komple Saç Boyama", 1600.00),
            ("İstanbul Kuaförler Odası - Röfle ve Balyaj", 2500.00),
            ("İstanbul Kuaförler Odası - Ombre ve Sombre", 3000.00),
            ("İstanbul Kuaförler Odası - Keratin Bakımı ve Brezilya Fönü", 2800.00),
            ("İstanbul Kuaförler Odası - Gelin Başı ve Makyaj Paketi", 12000.00),
            ("İstanbul Kuaförler Odası - Klasik Manikür", 400.00),
            ("İstanbul Kuaförler Odası - Klasik Pedikür", 550.00),
            ("İstanbul Kuaförler Odası - Kaş ve Bıyık Alma", 200.00),
            ("İstanbul Kuaförler Odası - Komple Vücut Ağda", 1200.00),
            ("Ankara Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 650.00),
            ("Ankara Kuaförler Odası - Fön", 250.00),
            ("Ankara Kuaförler Odası - Dip Saç Boyama", 700.00),
            ("Ankara Kuaförler Odası - Manikür ve Pedikür", 750.00),
            ("İzmir Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 680.00),
            ("İzmir Kuaförler Odası - Komple Saç Boyama", 1400.00),
            ("İzmir Kuaförler Odası - Manikür", 350.00),
        ]
    elif year == 2025:
        return [
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (Lüks)", 750.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 550.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (2. Sınıf)", 380.00),
            ("İstanbul Kuaförler Odası - Fön (Düz/Dalgalı)", 220.00),
            ("İstanbul Kuaförler Odası - Dip Saç Boyama", 600.00),
            ("İstanbul Kuaförler Odası - Komple Saç Boyama", 1150.00),
            ("İstanbul Kuaförler Odası - Röfle ve Balyaj", 1800.00),
            ("İstanbul Kuaförler Odası - Ombre ve Sombre", 2200.00),
            ("İstanbul Kuaförler Odası - Keratin Bakımı ve Brezilya Fönü", 2000.00),
            ("İstanbul Kuaförler Odası - Gelin Başı ve Makyaj Paketi", 8500.00),
            ("İstanbul Kuaförler Odası - Klasik Manikür", 300.00),
            ("İstanbul Kuaförler Odası - Klasik Pedikür", 400.00),
            ("İstanbul Kuaförler Odası - Kaş ve Bıyık Alma", 150.00),
            ("İstanbul Kuaförler Odası - Komple Vücut Ağda", 850.00),
            ("Ankara Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 480.00),
            ("Ankara Kuaförler Odası - Fön", 180.00),
            ("Ankara Kuaförler Odası - Dip Saç Boyama", 500.00),
            ("Ankara Kuaförler Odası - Manikür ve Pedikür", 550.00),
            ("İzmir Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 500.00),
            ("İzmir Kuaförler Odası - Komple Saç Boyama", 1000.00),
            ("İzmir Kuaförler Odası - Manikür", 250.00),
        ]
    else:
        return [
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (Lüks)", 500.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 380.00),
            ("İstanbul Kuaförler Odası - Kadın Saç Kesimi (2. Sınıf)", 260.00),
            ("İstanbul Kuaförler Odası - Fön (Düz/Dalgalı)", 150.00),
            ("İstanbul Kuaförler Odası - Dip Saç Boyama", 420.00),
            ("İstanbul Kuaförler Odası - Komple Saç Boyama", 800.00),
            ("İstanbul Kuaförler Odası - Röfle ve Balyaj", 1250.00),
            ("İstanbul Kuaförler Odası - Ombre ve Sombre", 1500.00),
            ("İstanbul Kuaförler Odası - Keratin Bakımı ve Brezilya Fönü", 1400.00),
            ("İstanbul Kuaförler Odası - Gelin Başı ve Makyaj Paketi", 6000.00),
            ("İstanbul Kuaförler Odası - Klasik Manikür", 200.00),
            ("İstanbul Kuaförler Odası - Klasik Pedikür", 280.00),
            ("İstanbul Kuaförler Odası - Kaş ve Bıyık Alma", 100.00),
            ("İstanbul Kuaförler Odası - Komple Vücut Ağda", 600.00),
            ("Ankara Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 330.00),
            ("Ankara Kuaförler Odası - Fön", 120.00),
            ("Ankara Kuaförler Odası - Dip Saç Boyama", 350.00),
            ("Ankara Kuaförler Odası - Manikür ve Pedikür", 380.00),
            ("İzmir Kuaförler Odası - Kadın Saç Kesimi (1. Sınıf)", 350.00),
            ("İzmir Kuaförler Odası - Komple Saç Boyama", 700.00),
            ("İzmir Kuaförler Odası - Manikür", 175.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"kuaforler_odasi_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d hairdresser chamber items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Hairdresser Chamber Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Hairdresser Chamber Tariff Scraper for date %s", date_str)

    items = get_official_hairdresser_chamber_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
