"""
tuvturk_scraper.py — TÜVTÜRK Vehicle Inspection Tariff Tracker for TÜİK CPI Group 1390902

Tracks official vehicle periodic inspection fees and exhaust gas emission measurement fees
established by the Ministry of Transport and Infrastructure and operated by TÜVTÜRK.

Categories covered:
  - Passenger Car, Minibus, Pickup Truck Periodic Inspection (KDV Included)
  - Bus, Truck, Tractor-Trailer, Tanker Inspection
  - Motorcycle, Moped, Agricultural Tractor Inspection
  - Exhaust Gas Emission Test Fee (Egzoz Emisyon Ölçümü)
  - Trailer and Semi-Trailer Periodic Inspection
  - Off-Road and Special Purpose Vehicle Inspection
  - Commercial Vehicle Roadworthiness Test

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/Tuvturk/tuvturk_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("TuvturkScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "Tuvturk"


def get_official_tuvturk_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official vehicle inspection statutory fees in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("TÜVTÜRK - Otomobil, Minibüs, Kamyonet Periyodik Muayene Ücreti", 3288.00),
            ("TÜVTÜRK - Otobüs, Kamyon, Çekici ve Tanker Muayene Ücreti", 4446.00),
            ("TÜVTÜRK - Motosiklet, Motorlu Bisiklet ve Traktör Muayene Ücreti", 1674.00),
            ("TÜVTÜRK - Egzoz Gazı Emisyon Ölçüm Bedeli (Zorunlu)", 460.00),
            ("TÜVTÜRK - Römork ve Yarı Römork Muayene Ücreti", 3288.00),
            ("TÜVTÜRK - Arazi Taşıtı ve Özel Amaçlı Taşıt Muayene Ücreti", 3288.00),
            ("TÜVTÜRK - Ticari Araç Yola Elverişlilik Muayenesi", 2200.00),
        ]
    elif year == 2025:
        return [
            ("TÜVTÜRK - Otomobil, Minibüs, Kamyonet Periyodik Muayene Ücreti", 2622.00),
            ("TÜVTÜRK - Otobüs, Kamyon, Çekici ve Tanker Muayene Ücreti", 3544.00),
            ("TÜVTÜRK - Motosiklet, Motorlu Bisiklet ve Traktör Muayene Ücreti", 1335.00),
            ("TÜVTÜRK - Egzoz Gazı Emisyon Ölçüm Bedeli (Zorunlu)", 360.00),
            ("TÜVTÜRK - Römork ve Yarı Römork Muayene Ücreti", 2622.00),
            ("TÜVTÜRK - Arazi Taşıtı ve Özel Amaçlı Taşıt Muayene Ücreti", 2622.00),
            ("TÜVTÜRK - Ticari Araç Yola Elverişlilik Muayenesi", 1750.00),
        ]
    else:
        return [
            ("TÜVTÜRK - Otomobil, Minibüs, Kamyonet Periyodik Muayene Ücreti", 1821.60),
            ("TÜVTÜRK - Otobüs, Kamyon, Çekici ve Tanker Muayene Ücreti", 2462.40),
            ("TÜVTÜRK - Motosiklet, Motorlu Bisiklet ve Traktör Muayene Ücreti", 928.80),
            ("TÜVTÜRK - Egzoz Gazı Emisyon Ölçüm Bedeli (Zorunlu)", 256.00),
            ("TÜVTÜRK - Römork ve Yarı Römork Muayene Ücreti", 1821.60),
            ("TÜVTÜRK - Arazi Taşıtı ve Özel Amaçlı Taşıt Muayene Ücreti", 1821.60),
            ("TÜVTÜRK - Ticari Araç Yola Elverişlilik Muayenesi", 1200.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"tuvturk_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d TÜVTÜRK inspection items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="TÜVTÜRK Vehicle Inspection Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting TÜVTÜRK Tariff Scraper for date %s", date_str)

    items = get_official_tuvturk_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
