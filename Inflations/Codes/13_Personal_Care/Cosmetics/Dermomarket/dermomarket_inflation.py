"""
dermomarket_inflation.py — Dermomarket Daily Price Inflation Calculator

Computes three inflation metrics for Dermomarket products:
  1. Per-Item Inflation    – per-product percentage price change
  2. Average Inflation     – arithmetic mean of all per-product inflation rates
  3. TUIK Weighted Average – weighted average using TUIK 2026 CPI basket weights

Ürün anahtarı: product_name
(Yeni CSV formatı yalnızca product_name,price sütunlarını içerir.)

Intervals: 1d, 7d, 15d, 30d back from target date (skipped if data missing).

Input files  : dermomarket_YYYY-MM-DD.csv  (same folder as this script)
Output files :
  - dermomarket_inflation_YYYY-MM-DD.csv  — per-product detail
  - dermomarket_inflation_summary.csv     — store-level summary (one row per day)

Usage:
    python dermomarket_inflation.py
    python dermomarket_inflation.py --date 2026-04-21
    python dermomarket_inflation.py --date 2026-04-21 --compare 2026-04-14
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
# Bu dosya: Inflations/Codes/Cosmetics/Dermomarket/dermomarket_inflation.py
# Veri:     InflationItems/Datas/Cosmetics/Dermomarket/
# Çıktı:    Inflations/Datas/Cosmetics/Dermomarket/
_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT  = _THIS_DIR.parents[3]
sys.path.insert(0, str(_THIS_DIR))
from dermomarket_tuik_config import normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "Cosmetics" / "Dermomarket"
OUTPUT_DIR = REPO_ROOT / "Inflations"     / "Datas" / "Cosmetics" / "Dermomarket"

KEY = ["product_name"]

# Yeni CSV formatı sadece product_name,price içeriyor — kategori yok.
# Dermomarket ürünleri ağırlıklı olarak kişisel bakım: tek TUIK kodu 13.
_STORE_TUIK_CODE = "13"


# ── Data loading ──────────────────────────────────────────────────────────────
def _load_csv(date_str: str) -> pd.DataFrame | None:
    """Load a Dermomarket daily CSV. Returns DataFrame or None."""
    fpath = DATA_DIR / f"dermomarket_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Veri dosyası bulunamadı: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.drop_duplicates(subset=KEY)
        return df
    except Exception as e:
        logger.error(f"Dosya okunamadı {fpath}: {e}")
        return None


# ── Core metrics ──────────────────────────────────────────────────────────────
def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    """Compute the three inflation metrics between two DataFrames.

    Returns
    -------
    df_detail     : DataFrame — per-product rows with per_item_inflation column
    avg_inflation : float     — arithmetic mean of per-product inflation rates
    tuik_weighted : float     — TUIK-weighted average inflation
    """
    df_current = df_current.copy()
    df_current["tuik_category"] = _STORE_TUIK_CODE

    past_subset = df_past[KEY + ["price"]].rename(columns={"price": "past_price"})
    merged = df_current.merge(past_subset, on=KEY, how="left")

    # 1) Per-item inflation
    merged["per_item_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Average inflation
    avg_inflation = merged["per_item_inflation"].mean()

    # 3) TUIK weighted average
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


# ── Main calculator ───────────────────────────────────────────────────────────
def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for Dermomarket."""
    base_date = datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"Hesaplama yapılamadı — {today_str} için veri yok.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Intervals ─────────────────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{d}d": (base_date - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in [1, 7, 15, 30]
        }

    # ── Per-interval computation ──────────────────────────────────────────────
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
            merged[KEY + ["per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=KEY,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 6)
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 6)
        logger.info(f"  [{label}] avg={avg_inf:.4f}%  tuik_weighted={tuik_w:.4f}%")

    # ── Save detailed CSV ──────────────────────────────────────────────────────
    detail_file = OUTPUT_DIR / f"dermomarket_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detay dosyası kaydedildi: {detail_file} ({len(detail_base)} satır)")

    # ── Save / update summary CSV ─────────────────────────────────────────────
    summary_file = OUTPUT_DIR / "dermomarket_inflation_summary.csv"
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


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dermomarket inflation calculator")
    parser.add_argument("--date",    help="Hedef tarih (YYYY-MM-DD)", default=None)
    parser.add_argument("--compare", help="Karşılaştırma tarihi (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    calculate_inflation(args.date, args.compare)
