def get_tuik_class(cat_name):
    cat = str(cat_name).lower()

    # --- GRUP 07: ULAŞTIRMA (Oto Bakım ve Aksesuar) ---
    oto_keywords = [
        'autokit', 'lastik bakım', 'antifriz', 'cam suyu', 'kriko',
        'oto', 'jant', 'akü', 'fren balata', 'gres yağı', 'kar zinciri'
    ]
    if any(k in cat for k in oto_keywords):
        return "07"

    # --- GRUP 09: EĞLENCE VE KÜLTÜR (Bitki, Evcil Hayvan, Kamp) ---
    hobby_keywords = [
        'yapay ağaç', 'yapay çiçek', 'peyzaj', 'tasma', 'köpek', 'evcil',
        'kamp', 'spor', 'vazo', 'tablo', 'saatler', 'oyuncak'
    ]
    if any(k in cat for k in hobby_keywords):
        return "09"

    # --- GRUP 05: EV BAKIM VE HIRDAVAT (Geri kalan her şey) ---
    # Vidalar, borular, mobilya, aydınlatma, el aletleri vb.
    return "05"

import pandas as pd
import json

# JSON'u yükle
with open('kategori_haritasi.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

df = pd.DataFrame(list(data.items()), columns=['url', 'category'])

# TÜİK sınıflarını ata
df['tuik_code'] = df['category'].apply(get_tuik_class)

# Sonuçları printle
print("--- TÜİK GRUP DAĞILIMI ---")
print(df['tuik_code'].value_counts())

# Hangi grupta hangi kategoriler var örnek gör
print("\n--- 07 (ULAŞTIRMA) GRUBUNA GİREN BAZI KATEGORİLER ---")
print(df[df['tuik_code'] == "07"]['category'].unique()[:10])