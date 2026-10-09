"""
vakko_inflation.py — Vakko Enflasyon Hesaplayıcı
"""

import logging
import os
from datetime import datetime, timedelta
import pandas as pd

# Dosya ismini vakko_tuik_config olarak güncelledik
from vakko_tuik_config import vakko_category_to_tuik, normalised_weights

# ── RELATIVE PATH SETUP ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Target: inflationstudymirror root (Up 3 levels from Codes/ClothingStores/Vakko)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "Datas", "ClothingStores", "Vakko")
INFLATION_OUT_DIR = os.path.join(PROJECT_ROOT, "Inflations", "Datas", "ClothingStores", "Vakko")

# Ensure output directory exists
os.makedirs(INFLATION_OUT_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

def _load_csv(date_str):
    """Vakko CSV'sini yükler ve fiyatları float formatına temizler."""
    fpath = os.path.join(DATA_DIR, f"vakko_{date_str}.csv")
    if not os.path.exists(fpath):
        logger.info(f"Dosya bulunamadı, bu tarih atlanıyor: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath)

        if 'product-price' in df.columns:
            # Fiyat temizleme: ₺ ve binlik noktalarını kaldır, kuruş virgülünü noktaya çevir
            cleaned_price = (
                df['product-price']
                .astype(str)
                .str.replace('₺', '', regex=False)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
            )
            df['Fiyat'] = pd.to_numeric(cleaned_price, errors='coerce')
        return df
    except Exception as e:
        logger.error(f"Dosya okunurken hata oluştu {fpath}: {e}")
        return None

def _compute_metrics(df_current, df_past):
    df_current = df_current.copy()

    # Kategori tespitini ürün adından yap (product-name sütunu kullanılıyor)
    df_current['tuik_category'] = df_current['product-name'].apply(vakko_category_to_tuik)

    past_subset = df_past[['Stok Kodu', 'Fiyat']].rename(columns={'Fiyat': 'past_price'})
    merged = df_current.merge(past_subset, on='Stok Kodu', how='left')

    # 1) Ürün bazlı temel enflasyon
    merged['basic_inflation'] = ((merged['Fiyat'] - merged['past_price']) / merged['past_price']) * 100

    # Sonsuz değerleri temizle (Sıfıra bölünme vs. durumları için)
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2) Ortalama Enflasyon
    avg_inflation = merged['basic_inflation'].mean()

    # 3) TUIK Ağırlıklı Enflasyon
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c]))

    return merged, avg_inflation, tuik_weighted

def calculate_inflation(target_date=None, compare_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()

    today_str = base_date.strftime("%Y-%m-%d")
    df_today = _load_csv(today_str)

    if df_today is None:
        print(f"HATA: {today_str} tarihli güncel veri bulunamadı! İşlem iptal edildi.")
        return

    # Hesaplanacak aralıkları belirle (Karşılaştırma tarihi varsa sadece onu, yoksa standart aralıkları kullan)
    if compare_date:
        intervals = {f"custom": compare_date}
    else:
        intervals = {"1d": 1, "7d": 7, "15d": 15, "30d": 30}

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = detail_base['product-name'].apply(vakko_category_to_tuik)

    for label, val in intervals.items():
        if isinstance(val, int):
            past_str = (base_date - timedelta(days=val)).strftime("%Y-%m-%d")
        else:
            past_str = val

        df_past = _load_csv(past_str)

        if df_past is None:
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['Stok Kodu', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='Stok Kodu', how='left'
        )
        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # Detaylı veriyi kaydet (vakko_inflation_YYYY-MM-DD.csv)
    detail_file = os.path.join(INFLATION_OUT_DIR, f"vakko_inflation_{today_str}.csv")
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Detaylı enflasyon verisi kaydedildi: {detail_file}")

    # Özet tabloyu güncelle veya oluştur (inflation_summary.csv)
    summary_file = os.path.join(INFLATION_OUT_DIR, "inflation_summary.csv")
    df_summary = pd.DataFrame([summary_row])

    try:
        if os.path.exists(summary_file):
            df_existing = pd.read_csv(summary_file)
            # Aynı tarihe ait eski bir kayıt varsa ez (tekrar çalıştırılma durumuna karşı)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
        logger.info(f"Özet enflasyon verisi güncellendi: {summary_file}")
    except Exception as e:
        logger.error(f"Özet dosyası yazılırken hata oluştu: {e}")

    print(f"İşlem başarıyla tamamlandı. Sonuçları '{INFLATION_OUT_DIR}' klasöründen inceleyebilirsin.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vakko enflasyon hesaplayıcı")
    parser.add_argument("--date", help="Hedef (güncel) tarih YYYY-MM-DD formatında", default=None)
    parser.add_argument("--compare", help="Karşılaştırılacak (geçmiş) tarih YYYY-MM-DD formatında", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)