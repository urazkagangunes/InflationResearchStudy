"""
mersin_adana_rent_inflation.py — Mersin & Adana Daily Rent Inflation Calculator

Computes inflation metrics for rental properties in Mersin and Adana:
  1. Per-item inflation — percentage price change per listing (by District + Rooms)
  2. Average inflation  — arithmetic mean of per-item rates
  3. TUIK weighted avg  — weighted average using TUIK 2026 CPI basket weights

All rent listings map to TUIK category 04 (Housing, utilities).
Listings are matched across dates by District + Rooms.
Multiple listings per district+rooms are averaged before comparison.

Output is separated per city:
  - Detailed: {city}_rent_inflation_YYYY-MM-DD.csv
  - Summary:  {city}_inflation_summary.csv
Plus a combined summary across both cities.

Intervals: 1d, 7d, 15d, 30d

Usage:
    python mersin_adana_rent_inflation.py                  # Uses today's date
    python mersin_adana_rent_inflation.py --date 2026-05-01 # Specific date
    python mersin_adana_rent_inflation.py --all            # Calculates for all dates
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

sys.path.insert(0, str(_CODES_DIR))
try:
    from tuik_config import TUIK_WEIGHTS, normalised_weights
except ImportError:
    raise ImportError("Could not load tuik_config.py. Ensure it is in the _CODES_DIR.")

DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HousesRent"
# Output directory combining both cities
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "HousesRent" / "MersinAdana"

TUIK_CATEGORY = "04" 
CITIES = ["Mersin", "Adana"]


def _load_city_csv(city, date_str):
    """Loads and aggregates the daily CSV for a specific city."""
    filename = f"{city.lower()}_{date_str}.csv"
    fpath = DATA_DIR / city / filename
    
    if not fpath.exists():
        return None
        
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        
        aggregated = df.groupby(["District", "Rooms"], as_index=False).agg(
            {"Price": "mean"}
        )
        return aggregated
    except Exception as e:
        print(f"Failed to read {fpath}: {e}")
        return None


def _compute_city_metrics(df_current, df_past):
    """Computes inflation metrics between current and past dataframes."""
    match_cols = ["District", "Rooms"]

    past_subset = df_past[match_cols + ["Price"]].rename(
        columns={"Price": "past_price"}
    )
    merged = df_current.merge(past_subset, on=match_cols, how="inner")

    merged["per_item_inflation"] = (
        (merged["Price"] - merged["past_price"]) / merged["past_price"]
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

    match_cols = ["District", "Rooms"]

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

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 4) if pd.notnull(avg_inf) else None
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 4) if pd.notnull(tuik_w) else None

    # Save detailed data per city
    detail_file = city_out_dir / f"{city.lower()}_rent_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")

    # Save / update city summary
    summary_file = city_out_dir / f"{city.lower()}_inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file, encoding="utf-8-sig")
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8-sig")
        
    print(f"Calculated inflation for {city} -> {today_str}")

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

    city_results = {}
    for city in CITIES:
        result = _process_city(city, base_date, today_str, intervals)
        if result is not None:
            city_results[city] = result

    if not city_results:
        print(f"No data for any city on {today_str}.")
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
            round(sum(avg_vals) / len(avg_vals), 4) if avg_vals else None
        )
        combined_row[f"tuik_weighted_{label}"] = (
            round(sum(tuik_vals) / len(tuik_vals), 4) if tuik_vals else None
        )

    summary_file = INFLATION_OUT_DIR / "combined_inflation_summary.csv"
    df_summary = pd.DataFrame([combined_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file, encoding="utf-8-sig")
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8-sig")
        
    print(f"Combined summary updated for {today_str}")


def calculate_all_history():
    """Finds all distinct dates across all cities and runs the calculation chronologically."""
    all_dates = set()
    
    for city in CITIES:
        city_dir = DATA_DIR / city
        if city_dir.exists():
            files = list(city_dir.glob(f"{city.lower()}_*.csv"))
            for f in files:
                date_str = f.stem.replace(f"{city.lower()}_", "")
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                    all_dates.add(date_str)
                except ValueError:
                    continue

    dates = sorted(list(all_dates))
    
    if not dates:
        print(f"no valid CSV files found in {DATA_DIR}")
        return

    for date_str in dates:
        calculate_inflation(date_str)
        
    print("calculation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mersin & Adana rent inflation calculator"
    )
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument("--all", action="store_true", help="Calculate inflation for all dates in directory")
    args = parser.parse_args()
    
    if args.all:
        calculate_all_history()
    else:
        calculate_inflation(args.date)