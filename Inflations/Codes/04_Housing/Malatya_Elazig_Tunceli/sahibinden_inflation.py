"""
sahibinden_inflation.py — Sahibinden Daily Rental Inflation Calculator

Computes three inflation metrics for Sahibinden rental listings:
  1. Per-Item Inflation    – per-listing percentage price change
  2. Average Inflation     – arithmetic mean of all per-listing inflation rates
  3. TUIK Weighted Average – weighted average using TUIK 2026 CPI basket weights,
                             normalised to the cities present

Intervals: 1d, 7d, 15d, 30d back from target date (skipped if data missing).

Şehirler: malatya, elazig, tunceli
Ürün anahtarı: product_name (District + Rooms birleşimi)

Input files  : {city}_rentals_YYYY_MM_DD.csv  (same folder as this script)
Output files :
  - sahibinden_inflation_YYYY-MM-DD.csv  — per-listing detail (tüm şehirler)
  - sahibinden_inflation_summary.csv     — store-level summary (one row per day)

Usage:
    python sahibinden_inflation.py                    # today
    python sahibinden_inflation.py --date 2026-03-21  # specific date
    python sahibinden_inflation.py --date 2026-03-21 --compare 2026-03-14
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
# Bu dosya: Inflations/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation.py
# Veri:     InflationItems/Datas/HousesRent/Malatya_Elazig_Tunceli/<Şehir>/
# Çıktı:    Inflations/Datas/HousesRent/Malatya_Elazig_Tunceli/
_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT  = _THIS_DIR.parents[3]
sys.path.insert(0, str(_THIS_DIR))
from sahibinden_tuik_config import sahibinden_city_to_tuik, normalised_weights

logger = logging.getLogger(__name__)

_BASE_DATA = REPO_ROOT / "InflationItems" / "Datas" / "HousesRent" / "Malatya_Elazig_Tunceli"
CITY_DATA_DIRS = {
    "malatya": _BASE_DATA / "Malatya",
    "elazig":  _BASE_DATA / "Elazig",
    "tunceli": _BASE_DATA / "Tunceli",
}
OUTPUT_DIR = REPO_ROOT / "Inflations" / "Datas" / "HousesRent" / "Malatya_Elazig_Tunceli"

CITIES = ["malatya", "elazig", "tunceli"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_price(price_str) -> float | None:
    """Fiyat degerini float'a cevirir. Yeni format: 17999.0 | Eski format: '13.000 TL'"""
    if pd.isna(price_str) or str(price_str).strip() == "":
        return None
    cleaned = (
        str(price_str)
        .replace("TL", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


# ── Data loading ──────────────────────────────────────────────────────────────
def _load_csv(city: str, date_str: str) -> pd.DataFrame | None:
    """
    Load a Sahibinden daily CSV for a city.
    date_str format: 'YYYY-MM-DD'  →  file: {city}_rentals_YYYY_MM_DD.csv
    """
    file_date = date_str.replace("-", ".")
    fpath = CITY_DATA_DIRS[city] / f"{city}_rentals_{file_date}.csv"
    if not fpath.exists():
        logger.info(f"Veri dosyası bulunamadı: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["price_numeric"] = df["price"].apply(_parse_price)
        df = df[df["price_numeric"].notna()]

        # IQR outlier filtresi — şehir genelinde aşırı uç fiyatları at
        q1 = df["price_numeric"].quantile(0.25)
        q3 = df["price_numeric"].quantile(0.75)
        iqr = q3 - q1
        df = df[
            (df["price_numeric"] >= q1 - 3.0 * iqr) &
            (df["price_numeric"] <= q3 + 3.0 * iqr)
        ]

        # Dedup: aynı product_name kombinasyonu → medyan fiyatı tut
        df = (
            df.groupby(["product_name"], as_index=False)["price_numeric"]
            .median()
            .rename(columns={"price_numeric": "price_numeric"})
        )
        return df
    except Exception as e:
        logger.error(f"Dosya okunamadı {fpath}: {e}")
        return None


# ── Core metrics ──────────────────────────────────────────────────────────────
def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame, city: str):
    """
    Compute the three inflation metrics between two DataFrames for a single city.

    Returns
    -------
    df_detail     : DataFrame — per-listing rows with per_item_inflation column
    avg_inflation : float     — arithmetic mean of per-listing inflation rates
    tuik_weighted : float     — TUIK-weighted average inflation
    """
    df_current = df_current.copy()
    df_current["city"] = city
    df_current["tuik_category"] = sahibinden_city_to_tuik(city)

    # Merge past prices by product_name
    past_subset = df_past[["product_name", "price_numeric"]].rename(
        columns={"price_numeric": "past_price"}
    )
    merged = df_current.merge(past_subset, on=["product_name"], how="left")

    # 1) Per-item inflation
    merged["per_item_inflation"] = (
        (merged["price_numeric"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["per_item_inflation"] = merged["per_item_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # ── Inflation-level IQR outlier filter ──────────────────────────────────
    # Fiyat-bazlı IQR (_load_csv) tek günün uç fiyatlarını atar ama
    # iki gün arasındaki absürt yüzde değişimleri yakalayamaz
    # (örn. 1.400→30.000 TL = %2042). Bu filtre per-item inflation
    # değerlerinin kendisine IQR×3.0 uygulayarak ortalamayı koruyor.
    #
    # Edge case: 1d gibi kısa intervallerde çoğu grup %0 değişim gösterir,
    # IQR=0 olur ve filtre sınırları [0,0]'a çöker → her non-zero değer
    # atılır. Minimum IQR tabanı (10 yüzde puan) bu durumu önler:
    # taban ile sınırlar en az ±30pp olur, gerçek outlier'lar hâlâ yakalanır.
    _inf_vals = merged["per_item_inflation"].dropna()
    if len(_inf_vals) >= 4:
        _q1 = _inf_vals.quantile(0.25)
        _q3 = _inf_vals.quantile(0.75)
        _iqr = max(_q3 - _q1, 10.0)
        _inf_lower = _q1 - 3.0 * _iqr
        _inf_upper = _q3 + 3.0 * _iqr
        merged.loc[
            merged["per_item_inflation"].notna() & (
                (merged["per_item_inflation"] < _inf_lower) |
                (merged["per_item_inflation"] > _inf_upper)
            ),
            "per_item_inflation",
        ] = pd.NA

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
    """Calculate inflation metrics for all Sahibinden cities."""
    base_date = datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Intervals ─────────────────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{d}d": (base_date - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in [1, 7, 15, 30]
        }

    all_detail_frames = []
    summary_row = {"tarih": today_str}

    # ── Per-city computation ──────────────────────────────────────────────────
    for city in CITIES:
        df_today = _load_csv(city, today_str)
        if df_today is None:
            logger.warning(f"[{city}] {today_str} verisi yok, atlandı.")
            continue

        city_detail = df_today.copy()
        city_detail["city"] = city
        city_detail["tuik_category"] = sahibinden_city_to_tuik(city)

        for label, past_str in intervals.items():
            df_past = _load_csv(city, past_str)

            if df_past is None:
                logger.info(f"[{city}] Interval {label} atlandı — {past_str} verisi yok.")
                city_detail[f"per_item_inflation_{label}"] = None
                summary_row[f"{city}_avg_inflation_{label}"] = None
                summary_row[f"{city}_tuik_weighted_{label}"] = None
                continue

            merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past, city)

            city_detail = city_detail.merge(
                merged[["product_name", "per_item_inflation"]].rename(
                    columns={"per_item_inflation": f"per_item_inflation_{label}"}
                ),
                on=["product_name"],
                how="left",
            )

            summary_row[f"{city}_avg_inflation_{label}"] = round(avg_inf, 6)
            summary_row[f"{city}_tuik_weighted_{label}"] = round(tuik_w, 6)
            logger.info(
                f"  [{city}][{label}] avg={avg_inf:.4f}%  tuik_weighted={tuik_w:.4f}%"
            )

        all_detail_frames.append(city_detail)

    if not all_detail_frames:
        logger.warning("Hiçbir şehir için veri bulunamadı.")
        return

    # ── Save detailed CSV ──────────────────────────────────────────────────────
    detail_df = pd.concat(all_detail_frames, ignore_index=True)
    detail_file = OUTPUT_DIR / f"sahibinden_inflation_{today_str}.csv"
    detail_df.to_csv(detail_file, index=False, encoding="utf-8-sig")
    logger.info(f"Detay dosyası kaydedildi: {detail_file} ({len(detail_df)} satır)")

    # ── Save / update summary CSV ─────────────────────────────────────────────
    summary_file = OUTPUT_DIR / "sahibinden_inflation_summary.csv"
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
    parser = argparse.ArgumentParser(description="Sahibinden rental inflation calculator")
    parser.add_argument("--date",    help="Hedef tarih (YYYY-MM-DD)", default=None)
    parser.add_argument("--compare", help="Karşılaştırma tarihi (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    calculate_inflation(args.date, args.compare)