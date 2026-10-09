"""
bellona_inflation.py — Daily inflation calculation for Bellona

The script calculates:
  1. Inflation for each item (in percentages)
  2. Average inflation across all items for the day
  3. TUIK weighted inflation (Category 05 - Furnishings and household goods)
  
Intervals: 1 day, 7 days, 15 days, 30 days.
Linking items between dates is done using the 'title' column
(files that name it 'product_name' are read as 'title').

Usage:
    python bellona_inflation.py                  # For today's date
    python bellona_inflation.py --date 2026-05-01 # For a specific date
    python bellona_inflation.py --all            # For ALL dates in the data folder
    python bellona_inflation.py --date 2026-09-29 --compare-date 2026-09-07
                                                 # Also compare with a chosen earlier date
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

# Append directory containing tuik_config
sys.path.insert(0, str(_CODES_DIR))
from tuik_config import TUIK_WEIGHTS, normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Bellona" 
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "HomeGoods" / "Bellona"

# TUIK Category 05: Furnishings, household equipment and routine household maintenance
TUIK_CATEGORY = "05" 

def _load_csv(date_str):
    """Loads the CSV file for the specified date."""
    fpath = DATA_DIR / f"Bellona_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        if "title" not in df.columns and "product_name" in df.columns:
            df = df.rename(columns={"product_name": "title"})
        # Ensure price is numeric
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        # Remove duplicates by title if they accidentally appear, keeping the first one
        df = df.drop_duplicates(subset=["title"], keep="first")
        return df
    except Exception as e:
        logger.error(f"Error reading {fpath}: {e}")
        return None

def _compute_metrics(df_current, df_past):
    """Compares current prices with past ones and calculates inflation metrics."""
    past_subset = df_past[["title", "price"]].rename(columns={"price": "past_price"})
    
    merged = df_current.merge(past_subset, on="title", how="inner")

    merged["per_item_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    avg_inflation = merged["per_item_inflation"].mean()

    # TUIK calculation same as in Bershka
    norm_w = normalised_weights([TUIK_CATEGORY])
    tuik_weighted = avg_inflation * norm_w.get(TUIK_CATEGORY, 100.0) / 100.0

    return merged, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
        
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"impossible to calculate inflation for {today_str}.")
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    intervals = {}
    for days in [1, 7, 15, 30]:
        past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
        intervals[f"{days}d"] = past_str

    if compare_date:
        gap = (base_date - datetime.strptime(compare_date, "%Y-%m-%d")).days
        if gap <= 0:
            logger.warning(f"compare date {compare_date} is not before {today_str}, ignored.")
        else:
            intervals[f"{gap}d"] = compare_date

    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = TUIK_CATEGORY # Add category column to the details file

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            detail_base[f"inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[["title", "per_item_inflation"]].rename(
                columns={"per_item_inflation": f"inflation_{label}"}
            ),
            on="title",
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 4) if pd.notnull(avg_inf) else None
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 4) if pd.notnull(tuik_w) else None


    detail_file = INFLATION_OUT_DIR / f"bellona_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detailed data saved to: {detail_file}")

    summary_file = INFLATION_OUT_DIR / "bellona_inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file)
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8-sig")
        
    logger.info(f"Summary updated in: {summary_file}")


def calculate_all_history():
    """Finds all files in the data folder and runs the calculation chronologically."""
    if not DATA_DIR.exists():
        logger.error(f"Data folder not found: {DATA_DIR}")
        return

    files = list(DATA_DIR.glob("Bellona_*.csv"))
    if not files:
        logger.warning(f"CSV files not found in {DATA_DIR}")
        return

    dates = []
    for f in files:
        date_str = f.stem.replace("Bellona_", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            continue

    dates.sort()
    
    logger.info(f"Files found for processing: {len(dates)}")
    logger.info("Starting historical calculation\n")

    for date_str in dates:
        calculate_inflation(date_str)
        
    logger.info("\ncalculation complete, summary updated.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="inflation calc for Bellona")
    parser.add_argument("--date", help="date (YYYY-MM-DD)", default=None)
    parser.add_argument("--all", action="store_true", help="Calculate inflation for all dates in directory")
    parser.add_argument(
        "--compare-date",
        help="extra earlier date (YYYY-MM-DD) to compare with, e.g. the last available file",
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    if args.all:
        calculate_all_history()
    else:
        calculate_inflation(args.date, args.compare_date)