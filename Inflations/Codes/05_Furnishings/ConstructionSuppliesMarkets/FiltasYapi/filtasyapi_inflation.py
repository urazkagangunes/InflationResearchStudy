"""
filtasyapi_inflation.py — FiltaşYapı Daily Inflation Calculator

Computes inflation metrics for FiltaşYapı construction supply products:
  1. Per-item inflation — percentage price change per product
  2. Average inflation  — arithmetic mean of per-item rates
  3. TUIK weighted avg  — weighted average using TUIK 2026 CPI basket weights

All FiltaşYapı products map to TUIK category 05 (Furniture, appliances, maintenance).
Products are matched across dates by title.

Intervals: 1d, 7d, 15d, 30d

Usage:
    python filtasyapi_inflation.py                  # Uses today's date
    python filtasyapi_inflation.py --date 2026-04-05 # Specific date
    python filtasyapi_inflation.py --all            # Calculates for all dates
"""

import argparse
import importlib.util
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

# Paths aligned with FiltaşYapı scraper
DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "ConstructionSuppliesMarkets" / "FiltasYapi"
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "ConstructionSuppliesMarkets" / "FiltasYapi"

# Match keys based on FiltaşYapı's CSV structure
MATCH_KEY = "title"
PRICE_COLUMN = "price"
TUIK_CATEGORY_CODE = "05"  # Furniture, household equipment, routine maintenance

logger = logging.getLogger(__name__)


def _load_csv(date_str):
    """Load one FiltaşYapı daily snapshot for the given date."""
    fpath = DATA_DIR / f"FiltaşYapı_{date_str}.csv"
    if not fpath.exists():
        logger.info("Data file not found: %s", fpath)
        return None

    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df[PRICE_COLUMN] = pd.to_numeric(df[PRICE_COLUMN], errors="coerce")
        df[MATCH_KEY] = df[MATCH_KEY].astype("string").str.strip()
        df = df[df[MATCH_KEY].notna() & (df[MATCH_KEY] != "")]
        
        # The FiltaşYapı scraper doesn't deduplicate before saving, so we must do it here
        df = df.drop_duplicates(subset=[MATCH_KEY], keep="first")
        return df
    except Exception as exc:
        logger.error("Failed to read %s: %s", fpath, exc)
        return None


def _add_tuik_category(df):
    """Assigns the static TUIK category 05 for FiltaşYapı items."""
    enriched = df.copy()
    enriched["tuik_category"] = TUIK_CATEGORY_CODE
    return enriched


def _clean_metric(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 6)


def _compute_metrics(df_current, df_past):
    """Compute per-item, average, and TUIK-weighted inflation metrics."""
    df_current = _add_tuik_category(df_current)

    past_subset = df_past[[MATCH_KEY, PRICE_COLUMN]].rename(
        columns={PRICE_COLUMN: "past_price"}
    )
    merged = df_current.merge(past_subset, on=MATCH_KEY, how="left")

    merged["per_item_inflation"] = (
        (merged[PRICE_COLUMN] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")],
        pd.NA,
    )

    per_item = merged["per_item_inflation"].dropna()
    avg_inflation = per_item.mean() if not per_item.empty else None

    # TUIK weighted calculation
    cat_avg = merged.groupby("tuik_category")["per_item_inflation"].mean().dropna()
    if cat_avg.empty:
        tuik_weighted = None
    else:
        norm_w = normalised_weights(list(cat_avg.index))
        tuik_weighted = (
            sum(cat_avg[code] * norm_w.get(code, 100.0) / 100.0 for code in norm_w)
            if norm_w
            else None
        )

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation outputs for FiltaşYapı."""
    base_date = (
        datetime.strptime(target_date, "%Y-%m-%d")
        if target_date
        else datetime.today()
    )
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning("Cannot calculate inflation - no data for %s.", today_str)
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in [1, 7, 15, 30]
        }

    summary_row = {"date": today_str}
    detail_base = _add_tuik_category(df_today)

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info("Skipping interval %s - no data for %s.", label, past_str)
            detail_base[f"per_item_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past)
        match_count = int(merged["per_item_inflation"].notna().sum())

        detail_base = detail_base.merge(
            merged[[MATCH_KEY, "per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=MATCH_KEY,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = _clean_metric(avg_inf)
        summary_row[f"tuik_weighted_{label}"] = _clean_metric(tuik_w)
        logger.info(
            "[%s] matched=%d avg=%s tuik_weighted=%s",
            label,
            match_count,
            summary_row[f"avg_inflation_{label}"],
            summary_row[f"tuik_weighted_{label}"],
        )

    detail_file = INFLATION_OUT_DIR / f"filtasyapi_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info("Saved detailed inflation data to: %s", detail_file)

    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file, encoding="utf-8-sig")
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        else:
            df_final = df_summary

        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
        logger.info("Updated inflation summary in: %s", summary_file)
    except Exception as exc:
        logger.error("Failed to write summary file: %s", exc)


def calculate_all_history():
    """Finds all files in the data folder and runs the calculation chronologically."""
    if not DATA_DIR.exists():
        logger.error("Data folder not found: %s", DATA_DIR)
        return

    files = list(DATA_DIR.glob("FiltaşYapı_*.csv"))
    if not files:
        logger.warning("CSV files not found in %s", DATA_DIR)
        return

    dates = []
    for f in files:
        date_str = f.stem.replace("FiltaşYapı_", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            continue

    dates.sort()
    
    logger.info("Files found for processing: %d", len(dates))
    logger.info("Starting historical calculation...\n")

    for date_str in dates:
        calculate_inflation(date_str)
        
    logger.info("\nHistorical calculation complete. Summary updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FiltaşYapı inflation calculator")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument(
        "--compare",
        help="Comparison date (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Calculate inflation for all dates in directory"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    if args.all:
        calculate_all_history()
    else:
        calculate_inflation(args.date, args.compare)