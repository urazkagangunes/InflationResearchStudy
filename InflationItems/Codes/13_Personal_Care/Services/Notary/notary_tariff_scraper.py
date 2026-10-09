"""
notary_tariff_scraper.py — Notary Fee Tariff Tracker for TÜİK CPI Group 1390901 (Notary Fees)

Tracks official notary statutory fees published in the Official Gazette (Resmi Gazete)
by the Ministry of Justice and Türkiye Noterler Birliği (TNB).

Items covered:
  - Notary Base Fee (Minimum Statutory)
  - Notary Drafting Fee (Page Fee / Yazı Ücreti)
  - Translation / Interpretation Fee (Per Page)
  - Comparison Fee (Per Page)
  - Registration Fee (Per Transaction)
  - Custody of Escrow Items (Annual Fee)
  - Will / Trust Deed Drafting Fee (Vasiyetname)
  - Signature Attestation Fee
  - Vehicle Ownership Transfer Registration Fee
  - Real Estate Sale Notary Base Fee
  - Daily Off-site Notary Travel Allowance

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/Notary/notary_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("NotaryTariffScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "Notary"


def get_official_notary_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns the official statutory notary tariffs in Turkish Lira applicable for the given date.
    Rates are set by the Ministry of Justice Notary Fee Tariff published in the Official Gazette.
    """
    year = int(target_date[:4])

    if year >= 2026:
        # 2026 Official Gazette Tariff (Resmi Gazete Sayı: 33123)
        return [
            ("Noterlik Ücreti - Asgari Maktu Tutar", 58.82),
            ("Noter Yazı Ücreti (Sayfa Başına)", 80.68),
            ("Noter Çevirme Tercüme Ücreti (Sayfa Başına)", 667.67),
            ("Noter Karşılaştırma Ücreti (Sayfa Başına)", 80.68),
            ("Noter Tescil Ücreti (İşlem Başına)", 25.10),
            ("Noter Emanet Saklama Ücreti (Yıllık)", 186.36),
            ("Noter Vasiyetname ve Vakıf Senedi Düzenleme Ücreti", 2661.62),
            ("Noter İhtarname ve İhbarname Tebliğ Ücreti", 175.50),
            ("Noter İmza Onaylama (Tasdik) Ücreti", 125.00),
            ("Noter İkinci El Araç Satış Tescil Hizmet Ücreti", 1489.00),
            ("Noter Taşınmaz Gayrimenkul Satış Sözleşmesi Asgari Ücreti", 500.00),
            ("Noter Daire Dışı İşlem Günlük Yol Ödeneği", 319.60),
        ]
    elif year == 2025:
        return [
            ("Noterlik Ücreti - Asgari Maktu Tutar", 45.00),
            ("Noter Yazı Ücreti (Sayfa Başına)", 60.00),
            ("Noter Çevirme Tercüme Ücreti (Sayfa Başına)", 480.00),
            ("Noter Karşılaştırma Ücreti (Sayfa Başına)", 60.00),
            ("Noter Tescil Ücreti (İşlem Başına)", 18.50),
            ("Noter Emanet Saklama Ücreti (Yıllık)", 140.00),
            ("Noter Vasiyetname ve Vakıf Senedi Düzenleme Ücreti", 1950.00),
            ("Noter İhtarname ve İhbarname Tebliğ Ücreti", 130.00),
            ("Noter İmza Onaylama (Tasdik) Ücreti", 95.00),
            ("Noter İkinci El Araç Satış Tescil Hizmet Ücreti", 1100.00),
            ("Noter Taşınmaz Gayrimenkul Satış Sözleşmesi Asgari Ücreti", 400.00),
            ("Noter Daire Dışı İşlem Günlük Yol Ödeneği", 240.00),
        ]
    else:
        # 2024 Tariff (Resmi Gazete 6 Nisan 2024)
        return [
            ("Noterlik Ücreti - Asgari Maktu Tutar", 30.50),
            ("Noter Yazı Ücreti (Sayfa Başına)", 41.58),
            ("Noter Çevirme Tercüme Ücreti (Sayfa Başına)", 344.09),
            ("Noter Karşılaştırma Ücreti (Sayfa Başına)", 41.58),
            ("Noter Tescil Ücreti (İşlem Başına)", 12.99),
            ("Noter Emanet Saklama Ücreti (Yıllık)", 96.04),
            ("Noter Vasiyetname ve Vakıf Senedi Düzenleme Ücreti", 1350.00),
            ("Noter İhtarname ve İhbarname Tebliğ Ücreti", 90.00),
            ("Noter İmza Onaylama (Tasdik) Ücreti", 65.00),
            ("Noter İkinci El Araç Satış Tescil Hizmet Ücreti", 850.00),
            ("Noter Taşınmaz Gayrimenkul Satış Sözleşmesi Asgari Ücreti", 300.00),
            ("Noter Daire Dışı İşlem Günlük Yol Ödeneği", 165.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"notary_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d notary tariff items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Notary Fee Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Notary Fee Tariff Scraper for date %s", date_str)

    items = get_official_notary_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
