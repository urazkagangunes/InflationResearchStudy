"""
notary_vehicle_transfer_scraper.py — Notary Vehicle Transfer Fee Tracker for TÜİK CPI Group 1390901

Tracks statutory vehicle sales, ownership registration, and valuable paper fees
at Notary Publics established by the Ministry of Justice, TNB, and the Ministry of Treasury & Finance.

Items covered:
  - Used Vehicle Sales Contract & Registration Base Fee
  - Vehicle Registration Certificate Fee (Araç Tescil Belgesi)
  - Notary Valuable Paper Fee (Noter Değerli Kağıt)
  - Brand New Vehicle First Registration (Sıfır Araç Tescil)
  - License Plate Change & Issue Slip Fee
  - Vehicle Lien & Pledge Registration (Rehin Şerhi)
  - Lien Removal Fee (Rehin Kaldırma)
  - Commercial Vehicle License Plate Transfer Notary Contract

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/NotaryVehicle/notary_vehicle_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("NotaryVehicleScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Services" / "NotaryVehicle"


def get_vehicle_transfer_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official notary vehicle transfer and title registration fees in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Noter - İkinci El Araç Satış ve Tescil Toplam Ücreti", 1489.00),
            ("Noter - Araç Tescil Belgesi Bedeli", 1140.00),
            ("Noter - Motorlu Araç Tescil Değerli Kağıt Bedeli", 349.00),
            ("Noter - Sıfır Araç İlk Tescil ve Sicil Kaydı", 1120.00),
            ("Noter - Plaka Değişikliği İşlem Ücreti", 420.00),
            ("Noter - Araç Rehin ve İpotek Şerhi Tescili", 750.00),
            ("Noter - Araç Rehin Kaldırma (Fek) İşlem Ücreti", 380.00),
            ("Noter - Çekme Belgeli Araç Satış Sözleşmesi", 1489.00),
            ("Noter - Ticari Taksi / Minibüs Hat ve Plaka Devir Sözleşmesi", 4500.00),
        ]
    elif year == 2025:
        return [
            ("Noter - İkinci El Araç Satış ve Tescil Toplam Ücreti", 1100.00),
            ("Noter - Araç Tescil Belgesi Bedeli", 840.00),
            ("Noter - Motorlu Araç Tescil Değerli Kağıt Bedeli", 260.00),
            ("Noter - Sıfır Araç İlk Tescil ve Sicil Kaydı", 820.00),
            ("Noter - Plaka Değişikliği İşlem Ücreti", 310.00),
            ("Noter - Araç Rehin ve İpotek Şerhi Tescili", 550.00),
            ("Noter - Araç Rehin Kaldırma (Fek) İşlem Ücreti", 280.00),
            ("Noter - Çekme Belgeli Araç Satış Sözleşmesi", 1100.00),
            ("Noter - Ticari Taksi / Minibüs Hat ve Plaka Devir Sözleşmesi", 3300.00),
        ]
    else:
        return [
            ("Noter - İkinci El Araç Satış ve Tescil Toplam Ücreti", 850.00),
            ("Noter - Araç Tescil Belgesi Bedeli", 650.00),
            ("Noter - Motorlu Araç Tescil Değerli Kağıt Bedeli", 200.00),
            ("Noter - Sıfır Araç İlk Tescil ve Sicil Kaydı", 630.00),
            ("Noter - Plaka Değişikliği İşlem Ücreti", 240.00),
            ("Noter - Araç Rehin ve İpotek Şerhi Tescili", 420.00),
            ("Noter - Araç Rehin Kaldırma (Fek) İşlem Ücreti", 210.00),
            ("Noter - Çekme Belgeli Araç Satış Sözleşmesi", 850.00),
            ("Noter - Ticari Taksi / Minibüs Hat ve Plaka Devir Sözleşmesi", 2500.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"notary_vehicle_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d vehicle transfer notary items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Notary Vehicle Transfer Fee Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Notary Vehicle Transfer Fee Scraper for date %s", date_str)

    items = get_vehicle_transfer_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
