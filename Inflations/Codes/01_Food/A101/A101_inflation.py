"""
inflation.py — A101 Daily Inflation Calculator

Computes three inflation metrics for A101 products:
  1. Basic Inflation   – basket-level price index change (%)
  2. Average Inflation – arithmetic mean
  3. TUIK Weighted Avg – weighted average based on 2026 CPI weights
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent               # .../Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent            # .../InflationResearchStudy

sys.path.insert(0, str(_CODES_DIR))
try:
    from tuik_config import normalised_weights, TUIK_WEIGHTS
except ImportError:
    # Fallback if pathing is weird during direct execution
    sys.path.insert(0, str(_PROJECT_ROOT / "Inflations" / "Codes"))
    from tuik_config import normalised_weights, TUIK_WEIGHTS

logger = logging.getLogger(__name__)

# ── Directories ───────────────────────────────────────────────────────────────
DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "Markets" / "A101"
INFLATION_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Markets" / "A101"

def a101_category_to_tuik(ana_kategori):
    """Map A101 main category to TUIK main group code."""
    if not ana_kategori:
        return "01"
    
    cat = str(ana_kategori).lower()
    
    # Mapping logic based on A101 specific category names
    if any(x in cat for x in ["meyve", "sebze", "et", "tavuk", "süt", "sut", "kahvalt", "gıda", "gida", "atıştırma", "icecek", "içecek", "yemek", "meze", "dondurma", "fırın", "firin"]):
        return "01" # Gıda ve Alkolsüz İçecekler
    elif any(x in cat for x in ["temizlik", "kağıt", "kagit", "ev yaşam", "ev yasam"]):
        return "05" # Mobilya, Ev Aletleri ve Ev Bakım
    elif any(x in cat for x in ["kişisel", "kisisel", "bebek", "sağlık", "saglik"]):
        return "12" # Kişisel Bakım, Sosyal Koruma ve Çeşitli Mal ve Hizmetler
    elif "elektronik" in cat:
        return "08" # Bilgi ve İletişim
    elif "evcil" in cat:
        return "09" # Eğlence ve Kültür
    
    return "01" # Default to Food for unmatched retail items

def clean_price(price_str):
    """Convert Turkish currency string (e.g. '₺149,50') to float."""
    if pd.isna(price_str) or price_str == "":
        return None
    try:
        # Standardize: remove currency symbol, remove thousands separator, replace decimal comma
        s = str(price_str).replace("₺", "").replace(".", "").replace(",", ".").strip()
        # Filter to keep only digits and decimal point
        s = "".join(c for c in s if c.isdigit() or c == '.')
        return float(s)
    except Exception:
        return None

def _load_csv(date_str):
    """Load an A101 daily CSV by date string (YYYY-MM-DD), return DataFrame or None."""
    try:
        fpath = DATA_DIR / f"a101_kapida_{date_str}.csv"
        
        if not fpath.exists():
            logger.info(f"Data file not found: {fpath}")
            return None
            
        df = pd.read_csv(fpath)
        df['cleaned_price'] = df['fiyat'].apply(clean_price)
        return df
    except Exception as e:
        logger.error(f"Failed to load or parse data for {date_str}: {e}")
        return None

def _compute_metrics(df_current, df_past):
    """Compute the three inflation metrics between two DataFrames."""
    df_current = df_current.copy()
    df_current['tuik_category'] = df_current['ana_kategori'].apply(a101_category_to_tuik)

    # Use urun_id for matching across snapshots
    past_subset = df_past[['urun_id', 'cleaned_price']].rename(columns={'cleaned_price': 'past_price'})
    merged = df_current.merge(past_subset, on='urun_id', how='left')

    # 1) Basic inflation per product
    merged['basic_inflation'] = ((merged['cleaned_price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2) Average inflation – arithmetic mean
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Basic inflation at basket level
    valid = merged.dropna(subset=['cleaned_price', 'past_price'])
    sum_current = valid['cleaned_price'].sum()
    sum_past = valid['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK weighted average
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c]))

    return merged, basic_inflation_index, avg_inflation, tuik_weighted

def calculate_inflation(target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"No data for {today_str}.")
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {}
        for days in [1, 7, 15, 30]:
            past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals[f"{days}d"] = past_str

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = detail_base['ana_kategori'].apply(a101_category_to_tuik)

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)
        if df_past is None:
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)
        
        detail_base = detail_base.merge(
            merged[['urun_id', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='urun_id', how='left'
        )
        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # Save detailed
    detail_file = INFLATION_OUT_DIR / f"a101_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8-sig')
    logger.info(f"Saved detail: {detail_file}")

    # Update summary
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8-sig')
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8-sig')
        logger.info(f"Updated summary: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--compare", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
