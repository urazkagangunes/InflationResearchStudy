"""
Run the daily scraper.

Usage:
    cd hapeloglu-price-tracker/
    python -m scripts.run_scraper
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OUTPUT_DIR
from src.utils import setup_logger
from src.scraper import scrape_all


def _resolve_scrape_timestamp() -> datetime:
    override = os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
    now = datetime.now().replace(microsecond=0)
    if not override:
        return now

    target_date = date.fromisoformat(override)
    return datetime.combine(target_date, now.time())


def main():
    setup_logger()
    timestamp = _resolve_scrape_timestamp()

    df = scrape_all()
    if df.empty:
        print("No products scraped. Check logs.")
        return

    df["scrape_date"] = timestamp.strftime("%Y-%m-%d")
    df["scrape_timestamp"] = timestamp.isoformat()

    # Standardize columns: product_name first, price second
    df = df.rename(columns={"name": "product_name", "current_price": "price"})
    cols = ["product_name", "price"] + [c for c in df.columns if c not in ("product_name", "price")]
    df = df[cols]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"hapeloglu_{timestamp.strftime('%Y-%m-%d')}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    # Save CSV
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    print(f"\n[DONE] {len(df)} items saved to {filepath}")


if __name__ == "__main__":
    main()
