"""
inflation.py — Karaca daily inflation calculator.

Computes per-product inflation, simple average inflation, and TUIK-weighted
inflation for Karaca catalog snapshots.
"""

import argparse
import importlib.util
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

_tuik_config_path = _THIS_DIR / "tuik_config.py"
_tuik_spec = importlib.util.spec_from_file_location("karaca_tuik_config", _tuik_config_path)
if _tuik_spec is None or _tuik_spec.loader is None:
    raise ImportError(f"Could not load local TUIK config from {_tuik_config_path}")
_tuik_config = importlib.util.module_from_spec(_tuik_spec)
_tuik_spec.loader.exec_module(_tuik_config)
karaca_category_to_tuik = _tuik_config.karaca_category_to_tuik
normalised_weights = _tuik_config.normalised_weights

try:
    _SCRAPER_DIR = (
        _PROJECT_ROOT / "InflationItems" / "Codes" / "HomeGoods" / "Karaca" / "scripts"
    )
    _config_path = _SCRAPER_DIR / "config.py"
    _spec = importlib.util.spec_from_file_location("karaca_scraper_config", _config_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not load scraper config from {_config_path}")
    _config = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_config)
    DATA_DIR = Path(_config.OUTPUT_DIR)
except Exception:
    DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Karaca"

INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "HomeGoods" / "Karaca"
MATCH_KEY = "Product ID"
PRICE_COLUMN = "price"
NAME_COLUMN = "product_name"
_LEGACY_COLUMNS = {"Product Name": NAME_COLUMN, "Product Cost": PRICE_COLUMN}
# Files without a Product ID can only be matched on the product name.
NAME_KEY = "_name_key"
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")

logger = logging.getLogger(__name__)


def _normalise_name(name):
    """Normalise a product name the same way turkey_inflation.py does."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.translate(_TR_MAP).lower().strip())


def _average_duplicates(df, key):
    """Keep one row per key with its mean price, like turkey_inflation.py."""
    df = df[df[key].notna() & (df[key] != "")]
    df = df.assign(**{
        PRICE_COLUMN: df.groupby(key)[PRICE_COLUMN].transform("mean")
    })
    return df.drop_duplicates(subset=[key])


def _match_key(df_a, df_b):
    """Match on Product ID when both files carry it, otherwise on the name."""
    if MATCH_KEY in df_a.columns and MATCH_KEY in df_b.columns:
        return MATCH_KEY
    return NAME_KEY


def _load_csv(date_str):
    """Load one Karaca daily snapshot for the given date."""
    fpath = DATA_DIR / f"karaca_{date_str}.csv"
    if not fpath.exists():
        logger.info("Data file not found: %s", fpath)
        return None

    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df = df.rename(columns={
            old: new for old, new in _LEGACY_COLUMNS.items()
            if new not in df.columns
        })
        df[PRICE_COLUMN] = pd.to_numeric(df[PRICE_COLUMN], errors="coerce")
        df[NAME_KEY] = df[NAME_COLUMN].map(_normalise_name)
        if MATCH_KEY not in df.columns:
            return _average_duplicates(df, NAME_KEY)
        df[MATCH_KEY] = df[MATCH_KEY].astype("string").str.strip()
        df = df[df[MATCH_KEY].notna() & (df[MATCH_KEY] != "")]
        df = df.drop_duplicates(subset=[MATCH_KEY])
        return df
    except Exception as exc:
        logger.error("Failed to read %s: %s", fpath, exc)
        return None


def _add_tuik_category(df):
    enriched = df.copy()
    enriched["tuik_category"] = enriched.apply(
        lambda row: karaca_category_to_tuik(
            row.get("Main Category"),
            row.get("Top Category"),
        ),
        axis=1,
    )
    return enriched


def _clean_metric(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 6)


def _compute_metrics(df_current, df_past, key):
    """Compute per-item, average, and TUIK-weighted inflation metrics."""
    df_current = _add_tuik_category(_average_duplicates(df_current, key))

    past_subset = _average_duplicates(df_past, key)[[key, PRICE_COLUMN]]
    past_subset = past_subset.rename(columns={PRICE_COLUMN: "past_price"})
    merged = df_current.merge(past_subset, on=key, how="left")

    merged["per_item_inflation"] = (
        (merged[PRICE_COLUMN] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")],
        pd.NA,
    )

    per_item = merged["per_item_inflation"].dropna()
    avg_inflation = per_item.mean() if not per_item.empty else None

    cat_avg = merged.groupby("tuik_category")["per_item_inflation"].mean().dropna()
    if cat_avg.empty:
        tuik_weighted = None
    else:
        norm_w = normalised_weights(list(cat_avg.index))
        tuik_weighted = (
            sum(cat_avg[code] * norm_w[code] / 100.0 for code in norm_w)
            if norm_w
            else None
        )

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation outputs for Karaca."""
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

        key = _match_key(df_today, df_past)
        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past, key)
        match_count = int(merged["per_item_inflation"].notna().sum())

        detail_base = detail_base.merge(
            merged[[key, "per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=key,
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

    detail_file = INFLATION_OUT_DIR / f"karaca_inflation_{today_str}.csv"
    detail_base.drop(columns=[NAME_KEY]).to_csv(
        detail_file, index=False, encoding="utf-8-sig"
    )
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Karaca inflation calculator")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument(
        "--compare",
        help="Comparison date (YYYY-MM-DD)",
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_inflation(args.date, args.compare)
