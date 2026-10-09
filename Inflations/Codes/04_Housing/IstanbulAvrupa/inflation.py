"""
inflation.py — IstanbulAvrupa (Rent) Daily Inflation Calculator

Computes three inflation metrics for IstanbulAvrupa rental listings:
  1. Basic Inflation   – basket-level price index change (%) calculated as sum of current median prices vs sum of past median prices
  2. Average Inflation – arithmetic mean of all per-segment median price percentage changes
  3. TUIK Weighted Avg – weighted average using TUIK 2026 CPI basket weights
                         (all segments map to group 04 – Konut)

Data format: product_name (District - Rooms), price (2 columns)

Output Files:
- IstanbulAvrupa_inflation_YYYY-MM-DD.csv – Segment-level data with basic_inflation columns
- inflation_summary.csv – Store-level summary with avg_inflation and tuik_weighted columns

Usage:
    python inflation.py                    # Uses today's date
    python inflation.py --date 2026-03-20  # Specific target date
    python inflation.py --date 2026-03-20 --compare 2026-03-10  # Arbitrary comparison
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent               # .../Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent            # .../InflationResearchStudy

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import normalised_weights, TUIK_WEIGHTS

# Scraper config for data paths
_scraper_dir = _PROJECT_ROOT / "InflationItems" / "Codes" / "HousesRent" / "IstanbulAvrupa" / "scripts"
sys.path.insert(0, str(_scraper_dir))
import config

logger = logging.getLogger(__name__)

# ── Directories ───────────────────────────────────────────────────────────────
DATA_DIR = Path(config.BASE_OUTPUT_DIR)
FOLDER_NAME = config.FOLDER_NAME
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "HousesRent" / "IstanbulAvrupa"

TUIK_CATEGORY = "04"  # Konut


def _parse_price(price_str):
    """Convert a Turkish price string like '8.000 TL' to a float 8000.0."""
    try:
        if pd.isna(price_str):
            return None
        clean_str = str(price_str).replace(' TL', '').replace('.', '').strip()
        return float(clean_str)
    except Exception:
        return None


def _load_and_group(date_str):
    """Load a daily CSV, parse prices, and return median-grouped DataFrame or None."""
    fpath = DATA_DIR / f"{FOLDER_NAME}_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath)
        df['price_num'] = df['price'].apply(_parse_price)
        grouped = df.groupby('product_name')['price_num'].median().reset_index()
        grouped.rename(columns={'price_num': 'price'}, inplace=True)
        return grouped
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    """Compute the three inflation metrics between two grouped DataFrames."""
    df_current = df_current.copy()
    df_current['tuik_category'] = TUIK_CATEGORY

    past_subset = df_past[['product_name', 'price']].rename(columns={'price': 'past_price'})
    merged = df_current.merge(past_subset, on='product_name', how='left')

    # 1) Basic inflation per segment
    merged['basic_inflation'] = ((merged['price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2) Average inflation
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Basic inflation at basket level
    valid = merged.dropna(subset=['price', 'past_price'])
    sum_current = valid['price'].sum()
    sum_past = valid['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK weighted average
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    valid_terms = [cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c])]
    tuik_weighted = sum(valid_terms) if valid_terms else None

    merged = merged.drop(columns=['past_price'], errors='ignore')
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for IstanbulAvrupa rental listings."""
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_and_group(today_str)
    if df_today is None:
        logger.warning(f"Cannot calculate inflation – no data for {today_str}.")
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {}
        for days in [1, 7, 15, 30]:
            past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals[f"{days}d"] = past_str

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = TUIK_CATEGORY

    for label, past_str in intervals.items():
        df_past = _load_and_group(past_str)

        if df_past is None:
            logger.info(f"Skipping interval {label} – no data for {past_str}.")
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['product_name', 'basic_inflation']].rename(
                columns={'basic_inflation': f'basic_inflation_{label}'}
            ),
            on='product_name', how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    detail_file = INFLATION_OUT_DIR / f"{FOLDER_NAME}_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Saved grouped inflation data to: {detail_file}")

    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Updated inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Created inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IstanbulAvrupa rent inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
