"""
koctas_inflation.py — Koçtaş Daily Inflation Calculator

Intervals: 1d, 7d, 15d, 30d

Input  : koctas_YYYY.MM.DD.csv
Output :
  - koctas_inflation_YYYY.MM.DD.csv   — per-product detail
  - koctas_inflation_summary.csv      — one row per day
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
# Bu dosya: Inflations/Codes/TechnologicalProducts/Koçtaş/koctas_inflation.py
# Veri:     InflationItems/Datas/TechnologicalProducts/Koçtaş/
# Çıktı:    Inflations/Datas/TechnologicalProducts/Koçtaş/
REPO_ROOT  = _THIS_DIR.parents[3]
sys.path.insert(0, str(_THIS_DIR))
from koctas_tuik_config import normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "TechnologicalProducts" / "Koçtaş"
OUTPUT_DIR = REPO_ROOT / "Inflations"     / "Datas" / "TechnologicalProducts" / "Koçtaş"

# Yeni CSV formatı sadece product_name,price içeriyor — kategori yok.
# Koçtaş ürünleri ağırlıklı olarak ev aletleri / yapı: tek TUIK kodu 05.
_STORE_TUIK_CODE = "05"


def _date_to_str(dt):
    return dt.strftime("%Y.%m.%d")


def _load_csv(date_str):
    fpath = DATA_DIR / f"koctas_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Veri dosyası bulunamadı: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.drop_duplicates(subset=["product_name"])
        return df
    except Exception as e:
        logger.error(f"Dosya okunamadı {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    df_current = df_current.copy()
    df_current["tuik_category"] = _STORE_TUIK_CODE

    past_subset = df_past[["product_name", "price"]].rename(
        columns={"price": "past_price"}
    )
    merged = df_current.merge(past_subset, on=["product_name"], how="left")

    merged["per_item_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
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

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y.%m.%d")
    else:
        base_date = datetime.today()
    today_str = _date_to_str(base_date)

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"Hesaplama yapılamadı — {today_str} için veri yok.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{d}d": _date_to_str(base_date - timedelta(days=d))
            for d in [1, 7, 15, 30]
        }

    summary_row = {"tarih": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = _STORE_TUIK_CODE

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(f"Interval {label} atlandı — {past_str} verisi yok.")
            detail_base[f"per_item_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[["product_name", "per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=["product_name"],
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 6)
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 6)
        logger.info(f"  [{label}] avg={avg_inf:.4f}%  tuik_weighted={tuik_w:.4f}%")

    detail_file = OUTPUT_DIR / f"koctas_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detay dosyası kaydedildi: {detail_file}")

    summary_file = OUTPUT_DIR / "koctas_inflation_summary.csv"
    df_new = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file, encoding="utf-8-sig")
            df_existing = df_existing[df_existing["tarih"] != today_str]
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = df_new

        df_final.to_csv(summary_file, index=False, encoding="utf-8-sig")
        logger.info(f"Özet dosyası güncellendi: {summary_file}")
    except Exception as e:
        logger.error(f"Özet dosyası yazılamadı: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Koçtaş inflation calculator")
    parser.add_argument("--date", help="Hedef tarih (YYYY.MM.DD)", default=None)
    parser.add_argument("--compare", help="Karşılaştırma tarihi (YYYY.MM.DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    calculate_inflation(args.date, args.compare)