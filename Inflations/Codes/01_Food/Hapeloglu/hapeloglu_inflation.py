"""
hapeloglu_inflation.py — Hapeloglu Daily Inflation Calculator

Computes inflation metrics for Hapeloglu market products:
  1. Per-item inflation — percentage price change per product
  2. Average inflation  — arithmetic mean of per-item rates
  3. TUIK weighted avg  — weighted average using TUIK 2026 CPI basket weights

Products are matched across dates without relying on product_id.
Matching order is:
  1. Unique image filename
  2. Unique URL slug without trailing numeric ID
  3. Unique normalised product name

Baby products (Bebek category) are excluded from calculation.

Intervals: 1d, 7d, 15d, 30d

Usage:
    python hapeloglu_inflation.py                    # Uses today's date
    python hapeloglu_inflation.py --date 2026-04-05  # Specific date
"""

import logging
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent
_PROJECT_ROOT = _CODES_DIR.parent.parent

sys.path.insert(0, str(_CODES_DIR))
from tuik_config import TUIK_WEIGHTS, normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "Markets" / "Hapeloglu"
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "Markets" / "Hapeloglu"

# Hapeloglu category -> TUIK code mapping
CATEGORY_TO_TUIK = {
    "Atistirmalik":           "01",
    "Et, Tavuk, Balik":       "01",
    "Firin, Pastane":         "01",
    "Meyve, Sebze":           "01",
    "Sut, Kahvaltilik":       "01",
    "Temel Gida":             "01",
    "Icecek":                 "01",
    "Deterjan, Temizlik":     "05",
    "Ev, Yasam":              "05",
    "Kisiel Bakim, Kozmetik": "12",
    "Kagit, Islak Mendil":    "12",
    "Evcil Hayvan":           "12",
}

# Normalised versions of category names (strip Turkish chars for matching)
_CATEGORY_NORMALIZE = {
    "Atıştırmalık":             "01",
    "Et, Tavuk, Balık":         "01",
    "Fırın, Pastane":           "01",
    "Meyve, Sebze":             "01",
    "Süt, Kahvaltılık":         "01",
    "Temel Gıda":               "01",
    "İçecek":                   "01",
    "Deterjan, Temizlik":       "05",
    "Ev, Yaşam":                "05",
    "Kişisel Bakım, Kozmetik":  "12",
    "Kağıt, Islak Mendil":      "12",
    "Evcil Hayvan":             "12",
}

EXCLUDED_CATEGORIES = {"Bebek"}
MATCH_ORDER = (
    ("image_key", "image"),
    ("slug_key", "slug"),
    ("name_key", "name"),
)
_TURKISH_TRANSLATION = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }
)


def _category_to_tuik(cat):
    if not cat or not isinstance(cat, str):
        return "01"
    cat = cat.strip()
    if cat in _CATEGORY_NORMALIZE:
        return _CATEGORY_NORMALIZE[cat]
    return "01"


def _load_csv(date_str):
    fpath = DATA_DIR / f"hapeloglu_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8")
        df["Product Cost"] = pd.to_numeric(df["Product Cost"], errors="coerce")
        # Exclude baby products
        df = df[~df["category"].isin(EXCLUDED_CATEGORIES)]
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _normalise_text(value):
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = text.translate(_TURKISH_TRANSLATION).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def _slug_without_numeric_id(url_value):
    if pd.isna(url_value):
        return None

    slug = Path(urlparse(str(url_value).strip()).path).name
    if not slug:
        return None

    slug = _normalise_text(slug)
    if slug is None:
        return None

    return re.sub(r"-\d+$", "", slug)


def _image_filename(url_value):
    if pd.isna(url_value):
        return None

    filename = Path(urlparse(str(url_value).strip()).path).name
    if not filename:
        return None

    return _normalise_text(filename)


def _prepare_match_frame(df):
    prepared = df.copy()
    if "__row_id" not in prepared.columns:
        prepared = prepared.reset_index(drop=True)
        prepared["__row_id"] = prepared.index

    prepared["tuik_category"] = prepared["category"].apply(_category_to_tuik)
    prepared["image_key"] = prepared["image_url"].apply(_image_filename)
    prepared["slug_key"] = prepared["product_url"].apply(_slug_without_numeric_id)
    prepared["name_key"] = prepared["Product Name"].apply(_normalise_text)
    return prepared


