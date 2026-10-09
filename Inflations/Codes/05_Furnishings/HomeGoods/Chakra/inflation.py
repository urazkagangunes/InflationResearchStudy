import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent
# Repo root and category folder come from this file's path
# (Inflations/Codes/<category>/Chakra), so they hold in any category layout.
_PARTS        = _THIS_DIR.parts
_ROOT         = _PARTS.index("Inflations")
_PROJECT_ROOT = Path(*_PARTS[:_ROOT])
_CATEGORY     = Path(*_PARTS[_ROOT + 2:-1])

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import (  # noqa: E402
    normalised_weights,
)

# Daily CSVs written by the Chakra scraper
DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / _CATEGORY / "Chakra"

logger = logging.getLogger(__name__)

# ── Output directory ──────────────────────────────────────────────────────────
INFLATION_OUT_DIR = (
    _PROJECT_ROOT / "Inflations" / "Datas" / _CATEGORY / "Chakra"
)

# Files without an id column can only be matched on the product name.
NAME_KEY = "_name_key"
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")


def _normalise_name(name):
    """Normalise a product name the same way turkey_inflation.py does."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.translate(_TR_MAP).lower().strip())


def _load_csv(date_str: str):
    """Load Chakra daily CSV; older file names use underscores in the date."""
    for date_token in (date_str, date_str.replace("-", "_")):
        fpath = DATA_DIR / f"chakra_all_categories_{date_token}.csv"
        if fpath.exists():
            break
    else:
        logger.info(f"Data file not found for {date_str} in {DATA_DIR}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        name_col = "product_name" if "product_name" in df.columns else "name"
        df[NAME_KEY] = df[name_col].map(_normalise_name)
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _match_key(df_a: pd.DataFrame, df_b: pd.DataFrame):
    """Match on id when both files carry it, otherwise on the product name."""
    if all("id" in df and df["id"].notna().any() for df in (df_a, df_b)):
        return "id"
    return NAME_KEY


def _average_duplicates(df: pd.DataFrame, key: str):
    """Keep one row per key with its mean price, like turkey_inflation.py."""
    df = df[df[key].notna() & (df[key] != "")]
    mean_price = df.groupby(key)["price"].transform("mean")
    return df.assign(price=mean_price).drop_duplicates(subset=[key])


def _compute_metrics(
    df_current: pd.DataFrame, df_past: pd.DataFrame, key: str
):
    """Compute inflation metrics using 'price' column and TUIK group 05."""
    df_current = _average_duplicates(df_current, key)
    df_current["tuik_category"] = "05"  # Default all to HomeGoods group 05

    past_subset = (
        _average_duplicates(df_past, key)[[key, "price"]]
        .rename(columns={"price": "past_price"})
    )
    merged = df_current.merge(past_subset, on=key, how="left")

    # 1) Basic inflation per product
    merged["basic_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["basic_inflation"] = merged["basic_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Average inflation
    avg_inflation = merged["basic_inflation"].mean()

    # 3) Basket-level price-index change
    valid = merged.dropna(subset=["price", "past_price"])
    sum_current = valid["price"].sum()
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

    # ── Determine intervals ──────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {}
        for days in [1, 7, 15, 30]:
            past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals[f"{days}d"] = past_str

    # ── Per-interval computation ─────────────────────────────────────────────
    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = "05"

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

        key = _match_key(df_today, df_past)
        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(
            df_today, df_past, key
        )

        detail_base = detail_base.merge(
            merged[[key, "basic_inflation"]].rename(
                columns={"basic_inflation": f"basic_inflation_{label}"}
            ),
            on=key,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    # ── Save detailed data ───────────────────────────────────────────────────
    detail_file = INFLATION_OUT_DIR / f"chakra_inflation_{today_str}.csv"
    detail_base.drop(columns=[NAME_KEY]).to_csv(
        detail_file, index=False, encoding="utf-8"
    )
    logger.info(f"Saved detailed inflation data to: {detail_file}")

    # ── Save / update summary ────────────────────────────────────────────────
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

    parser = argparse.ArgumentParser(description="Chakra inflation calculator")
    parser.add_argument(
        "--date",
        help="Target (current) date in YYYY-MM-DD format",
        default=None,
    )
    parser.add_argument(
        "--compare",
        help="Comparison (past) date in YYYY-MM-DD format",
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_inflation(args.date, args.compare)