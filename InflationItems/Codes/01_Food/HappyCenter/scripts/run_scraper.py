"""
Run the daily scraper.

Usage:
    cd InflationResearchStudy/Codes/Markets/HappyCenter/
    python -m scripts.run_scraper
"""

import os
import sys
from datetime import datetime

# Add project root to path so 'from src...' works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OUTPUT_DIR
from src.utils import setup_logger
from src.scraper import scrape_all


def main():
    setup_logger()
    timestamp = datetime.now()

    print(f"\n{'='*60}")
    print(f"  Happy Center Scraper - {timestamp.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    df = scrape_all()
    if df.empty:
        print("No products scraped. Check logs.")
        return

    # Add date columns
    df["scrape_date"] = timestamp.strftime("%Y-%m-%d")
    df["scrape_timestamp"] = timestamp.isoformat()

    # Save CSV and TSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"happycenter_{timestamp.strftime('%Y-%m-%d')}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")


    print(f"\nDone! {len(df)} products -> {filepath}")


if __name__ == "__main__":
    main()
