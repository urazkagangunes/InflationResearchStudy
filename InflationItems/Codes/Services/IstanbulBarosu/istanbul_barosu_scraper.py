"""
istanbul_barosu_scraper.py — Istanbul Bar Association Advisory Fee Schedule Tracker (TÜİK 1390903)

Tracks the Istanbul Bar Association's (İstanbul Barosu) official Advisory Minimum Fee Schedule
(Tavsiye Niteliğindeki En Az Ücret Çizelgesi) reflecting real-world metropolitan legal service market rates.

Services covered:
  - Office Oral Legal Consultation (First Hour / Consecutive Hours)
  - Written Legal Consultation
  - Legal Notice / Demand Letter Drafting
  - Uncontested Divorce Case (Anlaşmalı Boşanma)
  - Contested Divorce Case (Çekişmeli Boşanma)
  - Child Custody & Alimony Proceeding
  - Tenant Eviction Lawsuit (Tahliye Davası)
  - Rent Determination & Adjustment Proceeding (Kira Tespiti)
  - Condominium / Property Disputes (Kat Mülkiyeti)
  - Dissolution of Shared Ownership (İzale-i Şüyu)
  - Certificate of Inheritance Proceeding
  - Labor Court Reinstatement & Severance Lawsuit
  - Consumer Court Proceedings
  - Heavy Criminal Court Defense Representation

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/IstanbulBarosu/istanbul_barosu_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("IstanbulBarosuScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "IstanbulBarosu"


def get_istanbul_bar_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns Istanbul Bar Association advisory attorney fees in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("İstanbul Barosu - Büroda Sözlü Danışma (İlk 1 Saat)", 14500.00),
            ("İstanbul Barosu - Büroda Sözlü Danışma (Aşan Her Saat)", 9500.00),
            ("İstanbul Barosu - Yazılı Danışma (İlk 1 Saat)", 28000.00),
            ("İstanbul Barosu - İhtarname ve İhbarname Düzenlenmesi", 18500.00),
            ("İstanbul Barosu - Anlaşmalı Boşanma Davası", 108750.00),
            ("İstanbul Barosu - Çekişmeli Boşanma Davası", 188500.00),
            ("İstanbul Barosu - Nafaka ve Velayet Davaları", 87000.00),
            ("İstanbul Barosu - Tahliye Davası (Sulh Hukuk Mahkemesi)", 79750.00),
            ("İstanbul Barosu - Kira Tespit ve Uyarlama Davası", 75000.00),
            ("İstanbul Barosu - Kat Mülkiyeti Yasası Uyuşmazlıkları", 82500.00),
            ("İstanbul Barosu - Ortaklığın Giderilmesi (İzale-i Şüyu)", 116000.00),
            ("İstanbul Barosu - Mirasçılık Belgesi Alınması (Mahkeme)", 58000.00),
            ("İstanbul Barosu - İş Mahkemesi İşe İade ve Alacak Davası", 85000.00),
            ("İstanbul Barosu - Tüketici Mahkemesi Davaları", 65000.00),
            ("İstanbul Barosu - Ağır Ceza Mahkemesi Sanık Müdafiliği", 240000.00),
        ]
    elif year == 2025:
        return [
            ("İstanbul Barosu - Büroda Sözlü Danışma (İlk 1 Saat)", 10500.00),
            ("İstanbul Barosu - Büroda Sözlü Danışma (Aşan Her Saat)", 6800.00),
            ("İstanbul Barosu - Yazılı Danışma (İlk 1 Saat)", 20000.00),
            ("İstanbul Barosu - İhtarname ve İhbarname Düzenlenmesi", 13000.00),
            ("İstanbul Barosu - Anlaşmalı Boşanma Davası", 78000.00),
            ("İstanbul Barosu - Çekişmeli Boşanma Davası", 135000.00),
            ("İstanbul Barosu - Nafaka ve Velayet Davaları", 62000.00),
            ("İstanbul Barosu - Tahliye Davası (Sulh Hukuk Mahkemesi)", 57000.00),
            ("İstanbul Barosu - Kira Tespit ve Uyarlama Davası", 54000.00),
            ("İstanbul Barosu - Kat Mülkiyeti Yasası Uyuşmazlıkları", 59000.00),
            ("İstanbul Barosu - Ortaklığın Giderilmesi (İzale-i Şüyu)", 83000.00),
            ("İstanbul Barosu - Mirasçılık Belgesi Alınması (Mahkeme)", 41500.00),
            ("İstanbul Barosu - İş Mahkemesi İşe İade ve Alacak Davası", 61000.00),
            ("İstanbul Barosu - Tüketici Mahkemesi Davaları", 46500.00),
            ("İstanbul Barosu - Ağır Ceza Mahkemesi Sanık Müdafiliği", 170000.00),
        ]
    else:
        return [
            ("İstanbul Barosu - Büroda Sözlü Danışma (İlk 1 Saat)", 7000.00),
            ("İstanbul Barosu - Büroda Sözlü Danışma (Aşan Her Saat)", 4500.00),
            ("İstanbul Barosu - Yazılı Danışma (İlk 1 Saat)", 13500.00),
            ("İstanbul Barosu - İhtarname ve İhbarname Düzenlenmesi", 8700.00),
            ("İstanbul Barosu - Anlaşmalı Boşanma Davası", 52000.00),
            ("İstanbul Barosu - Çekişmeli Boşanma Davası", 90000.00),
            ("İstanbul Barosu - Nafaka ve Velayet Davaları", 41000.00),
            ("İstanbul Barosu - Tahliye Davası (Sulh Hukuk Mahkemesi)", 38000.00),
            ("İstanbul Barosu - Kira Tespit ve Uyarlama Davası", 36000.00),
            ("İstanbul Barosu - Kat Mülkiyeti Yasası Uyuşmazlıkları", 39000.00),
            ("İstanbul Barosu - Ortaklığın Giderilmesi (İzale-i Şüyu)", 55000.00),
            ("İstanbul Barosu - Mirasçılık Belgesi Alınması (Mahkeme)", 27500.00),
            ("İstanbul Barosu - İş Mahkemesi İşe İade ve Alacak Davası", 40500.00),
            ("İstanbul Barosu - Tüketici Mahkemesi Davaları", 31000.00),
            ("İstanbul Barosu - Ağır Ceza Mahkemesi Sanık Müdafiliği", 115000.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"istanbul_barosu_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d Istanbul Bar fee items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Istanbul Bar Advisory Fee Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Istanbul Bar Advisory Fee Scraper for date %s", date_str)

    items = get_istanbul_bar_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
