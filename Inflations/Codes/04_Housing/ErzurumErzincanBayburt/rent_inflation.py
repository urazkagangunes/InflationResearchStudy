"""
rent_inflation.py — ErzurumErzincanBayburt Daily Rent Inflation Calculator

Computes inflation metrics for rental properties in Erzurum, Erzincan, and Bayburt:
  1. Per-item inflation — percentage price change per listing
  2. Average inflation  — arithmetic mean of per-item rates
  3. TUIK weighted avg  — weighted average using TUIK 2026 CPI basket weights

All rent listings map to TUIK category 04 (Housing, utilities).
Listings are matched across dates by Product Name (district) + Rooms.
Multiple listings per district+rooms are averaged before comparison.

Output is separated per city:
  - Detailed: {city}_rent_inflation_YYYY-MM-DD.csv
  - Summary:  {city}_inflation_summary.csv
Plus a combined summary across all cities.

Intervals: 1d, 7d, 15d, 30d

Usage:
    python rent_inflation.py                    # Uses today's date
    python rent_inflation.py --date 2026-04-05  # Specific date
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

sys.path.insert(0, str(_CODES_DIR))
from tuik_config import TUIK_WEIGHTS, normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HousesRent" / "ErzurumErzincanBayburt"
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "HousesRent" / "ErzurumErzincanBayburt"

TUIK_CATEGORY = "04"  # All rent -> Housing
CITIES = ["Erzurum", "Erzincan", "Bayburt"]


def _load_city_csv(city, date_str):
    fpath = DATA_DIR / city / f"{city}_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8")
        df["Product Cost"] = pd.to_numeric(df["Product Cost"], errors="coerce")
        # Aggregate: average price per district+rooms
        aggregated = df.groupby(["Product Name", "Rooms"], as_index=False).agg(
            {"Product Cost": "mean"}
        )
        return aggregated
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_city_metrics(df_current, df_past):
    match_cols = ["Product Name", "Rooms"]

    past_subset = df_past[match_cols + ["Product Cost"]].rename(
        columns={"Product Cost": "past_price"}
    )
    merged = df_current.merge(past_subset, on=match_cols, how="inner")

    merged["per_item_inflation"] = (
        (merged["Product Cost"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    avg_inflation = merged["per_item_inflation"].mean()

    norm_w = normalised_weights([TUIK_CATEGORY])
    tuik_weighted = avg_inflation * norm_w.get(TUIK_CATEGORY, 100.0) / 100.0

    return merged, avg_inflation, tuik_weighted


def _process_city(city, base_date, today_str, intervals):
    """Process a single city: produce detailed + summary CSVs."""
    city_out_dir = INFLATION_OUT_DIR / city
    city_out_dir.mkdir(parents=True, exist_ok=True)

    df_today = _load_city_csv(city, today_str)
    if df_today is None:
        return None

    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = TUIK_CATEGORY

    match_cols = ["Product Name", "Rooms"]

    for label, past_str in intervals.items():
        df_past = _load_city_csv(city, past_str)

        if df_past is None:
            detail_base[f"per_item_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w = _compute_city_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[match_cols + ["per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=match_cols,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    # Save detailed data per city
    detail_file = city_out_dir / f"{city}_rent_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info(f"Saved {city} detailed data to: {detail_file}")

    # Save / update city summary
    summary_file = city_out_dir / f"{city}_inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file)
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8")
    logger.info(f"Updated {city} summary in: {summary_file}")

    return summary_row


def calculate_inflation(target_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    intervals = {}
    for days in [1, 7, 15, 30]:
        past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
        intervals[f"{days}d"] = past_str

    # Process each city separately
    city_results = {}
    for city in CITIES:
        result = _process_city(city, base_date, today_str, intervals)
        if result is not None:
            city_results[city] = result

    if not city_results:
        logger.warning(f"No data for any city on {today_str}.")
        return

    # Combined summary across all cities
    combined_row = {"date": today_str}
    for label in intervals:
        avg_vals = [
            r[f"avg_inflation_{label}"]
            for r in city_results.values()
            if r.get(f"avg_inflation_{label}") is not None
        ]
        tuik_vals = [
            r[f"tuik_weighted_{label}"]
            for r in city_results.values()
            if r.get(f"tuik_weighted_{label}") is not None
        ]
        combined_row[f"avg_inflation_{label}"] = (
            sum(avg_vals) / len(avg_vals) if avg_vals else None
        )
        combined_row[f"tuik_weighted_{label}"] = (
            sum(tuik_vals) / len(tuik_vals) if tuik_vals else None
        )

    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([combined_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file)
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8")
    logger.info(f"Updated combined summary in: {summary_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ErzurumErzincanBayburt rent inflation calculator"
    )
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    calculate_inflation(args.date)
