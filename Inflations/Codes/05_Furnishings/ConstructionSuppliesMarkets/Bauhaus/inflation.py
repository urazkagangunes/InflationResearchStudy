"""
inflation.py — Bauhaus Daily Inflation Calculator

Computes three inflation metrics for Bauhaus products:
  1. Basic Inflation   – basket-level price index change (%)
  2. Average Inflation – arithmetic mean of all per-product percentage price changes
  3. TUIK Weighted Avg – weighted average using TUIK 2026 CPI basket weights,
                         all Bauhaus products default to group 05 (Mobilya, ev aletleri ve ev bakım hizmetleri)

Data format: product_name, price (2 columns)

Output Files:
- bauhaus_inflation_YYYY-MM-DD.csv – Detailed per-product data with basic_inflation columns
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

try:
    _scraper_dir = _PROJECT_ROOT / "InflationItems" / "Codes" / "ConstructionSuppliesMarkets" / "Bauhaus" / "scripts"
    sys.path.insert(0, str(_scraper_dir))
    import config
    DATA_DIR = Path(config.OUTPUT_DIR)
except Exception:
    DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"

logger = logging.getLogger(__name__)

# ── Output directory ──────────────────────────────────────────────────────────
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"

TUIK_CATEGORY = "05"  # Mobilya, ev aletleri ve ev bakım hizmetleri


def _load_csv(date_str):
    """Load a Bauhaus daily CSV by date string, return DataFrame or None."""
    fpath = DATA_DIR / f"bauhaus_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    """Compute the three inflation metrics between two DataFrames."""
    df_current = df_current.copy()
    df_current['tuik_category'] = TUIK_CATEGORY

    past_subset = df_past[['product_name', 'price']].rename(columns={'price': 'past_price'})
    merged = df_current.merge(past_subset, on='product_name', how='left')

    # 1) Basic inflation per product
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
    tuik_weighted = sum(cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c]))

    merged = merged.drop(columns=['past_price'], errors='ignore')
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for Bauhaus."""
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
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
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(f"Skipping interval {label} – no data for {past_str}.")
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['product_name', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='product_name', how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    detail_file = INFLATION_OUT_DIR / f"bauhaus_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Saved detailed inflation data to: {detail_file}")

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
    parser = argparse.ArgumentParser(description="Bauhaus inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
