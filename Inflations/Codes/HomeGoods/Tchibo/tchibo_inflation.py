"""
tchibo_inflation.py - Tchibo Daily Price Inflation Calculator

Computes three inflation metrics for Tchibo "Ev & Yaşam" products:
  1. Per-Item Inflation    - per-product percentage price change
  2. Store Inflation       - MEDIAN of all per-product inflation rates
  3. TUIK Weighted Average - TUIK-weighted across categories; single store code
                             "05", so it equals the median store inflation

Product key: product_name (daily CSVs hold only product_name,price). Spring
2026 files write prices as text ("1.299,00 TL"), later files as numbers
("1299.0"); both are parsed.

Intervals: 1d, 7d, 15d, 30d back from target date (skipped if data missing).

Input files  : InflationItems/Datas/HomeGoods/Tchibo/
               tchibo_ev_yasam_YYYY-MM-DD.csv
Output files : Inflations/Datas/HomeGoods/Tchibo/
  - tchibo_inflation_YYYY-MM-DD.csv  - per-product detail
  - tchibo_inflation_summary.csv     - store summary, one row per day

Usage:
    python tchibo_inflation.py
    python tchibo_inflation.py --date 2026-09-29
    python tchibo_inflation.py --date 2026-09-29 --compare 2026-05-29
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ───────────────────────────────────────────────────────────────
# This file: Inflations/Codes/HomeGoods/Tchibo/tchibo_inflation.py
_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _THIS_DIR.parents[3]
sys.path.insert(0, str(_THIS_DIR))
from tchibo_tuik_config import normalised_weights  # noqa: E402

logger = logging.getLogger(__name__)

DATA_DIR = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Tchibo"
OUTPUT_DIR = REPO_ROOT / "Inflations" / "Datas" / "HomeGoods" / "Tchibo"

KEY = ["product_name"]

# The CSVs carry no category and the store sells home goods: one TUIK code.
_STORE_TUIK_CODE = "05"


# ── Data loading ─────────────────────────────────────────────────────────────
def _parse_price(values: pd.Series) -> pd.Series:
    """Parse "1.299,00 TL" style prices; plain "1299.0" values also work."""
    text = values.astype(str).str.replace(r"[^\d.,]", "", regex=True)
    has_comma = text.str.contains(",", regex=False, na=False)
    # With a decimal comma, any dot is a thousands separator.
    text = text.where(
        ~has_comma,
        text.str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
    )
    return pd.to_numeric(text, errors="coerce")


def _load_csv(date_str: str) -> pd.DataFrame | None:
    """Load a Tchibo daily CSV. Returns DataFrame or None."""
    fpath = DATA_DIR / f"tchibo_ev_yasam_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig", dtype={"price": str})
        df["price"] = _parse_price(df["price"])
        df = df.drop_duplicates(subset=KEY)
        return df
    except Exception as e:
        logger.error(f"Could not read {fpath}: {e}")
        return None


# ── Data-error guard ─────────────────────────────────────────────────────────
# A single-period price relative outside [1/4, 4] is implausible for homeware
# and is treated as a data error: the per-item detail keeps it, the
# store-level aggregates leave it out.
_PRICE_RELATIVE_MIN = 0.25
_PRICE_RELATIVE_MAX = 4.0


# ── Core metrics ─────────────────────────────────────────────────────────────
def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    """Compute the three inflation metrics between two DataFrames.

    Returns (merged_detail, avg_inflation, tuik_weighted, n_excluded).
    """
    df_current = df_current.copy()
    df_current["tuik_category"] = _STORE_TUIK_CODE

    past_subset = df_past[KEY + ["price"]].rename(
        columns={"price": "past_price"}
    )
    merged = df_current.merge(past_subset, on=KEY, how="left")

    # 1) Per-item inflation
    merged["per_item_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    ratio = merged["price"] / merged["past_price"]
    is_valid = merged["per_item_inflation"].notna() & ratio.between(
        _PRICE_RELATIVE_MIN, _PRICE_RELATIVE_MAX
    )
    n_excluded = int((merged["per_item_inflation"].notna() & ~is_valid).sum())
    clean = merged.loc[is_valid]

    # 2) Store-level inflation: the median, so a minority of wrong or variant
    #    prices that still fall inside the guard band cannot move it.
    avg_inflation = clean["per_item_inflation"].median()

    # 3) TUIK weighted average (cleaned set), median per category. With the
    #    single code "05" it equals avg_inflation; kept so the summary has the
    #    same columns as the other store calculators.
    cat_avg = clean.groupby("tuik_category")["per_item_inflation"].median()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(
        cat_avg[c] * norm_w[c] / 100.0
        for c in norm_w
        if c in cat_avg.index and pd.notna(cat_avg[c])
    )

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, avg_inflation, tuik_weighted, n_excluded


# ── Main calculator ──────────────────────────────────────────────────────────
def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for Tchibo."""
    base_date = (
        datetime.strptime(target_date, "%Y-%m-%d")
        if target_date
        else datetime.today()
    )
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"Cannot calculate: no data for {today_str}.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Intervals ────────────────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{d}d": (base_date - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in [1, 7, 15, 30]
        }

    # ── Per-interval computation ─────────────────────────────────────────────
    summary_row = {"tarih": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = _STORE_TUIK_CODE

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(f"Interval {label} skipped: no data for {past_str}.")
            detail_base[f"per_item_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w, n_excluded = _compute_metrics(
            df_today, df_past
        )

        detail_base = detail_base.merge(
            merged[KEY + ["per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=KEY,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 6)
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 6)
        excl_note = (
            f"  ({n_excluded} outlier prices excluded)" if n_excluded else ""
        )
        logger.info(
            f"  [{label}] avg={avg_inf:.4f}%  "
            f"tuik_weighted={tuik_w:.4f}%{excl_note}"
        )

    # ── Save detailed CSV ────────────────────────────────────────────────────
    detail_file = OUTPUT_DIR / f"tchibo_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detail file saved: {detail_file} ({len(detail_base)} rows)")

    # ── Save / update summary CSV ────────────────────────────────────────────
    summary_file = OUTPUT_DIR / "tchibo_inflation_summary.csv"
    df_new = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file, encoding="utf-8-sig")
            df_existing = df_existing[df_existing["tarih"] != today_str]
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = df_new

        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
        logger.info(f"Summary file updated: {summary_file}")
    except Exception as e:
        logger.error(f"Could not write summary file: {e}")


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tchibo inflation calculator")
    parser.add_argument(
        "--date", help="Target date (YYYY-MM-DD)", default=None
    )
    parser.add_argument(
        "--compare", help="Comparison date (YYYY-MM-DD)", default=None
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    calculate_inflation(args.date, args.compare)
