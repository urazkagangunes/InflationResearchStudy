"""
inflation.py — Ankara Housing Daily Inflation Calculator

Computes three inflation metrics for Ankara rental listings:
  1. Basic Inflation   – basket-level price index change (%)
  2. Average Inflation – arithmetic mean of per-district/room-type changes
  3. TUIK Weighted Avg – weighted average based on 2026 CPI weights
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

sys.path.insert(0, str(_CODES_DIR))
try:
    from tuik_config import normalised_weights, TUIK_WEIGHTS
except ImportError:
    # Fallback if pathing is weird during direct execution
    sys.path.insert(0, str(_PROJECT_ROOT / "Inflations" / "Codes"))
    from tuik_config import normalised_weights, TUIK_WEIGHTS

logger = logging.getLogger(__name__)

# ── Directories ───────────────────────────────────────────────────────────────
DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HousesRent" / "Ankara"
INFLATION_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "HousesRent" / "Ankara"

def _load_csv(date_str):
    """Load an Ankara rental CSV and aggregate into comparable units."""
    try:
        fpath = DATA_DIR / f"Ankara_ALL_{date_str}.csv"
        
        if not fpath.exists():
            logger.info(f"Data file not found: {fpath}")
            return None
            
        df = pd.read_csv(fpath)
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        
        # Since individual rental listings lack stable IDs across days,
        # we aggregate by District and Room Type to create a stable unit for comparison.
        df_agg = df.groupby(['District', 'Rooms'])['Price'].mean().reset_index()
        df_agg['unit_id'] = df_agg['District'] + "_" + df_agg['Rooms']
        return df_agg
    except Exception as e:
        logger.error(f"Failed to load or parse data for {date_str}: {e}")
        return None

def _compute_metrics(df_current, df_past):
    """Compute inflation metrics based on aggregated District-Room units."""
    df_current = df_current.copy()
    df_current['tuik_category'] = "04" # Housing Rent is Group 04

    past_subset = df_past[['unit_id', 'Price']].rename(columns={'Price': 'past_price'})
    merged = df_current.merge(past_subset, on='unit_id', how='left')

    # 1) Basic inflation per unit
    merged['basic_inflation'] = ((merged['Price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2) Average inflation – arithmetic mean
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Basic inflation at basket level
    valid = merged.dropna(subset=['Price', 'past_price'])
    sum_current = valid['Price'].sum()
    sum_past = valid['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK weighted average (With only one category present, weighted == average)
    tuik_weighted = avg_inflation

    return merged, basic_inflation_index, avg_inflation, tuik_weighted

def calculate_inflation(target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"No data for {today_str}.")
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
    detail_base['tuik_category'] = "04"

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)
        if df_past is None:
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)
        
        detail_base = detail_base.merge(
            merged[['unit_id', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='unit_id', how='left'
        )
        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # Save detailed
    detail_file = INFLATION_OUT_DIR / f"ankara_housing_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8-sig')
    logger.info(f"Saved detail: {detail_file}")

    # Update summary
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8-sig')
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8-sig')
        logger.info(f"Updated summary: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--compare", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
