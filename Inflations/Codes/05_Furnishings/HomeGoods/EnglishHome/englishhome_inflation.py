"""
englishhome_inflation.py — English Home Daily Price Inflation Calculator

Computes three inflation metrics for English Home products:
  1. Per-Item Inflation    – per-product percentage price change
  2. Store Inflation       – MEDIAN of all per-product inflation rates (robust;
                             the mean is unsafe here — see _compute_metrics)
  3. TUIK Weighted Average – TUIK-weighted across categories; single store code
                             "05" → equals the median store inflation

Ürün anahtarı: product_name
(Yeni CSV formatı yalnızca product_name,price sütunlarını içerir.)

Intervals: 1d, 7d, 15d, 30d back from target date (skipped if data missing).

Input files  : englishhome_YYYY-MM-DD.csv  (same folder as this script)
Output files :
  - englishhome_inflation_YYYY-MM-DD.csv  — per-product detail
  - englishhome_inflation_summary.csv     — store-level summary (one row per day)

Usage:
    python englishhome_inflation.py
    python englishhome_inflation.py --date 2026-04-28
    python englishhome_inflation.py --date 2026-04-28 --compare 2026-04-21
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
# Bu dosya: Inflations/Codes/HomeGoods/EnglishHome/englishhome_inflation.py
# Veri:     InflationItems/Datas/HomeGoods/EnglishHome/
# Çıktı:    Inflations/Datas/HomeGoods/EnglishHome/
_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT  = _THIS_DIR.parents[3]
sys.path.insert(0, str(_THIS_DIR))
from englishhome_tuik_config import normalised_weights

logger = logging.getLogger(__name__)

DATA_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "EnglishHome"
OUTPUT_DIR = REPO_ROOT / "Inflations"     / "Datas" / "HomeGoods" / "EnglishHome"

KEY = ["product_name"]

# Yeni CSV formatı sadece product_name,price içeriyor — kategori yok.
# English Home zaten ev eşyası sitesi: tek TUIK kodu 05.
_STORE_TUIK_CODE = "05"


# ── Data loading ──────────────────────────────────────────────────────────────
def _load_csv(date_str: str) -> pd.DataFrame | None:
    """Load an English Home daily CSV. Returns DataFrame or None."""
    fpath = DATA_DIR / f"englishhome_{date_str}.csv"
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


# ── Data-error guard ──────────────────────────────────────────────────────────
# English Home's listing intermittently serves inflated / wrong-variant prices
# (a product can read 5–10× its real price on some scrapes; observed 2026-05-31).
# A single-period price relative outside [1/4, 4] is implausible for homeware and
# is treated as a DATA ERROR — excluded from the store-level aggregates so a
# corrupted minority cannot blow up the number. This is standard price-index
# practice (extreme price relatives are trimmed before averaging). The per-item
# detail still keeps every value; only the aggregates use the cleaned set.
_PRICE_RELATIVE_MIN = 0.25   # price fell below 1/4  → data error
_PRICE_RELATIVE_MAX = 4.0    # price more than 4×    → data error


# ── Core metrics ──────────────────────────────────────────────────────────────
def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    """Compute the three inflation metrics between two DataFrames.

    Returns (merged_detail, avg_inflation, tuik_weighted, n_excluded).
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

    # Data-error guard: keep only plausible price relatives for the aggregates.
    ratio = merged["price"] / merged["past_price"]
    is_valid = merged["per_item_inflation"].notna() & ratio.between(
        _PRICE_RELATIVE_MIN, _PRICE_RELATIVE_MAX
    )
    n_excluded = int((merged["per_item_inflation"].notna() & ~is_valid).sum())
    clean = merged.loc[is_valid]

    # 2) Store-level inflation — MEDIAN of per-item changes (cleaned set).
    #    English Home intermittently serves wrong/variant prices that land
    #    INSIDE the [1/4, 4] guard band (typically 1.5x–2x jumps on a minority
    #    of cologne/towel/perfume cards). The arithmetic mean is hijacked by that
    #    right tail (e.g. 2026-06-05: 1d mean +7.87% vs median 0.00%), so we
    #    report the median — the change of the TYPICAL product — which is immune
    #    to the tail by construction (standard median-CPI / trimmed-mean practice).
    avg_inflation = clean["per_item_inflation"].median()

    # 3) TUIK weighted average (cleaned set) — median per category.
    #    Single store → single TUIK code "05", so this equals avg_inflation;
    #    kept for schema/report compatibility (run_all.py reads tuik_weighted_*).
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


# ── Main calculator ───────────────────────────────────────────────────────────
def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for English Home."""
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

        merged, avg_inf, tuik_w, n_excluded = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[KEY + ["per_item_inflation"]].rename(
                columns={"per_item_inflation": f"per_item_inflation_{label}"}
            ),
            on=KEY,
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = round(avg_inf, 6)
        summary_row[f"tuik_weighted_{label}"] = round(tuik_w, 6)
        excl_note = f"  ({n_excluded} aykırı fiyat hariç tutuldu)" if n_excluded else ""
        logger.info(f"  [{label}] avg={avg_inf:.4f}%  tuik_weighted={tuik_w:.4f}%{excl_note}")

    # ── Save detailed CSV ──────────────────────────────────────────────────────
    detail_file = OUTPUT_DIR / f"englishhome_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detay dosyası kaydedildi: {detail_file} ({len(detail_base)} satır)")

    # ── Save / update summary CSV ─────────────────────────────────────────────
    summary_file = OUTPUT_DIR / "englishhome_inflation_summary.csv"
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
    parser = argparse.ArgumentParser(description="English Home inflation calculator")
    parser.add_argument("--date",    help="Hedef tarih (YYYY-MM-DD)", default=None)
    parser.add_argument("--compare", help="Karşılaştırma tarihi (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    calculate_inflation(args.date, args.compare)
