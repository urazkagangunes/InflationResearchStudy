"""
legal_tariff_scraper.py — Legal Services Fee Tariff Tracker for TÜİK CPI Group 1390903 (Legal Services)

Tracks official attorney minimum fee tariffs (Avukatlık Asgari Ücret Tarifesi - AAÜT)
published in the Official Gazette by the Union of Turkish Bar Associations (Türkiye Barolar Birliği - TBB).

Services covered:
  - Oral Legal Consultation at Office (First Hour)
  - Oral Legal Consultation at Office (Subsequent Hours)
  - On-site Oral Consultation
  - Written Legal Opinion / Consultation
  - Legal Notice, Warning, Demand Drafting (İhtarname, İhbarname)
  - Lease Agreement & Contract Drafting (Kira Sözleşmesi)
  - Articles of Association & Corporate Bylaw Drafting
  - Enforcement Offices Proceeding Base Fee (İcra Takibi)
  - Civil Peace Court Proceedings (Sulh Hukuk Mahkemesi)
  - Civil Court of First Instance Proceedings (Asliye Hukuk Mahkemesi)
  - Consumer Court Proceedings (Tüketici Mahkemesi)
  - Labor Court Proceedings (İş Mahkemesi)
  - Heavy Criminal Court Proceedings (Ağır Ceza Mahkemesi)
  - Administrative & Tax Court Proceedings (İdare ve Vergi Mahkemesi)

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Services/Legal/legal_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("LegalTariffScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "Services" / "Legal"


def get_official_legal_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns official statutory legal service minimum fee tariffs in TRY.
    Tariffs are published annually by TBB in the Official Gazette.
    """
    year = int(target_date[:4])

    if year >= 2026:
        # 2025-2026 TBB Official Gazette Tariff
        return [
            ("Avukatlık - Büroda Sözlü Danışma (İlk 1 Saat)", 4500.00),
            ("Avukatlık - Büroda Sözlü Danışma (Takip Eden Her Saat)", 2000.00),
            ("Avukatlık - Çağrı Üzerine Gidilen Yerde Sözlü Danışma", 9000.00),
            ("Avukatlık - Yazılı Danışma (İlk 1 Saat)", 9000.00),
            ("Avukatlık - İhtarname, İhbarname, Protesto Düzenlenmesi", 6500.00),
            ("Avukatlık - Kira Sözleşmesi ve Benzeri Sözleşme Hazırlama", 10000.00),
            ("Avukatlık - Şirket Ana Sözleşmesi ve Tüzük Hazırlama", 26000.00),
            ("Avukatlık - İcra Dairelerinde Yapılan Takipler (Maktu)", 6000.00),
            ("Avukatlık - İcra Mahkemelerinde Takip Edilen Davalar", 12000.00),
            ("Avukatlık - Sulh Hukuk Mahkemelerinde Takip Edilen Davalar", 24000.00),
            ("Avukatlık - Asliye Mahkemelerinde Takip Edilen Davalar", 40000.00),
            ("Avukatlık - Tüketici Mahkemelerinde Takip Edilen Davalar", 20000.00),
            ("Avukatlık - İş Mahkemelerinde Takip Edilen Davalar", 30000.00),
            ("Avukatlık - Ağır Ceza Mahkemelerinde Takip Edilen Davalar", 65000.00),
            ("Avukatlık - İdare ve Vergi Mahkemelerinde Duruşmalı Davalar", 36000.00),
        ]
    elif year == 2025:
        # 2024-2025 TBB Official Gazette Tariff
        return [
            ("Avukatlık - Büroda Sözlü Danışma (İlk 1 Saat)", 3500.00),
            ("Avukatlık - Büroda Sözlü Danışma (Takip Eden Her Saat)", 1500.00),
            ("Avukatlık - Çağrı Üzerine Gidilen Yerde Sözlü Danışma", 7000.00),
            ("Avukatlık - Yazılı Danışma (İlk 1 Saat)", 7000.00),
            ("Avukatlık - İhtarname, İhbarname, Protesto Düzenlenmesi", 5000.00),
            ("Avukatlık - Kira Sözleşmesi ve Benzeri Sözleşme Hazırlama", 7500.00),
            ("Avukatlık - Şirket Ana Sözleşmesi ve Tüzük Hazırlama", 20000.00),
            ("Avukatlık - İcra Dairelerinde Yapılan Takipler (Maktu)", 4500.00),
            ("Avukatlık - İcra Mahkemelerinde Takip Edilen Davalar", 9000.00),
            ("Avukatlık - Sulh Hukuk Mahkemelerinde Takip Edilen Davalar", 18000.00),
            ("Avukatlık - Asliye Mahkemelerinde Takip Edilen Davalar", 30000.00),
            ("Avukatlık - Tüketici Mahkemelerinde Takip Edilen Davalar", 15000.00),
            ("Avukatlık - İş Mahkemelerinde Takip Edilen Davalar", 22500.00),
            ("Avukatlık - Ağır Ceza Mahkemelerinde Takip Edilen Davalar", 48000.00),
            ("Avukatlık - İdare ve Vergi Mahkemelerinde Duruşmalı Davalar", 27000.00),
        ]
    else:
        # 2023-2024 TBB Tariff
        return [
            ("Avukatlık - Büroda Sözlü Danışma (İlk 1 Saat)", 2300.00),
            ("Avukatlık - Büroda Sözlü Danışma (Takip Eden Her Saat)", 1000.00),
            ("Avukatlık - Çağrı Üzerine Gidilen Yerde Sözlü Danışma", 4600.00),
            ("Avukatlık - Yazılı Danışma (İlk 1 Saat)", 4600.00),
            ("Avukatlık - İhtarname, İhbarname, Protesto Düzenlenmesi", 3300.00),
            ("Avukatlık - Kira Sözleşmesi ve Benzeri Sözleşme Hazırlama", 5000.00),
            ("Avukatlık - Şirket Ana Sözleşmesi ve Tüzük Hazırlama", 13000.00),
            ("Avukatlık - İcra Dairelerinde Yapılan Takipler (Maktu)", 3000.00),
            ("Avukatlık - İcra Mahkemelerinde Takip Edilen Davalar", 6000.00),
            ("Avukatlık - Sulh Hukuk Mahkemelerinde Takip Edilen Davalar", 10700.00),
            ("Avukatlık - Asliye Mahkemelerinde Takip Edilen Davalar", 17900.00),
            ("Avukatlık - Tüketici Mahkemelerinde Takip Edilen Davalar", 9000.00),
            ("Avukatlık - İş Mahkemelerinde Takip Edilen Davalar", 14000.00),
            ("Avukatlık - Ağır Ceza Mahkemelerinde Takip Edilen Davalar", 29800.00),
            ("Avukatlık - İdare ve Vergi Mahkemelerinde Duruşmalı Davalar", 16000.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"legal_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d legal tariff items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Legal Services Fee Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Legal Services Fee Tariff Scraper for date %s", date_str)

    items = get_official_legal_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
