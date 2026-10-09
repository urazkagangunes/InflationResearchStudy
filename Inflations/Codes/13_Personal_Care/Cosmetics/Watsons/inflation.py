import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent  # inflationstudymirror

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import (  # noqa: E402
    normalised_weights,
)

DATA_DIR = _PROJECT_ROOT / "Datas" / "Cosmetics" / "Watson"
INFLATION_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Cosmetics"

logger = logging.getLogger(__name__)


def _load_csv(date_str: str):
    """Convert YYYY-MM-DD -> DD-MM-YYYY for Watson file lookup with column fallbacks."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        watson_date = date_obj.strftime("%d-%m-%Y")
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return None

    fpath = DATA_DIR / f"watsons_{watson_date}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, sep=";", encoding="utf-8-sig")

        name_col = "product-name" if "product-name" in df.columns else "name"
        price_col = "product-price" if "product-price" in df.columns else "price"

        if name_col not in df.columns or price_col not in df.columns:
            logger.error(f"Columns not found in {fpath}")
            return None

        df["shown_price"] = pd.to_numeric(df[price_col], errors="coerce")
        df["id"] = df[name_col]
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    df_current = df_current.copy()
    df_current["tuik_category"] = "12"  # Cosmetics group 12

    past_subset = (
        df_past[["id", "shown_price"]]
        .rename(columns={"shown_price": "past_price"})
    )
    merged = df_current.merge(past_subset, on="id", how="left")

    # 1) Basic inflation per product
    merged["basic_inflation"] = (
                                        (merged["shown_price"] - merged["past_price"]) / merged["past_price"]
                                ) * 100
    merged["basic_inflation"] = merged["basic_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Average inflation
    avg_inflation = merged["basic_inflation"].mean()

    # 3) Basket-level price-index change
    valid = merged.dropna(subset=["shown_price", "past_price"])
    sum_current = valid["shown_price"].sum()
    sum_past = valid["past_price"].sum()
    basic_inflation_index = (
        ((sum_current - sum_past) / sum_past) * 100 if sum_past else None
    )

    # 4) TUIK weighted average
    cat_avg = merged.groupby("tuik_category")["basic_inflation"].mean()
    present_codes = list(cat_avg.dropna().index)
    if present_codes:
        norm_w = normalised_weights(present_codes)
        tuik_weighted = sum(
            cat_avg[c] * norm_w[c] / 100.0
            for c in norm_w
            if c in cat_avg.index and pd.notna(cat_avg[c])
        )
    else:
        tuik_weighted = None

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    base_date = (
        datetime.strptime(target_date, "%Y-%m-%d")
        if target_date
        else datetime.today()
    )
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(
            f"Cannot calculate inflation – no data for {today_str}."
        )
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {}
        for days in [1, 7, 15, 30]:
            past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals[f"{days}d"] = past_str

    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = "12"

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(
                f"Skipping interval {label} – no data for {past_str}."
            )
            detail_base[f"basic_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[["id", "basic_inflation"]].rename(
                columns={"basic_inflation": f"basic_inflation_{label}"}
            ),
            on="id",
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    detail_file = INFLATION_OUT_DIR / f"watsons_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info(f"Saved detailed inflation data to: {detail_file}")

    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info(f"Updated inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info(f"Created inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watsons inflation calculator")
    parser.add_argument(
        "--date",
        help="Target date YYYY-MM-DD",
        default=None,
    )
    parser.add_argument(
        "--compare",
        help="Comparison date YYYY-MM-DD",
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_inflation(args.date, args.compare)