def _match_unique_rows(df_current, df_past, key_name, source_name):
    current_valid = df_current[df_current[key_name].notna() & (df_current[key_name] != "")]
    past_valid = df_past[df_past[key_name].notna() & (df_past[key_name] != "")]

    current_counts = current_valid[key_name].value_counts()
    past_counts = past_valid[key_name].value_counts()
    unique_keys = current_counts[current_counts == 1].index.intersection(
        past_counts[past_counts == 1].index
    )

    if unique_keys.empty:
        return pd.DataFrame()

    current_unique = current_valid[current_valid[key_name].isin(unique_keys)]
    past_unique = past_valid[past_valid[key_name].isin(unique_keys)]

    matches = current_unique.merge(
        past_unique[[key_name, "__row_id", "Product Cost"]].rename(
            columns={"__row_id": "__past_row_id", "Product Cost": "past_price"}
        ),
        on=key_name,
        how="inner",
    )
    matches["match_source"] = source_name
    return matches


def _match_products(df_current, df_past):
    current_remaining = _prepare_match_frame(df_current)
    past_remaining = _prepare_match_frame(df_past)
    matched_frames = []

    for key_name, source_name in MATCH_ORDER:
        step_matches = _match_unique_rows(
            current_remaining, past_remaining, key_name, source_name
        )
        if step_matches.empty:
            continue

        matched_frames.append(step_matches)
        current_remaining = current_remaining[
            ~current_remaining["__row_id"].isin(step_matches["__row_id"])
        ].copy()
        past_remaining = past_remaining[
            ~past_remaining["__row_id"].isin(step_matches["__past_row_id"])
        ].copy()

    if matched_frames:
        matched = pd.concat(matched_frames, ignore_index=True)
    else:
        matched = current_remaining.head(0).copy()
        matched["__past_row_id"] = pd.Series(dtype="Int64")
        matched["past_price"] = pd.Series(dtype="float64")
        matched["match_source"] = pd.Series(dtype="object")

    match_counts = matched["match_source"].value_counts().to_dict()
    logger.debug(
        "Matched Hapeloglu rows: total=%d image=%d slug=%d name=%d",
        len(matched),
        match_counts.get("image", 0),
        match_counts.get("slug", 0),
        match_counts.get("name", 0),
    )
    return matched


def _compute_metrics(df_current, df_past):
    merged = _match_products(df_current, df_past)

    merged["per_item_inflation"] = (
        (merged["Product Cost"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    avg_inflation = merged["per_item_inflation"].mean()

    cat_avg = merged.groupby("tuik_category")["per_item_inflation"].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(
        cat_avg[c] * norm_w[c] / 100.0
        for c in norm_w
        if c in cat_avg.index and pd.notna(cat_avg[c])
    )

    merged = merged[["__row_id", "tuik_category", "per_item_inflation"]].copy()
    return merged, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"Cannot calculate inflation - no data for {today_str}.")
        return
    df_today = df_today.reset_index(drop=True)
    df_today["__row_id"] = df_today.index

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    intervals = {}
    for days in [1, 7, 15, 30]:
        past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
        intervals[f"{days}d"] = past_str

    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = detail_base["category"].apply(_category_to_tuik)

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            detail_base[f"per_item_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[["__row_id", "per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on="__row_id",
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    # Save detailed data
    detail_file = INFLATION_OUT_DIR / f"hapeloglu_inflation_{today_str}.csv"
    detail_base = detail_base.drop(columns=["__row_id"], errors="ignore")
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info(f"Saved detailed inflation data to: {detail_file}")

    # Save / update summary
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    if summary_file.exists():
        df_existing = pd.read_csv(summary_file)
        df_existing = df_existing[df_existing["date"] != today_str]
        df_final = pd.concat([df_existing, df_summary], ignore_index=True)
        df_final.to_csv(summary_file, index=False, encoding="utf-8")
    else:
        df_summary.to_csv(summary_file, index=False, encoding="utf-8")
    logger.info(f"Updated inflation summary in: {summary_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hapeloglu inflation calculator")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    calculate_inflation(args.date)
