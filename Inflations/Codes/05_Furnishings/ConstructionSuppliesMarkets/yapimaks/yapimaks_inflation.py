import argparse
import os
import pandas as pd
import json
import logging
from datetime import datetime, timedelta

# --- RELATIVE PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Target: inflationstudymirror root (Up 4 levels from Inflations/Codes/ConstructionMarkets/yapimaks)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "Datas", "yapimaks")
OUT_DIR = os.path.join(PROJECT_ROOT, "Inflations", "Datas", "ConstructionSuppliesMarkets", "Yapimaks")
JSON_PATH = os.path.join(PROJECT_ROOT, "Inflations", "Codes", "ConstructionMarkets", "yapimaks", "Category", "kategori_haritasi.json")

# Ensure output directory exists
os.makedirs(OUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# --- TÜİK MAPPING FONKSİYONU ---
def get_tuik_class(cat_name):
    cat = str(cat_name).lower()
    if any(k in cat for k in ['autokit', 'lastik bakım', 'antifriz', 'cam suyu', 'kriko', 'oto', 'jant', 'akü']):
        return "07"  # Ulaştırma
    if any(k in cat for k in ['yapay ağaç', 'yapay çiçek', 'peyzaj', 'tasma', 'köpek', 'evcil', 'kamp', 'spor']):
        return "09"  # Eğlence/Kültür
    return "05"  # Ev Bakım/Hırdavat (Default)


def load_data(date_str, category_map):
    fpath = os.path.join(DATA_DIR, f"{date_str}.csv")
    if not os.path.exists(fpath):
        return None

    df = pd.read_csv(fpath)

    # Handle both column name patterns safely
    price_col = 'product-price' if 'product-price' in df.columns else 'price'

    df['price'] = df[price_col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')

    df['category'] = df['url'].map(category_map).fillna("Bilinmeyen")
    df['tuik_code'] = df['category'].apply(get_tuik_class)

    return df[['product_id', 'price', 'category', 'tuik_code']]


def calculate_metrics(df_now, df_old, suffix):
    merged = df_now.merge(df_old[['product_id', 'price']], on='product_id', how='inner', suffixes=('', '_old'))

    # Ürün bazlı yüzde değişim
    merged[f'change_{suffix}'] = ((merged['price'] - merged['price_old']) / merged['price_old']) * 100

    # 1. Genel Mağaza Enflasyonu (Sepet)
    total_now = merged['price'].sum()
    total_old = merged['price_old'].sum()
    basket_inf = ((total_now - total_old) / total_old) * 100 if total_old > 0 else 0

    # 2. TÜİK Gruplarına Göre Enflasyon
    group_inf = merged.groupby('tuik_code').apply(
        lambda x: ((x['price'].sum() - x['price_old'].sum()) / x['price_old'].sum()) * 100 if x[
                                                                                                  'price_old'].sum() > 0 else 0
    ).to_dict()

    return merged, basket_inf, group_inf


def run_inflation_report(target_date_str):
    # 1. Kategori haritasını yükle
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        category_map = json.load(f)

    df_target = load_data(target_date_str, category_map)
    if df_target is None:
        logger.error(f"{target_date_str} verisi bulunamadı!")
        return

    base_date = datetime.strptime(target_date_str, "%Y-%m-%d")

    summary = {"date": target_date_str}
    detailed_df = df_target.copy()

    # 1, 7, 15, 30 günlük döngü
    for days in [1, 7, 15, 30]:
        old_date_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
        df_old = load_data(old_date_str, category_map)

        if df_old is not None:
            merged, basket, groups = calculate_metrics(df_target, df_old, f"{days}d")

            # Detaylı dosyaya ekle
            detailed_df = detailed_df.merge(merged[['product_id', f'change_{days}d']], on='product_id', how='left')

            # Özet dosyaya ekle
            summary[f'genel_{days}d'] = round(basket, 2)
            for code, val in groups.items():
                summary[f'grup_{code}_{days}d'] = round(val, 2)
        else:
            logger.info(f"{days} gün öncesine ait veri ({old_date_str}) yok, atlanıyor.")

    # Kayıt işlemleri
    detailed_output_file = os.path.join(OUT_DIR, f"yapimaks_detailed_inf_{target_date_str}.csv")
    detailed_df.to_csv(detailed_output_file, index=False, encoding='utf-8-sig')

    summary_file = os.path.join(OUT_DIR, "inflation_summary.csv")
    summary_df = pd.DataFrame([summary])
    if os.path.exists(summary_file):
        old_summary = pd.read_csv(summary_file)
        # Aynı tarihli kayıt varsa güncelle, yoksa ekle
        summary_df = pd.concat([old_summary[old_summary['date'] != target_date_str], summary_df], ignore_index=True)

    summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    logger.info(f"Raporlar tamamlandı! Klasör: {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="Çalıştırılacak tarih (Örn: 2026-03-24)")
    args = parser.parse_args()

    if args.date:
        run_inflation_report(args.date)
    else:
        run_inflation_report("2026-03-24")