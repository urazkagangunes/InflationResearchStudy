import logging
import sys
import argparse
from datetime import datetime, timedelta
import os
import pandas as pd

# ── RELATIVE PATH SETUP ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "Datas", "HousesRent")
INFLATION_OUT_DIR_BASE = os.path.join(PROJECT_ROOT, "Inflations", "Datas", "HousesRent")

logger = logging.getLogger(__name__)

CITIES = ["Kayseri", "Sivas", "Tokat"]

TUIK_WEIGHTS = {
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar", "weight": 11.40}
}


def normalised_weights(present_codes):
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ── Core Functions ────────────────────────────────────────────────────────────
def _load_and_group(city, date_str):
    """Loads CSV, applies structural parsing fixes, and runs outlier insulation."""
    fpath = os.path.join(RAW_DATA_DIR, city, f"{date_str}.csv")

    if not os.path.exists(fpath):
        return None

    try:
        df = pd.read_csv(fpath, usecols=['District', 'Rooms', 'Price'])

        # 1) Duplicate Detection
        df = df.drop_duplicates()

        # 2) Standardized Price Clean (Handles raw numbers, floats, and strings)
        clean_price = df['Price'].astype(str).str.replace(' TL', '', regex=False).str.strip()
        clean_price = clean_price.apply(lambda x: x[:-2] if x.endswith('.0') else x)
        df['Price_Num'] = pd.to_numeric(clean_price.str.replace('.', '', regex=False), errors='coerce')

        # 3) Protection 1: Global Hard Boundaries (Filters out extreme data entry typos)
        df = df[(df['Price_Num'] >= 1500) & (df['Price_Num'] <= 500000)]

        if df.empty:
            return None

        # 4) Outlier Detection via Vectorized IQR
        q1 = df.groupby(['District', 'Rooms'])['Price_Num'].transform('quantile', 0.25)
        q3 = df.groupby(['District', 'Rooms'])['Price_Num'].transform('quantile', 0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        counts = df.groupby(['District', 'Rooms'])['Price_Num'].transform('count')

        # Filter rows using IQR for segments with sufficient data
        df = df[(counts < 4) | ((df['Price_Num'] >= lower_bound) & (df['Price_Num'] <= upper_bound))]

        # Median Aggregation
        grouped = df.groupby(['District', 'Rooms'])['Price_Num'].median().reset_index()
        grouped.rename(columns={'Price_Num': 'median_price'}, inplace=True)
        return grouped
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    """Computes inflation metrics using mathematical bound shields."""
    df_current = df_current.copy()
    df_current['tuik_category'] = "04"

    past_subset = df_past[['District', 'Rooms', 'median_price']].rename(columns={'median_price': 'past_price'})
    merged = df_current.merge(past_subset, on=['District', 'Rooms'], how='inner')

    # Protection 2: Minimum Overlap Shield (Prevents calculations on collapsed sample spaces)
    if len(merged) < 3:
        logger.warning(f"Aborting calculation: insufficient segment overlap count ({len(merged)} found).")
        return None, None, None, None

    # 1) Segment inflation calculation
    merged['basic_inflation'] = ((merged['median_price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA).dropna()

    # Protection 3: Micro-Segment Variance Clipping (Clips impossible short-term segment spikes)
    merged['basic_inflation'] = merged['basic_inflation'].clip(lower=-75.0, upper=100.0)

    # 2) Average inflation
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Basket General Index
    sum_current = merged['median_price'].sum()
    sum_past = merged['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK weighted average
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)

    valid_terms = [cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c])]
    tuik_weighted = sum(valid_terms) if valid_terms else None

    merged.drop(columns=['past_price'], errors='ignore', inplace=True)
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(city, target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_and_group(city, today_str)
    if df_today is None:
        logger.warning(f"Skipping {city} – no target data found for {today_str}.")
        return

    city_out_dir = os.path.join(INFLATION_OUT_DIR_BASE, city)
    os.makedirs(city_out_dir, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d") for days in [1, 7, 15, 30]}

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = "04"

    for label, past_str in intervals.items():
        df_past = _load_and_group(city, past_str)

        if df_past is None:
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'basket_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        if merged is None:
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'basket_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        detail_base = detail_base.merge(
            merged[['District', 'Rooms', 'basic_inflation']].rename(
                columns={'basic_inflation': f'basic_inflation_{label}'}
            ),
            on=['District', 'Rooms'], how='left'
        )

        summary_row[f'basket_inflation_{label}'] = basic_idx
        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # Save outputs
    detail_file = os.path.join(city_out_dir, f"{city}_inflation_{today_str}.csv")
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')

    summary_file = os.path.join(city_out_dir, f"{city}_inflation_summary.csv")
    df_summary = pd.DataFrame([summary_row])

    try:
        if os.path.exists(summary_file):
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
    except Exception as e:
        logger.error(f"[{city}] Failed to write summary file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-City rent inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    for current_city in CITIES:
        logger.info(f"--- Processing city: {current_city} ---")
        calculate_inflation(current_city, args.date, args.compare)