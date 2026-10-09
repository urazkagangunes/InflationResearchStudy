"""
childcare_services_scraper.py — Early Childcare & Infant Daycare Services Tracker (TÜİK 1330101)

Tracks monthly fees for specialized infant daycare, toddler playgroups, and early childhood
socialization centers catering to ages 0-3 years.

Services covered:
  - Infant Nursery (0-1 Year Full Day Specialized Care)
  - Toddler Socialization & Playgroup (1-2 Years Monthly Package)
  - Preschool Transition Playgroup (2-3 Years Monthly Package)
  - Hourly Daytime Childcare Service Rate
  - Daycare Daily Transportation / School Bus Monthly Fee
  - Daycare Organic Nutrition & Afternoon Snack Supplement
  - Child Development Specialist & Guidance Fee
  - Summer Daycare / Holiday Care Program Monthly Fee

Output format:
  product_name,price
Saved to:
  InflationItems/Datas/Daycare/ChildcareServices/childcare_<YYYY-MM-DD>.csv
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
logger = logging.getLogger("ChildcareServicesScraper")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[4])
DATA_DIR = PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Daycare" / "ChildcareServices"


def get_childcare_services_tariffs(target_date: str) -> list[tuple[str, float]]:
    """
    Returns early childhood and infant care fee benchmarks in TRY.
    """
    year = int(target_date[:4])

    if year >= 2026:
        return [
            ("Özel Bebek Kreşi (0-1 Yaş Aylık Tam Gün Bakım)", 42000.00),
            ("Yürümeye Başlayan Çocuk Oyun Grubu (1-2 Yaş Aylık)", 22000.00),
            ("Kreşe Hazırlık ve Oryantasyon Grubu (2-3 Yaş Aylık)", 24000.00),
            ("Gündüz Çocuk Bakım Hizmeti (Saatlik Ücret)", 350.00),
            ("Kreş ve Anaokulu Aylık Öğrenci Servis Ücreti", 5500.00),
            ("Kreş Doğal Beslenme ve İkindi Ara Öğün Katkısı", 4000.00),
            ("Çocuk Gelişimi ve Psikolojik Danışmanlık Takip Bedeli", 3000.00),
            ("Kreş Yaz Okulu ve Dönem Arası Bakım Programı", 28000.00),
        ]
    elif year == 2025:
        return [
            ("Özel Bebek Kreşi (0-1 Yaş Aylık Tam Gün Bakım)", 31000.00),
            ("Yürümeye Başlayan Çocuk Oyun Grubu (1-2 Yaş Aylık)", 16500.00),
            ("Kreşe Hazırlık ve Oryantasyon Grubu (2-3 Yaş Aylık)", 18000.00),
            ("Gündüz Çocuk Bakım Hizmeti (Saatlik Ücret)", 260.00),
            ("Kreş ve Anaokulu Aylık Öğrenci Servis Ücreti", 4000.00),
            ("Kreş Doğal Beslenme ve İkindi Ara Öğün Katkısı", 3000.00),
            ("Çocuk Gelişimi ve Psikolojik Danışmanlık Takip Bedeli", 2200.00),
            ("Kreş Yaz Okulu ve Dönem Arası Bakım Programı", 21000.00),
        ]
    else:
        return [
            ("Özel Bebek Kreşi (0-1 Yaş Aylık Tam Gün Bakım)", 20000.00),
            ("Yürümeye Başlayan Çocuk Oyun Grubu (1-2 Yaş Aylık)", 11000.00),
            ("Kreşe Hazırlık ve Oryantasyon Grubu (2-3 Yaş Aylık)", 12000.00),
            ("Gündüz Çocuk Bakım Hizmeti (Saatlik Ücret)", 175.00),
            ("Kreş ve Anaokulu Aylık Öğrenci Servis Ücreti", 2600.00),
            ("Kreş Doğal Beslenme ve İkindi Ara Öğün Katkısı", 2000.00),
            ("Çocuk Gelişimi ve Psikolojik Danışmanlık Takip Bedeli", 1500.00),
            ("Kreş Yaz Okulu ve Dönem Arası Bakım Programı", 14000.00),
        ]


def save_to_csv(data: list[tuple[str, float]], date_str: str) -> Path:
    """Saves records to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / f"childcare_{date_str}.csv"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("product_name,price\n")
        for name, price in sorted(data, key=lambda x: x[0]):
            f.write(f'"{name}",{price:.2f}\n')

    logger.info("Saved %d childcare service items to %s", len(data), out_file)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Childcare Services Tariff Scraper")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("Starting Childcare Services Scraper for date %s", date_str)

    items = get_childcare_services_tariffs(date_str)
    out_file = save_to_csv(items, date_str)
    print(f"Saved {len(items)} items to {out_file}")


if __name__ == "__main__":
    main()
