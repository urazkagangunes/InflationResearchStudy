import os

import requests
import re
import time
import random
import datetime
import pandas as pd
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

print("🚀 Vakko Master Scraper Başlatılıyor...\n")

# ==========================================
# 1. AŞAMA: XML'DEN KATEGORİLERİ ÇEKME
# ==========================================
mevcut_klasor = Path(__file__).parent
xml_dosya_yolu = mevcut_klasor / "vakko_categories.xml"

try:
    with open(xml_dosya_yolu, "r", encoding="utf-8") as dosya:
        xml_metni = dosya.read()
except FileNotFoundError:
    print("❌ HATA: vakko_categories.xml dosyası bulunamadı!")
    exit()

kategoriler = {"Kadin": [], "Erkek": [], "Shoes_Bags": []}
linkler = re.findall(r'<loc>(.*?)</loc>', xml_metni)

for link in linkler:
    link = link.strip()
    match = re.search(r'-c-([a-zA-Z0-9_-]+)/?$', link)
    if match:
        kat_id = match.group(1)
        if "/kadin" in link and "/outlet" not in link and kat_id not in kategoriler["Kadin"]:
            kategoriler["Kadin"].append(kat_id)
        elif "/erkek" in link and "/outlet" not in link and kat_id not in kategoriler["Erkek"]:
            kategoriler["Erkek"].append(kat_id)
        elif ("/ayakkabi-canta" in link or "/shoes-bags" in link) and "/outlet" not in link and kat_id not in \
                kategoriler["Shoes_Bags"]:
            kategoriler["Shoes_Bags"].append(kat_id)

toplam_kategori = sum(len(ids) for ids in kategoriler.values())
print(f"✅ XML Okundu! Toplam {toplam_kategori} kategori taramaya alınıyor...\n")

# ==========================================
# 2. AŞAMA: API'DEN ÜRÜNLERİ ÇEKME
# ==========================================
session = requests.Session()
url = "https://api.vakko.com/occ/v2/vsite/products/search"

gizli_cookie = os.getenv("VAKKO_COOKIE")
gizli_user_agent = os.getenv("VAKKO_USER_AGENT")

headers = {
    "User-Agent": gizli_user_agent,
    "Accept": "application/json, text/plain, */*",
    "Platform": "WEB",
    "Origin": "https://www.vakko.com",
    "Referer": "https://www.vakko.com/",
    "Cookie": gizli_cookie
}
session.headers.update(headers)

tum_urunler_temiz = []
islenen_kategori = 0

for ana_kategori, id_list in kategoriler.items():
    for kat_id in id_list:
        islenen_kategori += 1
        mevcut_sayfa = 0
        toplam_sayfa = 1

        print(f"[{islenen_kategori}/{toplam_kategori}] Taraniyor -> {ana_kategori} | ID: {kat_id}")

        while mevcut_sayfa < toplam_sayfa:
            params = {
                "fields": "FULL,facets,breadcrumbs,pagination(DEFAULT),sorts(DEFAULT)",
                "query": f":relevance:allCategories:{kat_id}",
                "pageSize": "48",
                "lang": "tr",
                "curr": "TRY",
                "currentPage": str(mevcut_sayfa)
            }

            try:
                response = session.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    toplam_sayfa = data.get('pagination', {}).get('totalPages', 1)
                    urunler = data.get('products', [])

                    for urun in urunler:
                        fiyat_sozlugu = urun.get('price', {})
                        fiyat = fiyat_sozlugu.get('formattedValue', fiyat_sozlugu.get('value', 'Fiyat Yok'))

                        tum_urunler_temiz.append({
                            "Ana Kategori": ana_kategori,
                            "Kategori ID": kat_id,
                            "Stok Kodu": urun.get('code', 'Kod Yok'),
                            "Ürün Adı": urun.get('name', 'İsimsiz'),
                            "Fiyat": fiyat
                        })

                    mevcut_sayfa += 1

                    if mevcut_sayfa < toplam_sayfa:
                        time.sleep(random.uniform(3.2, 4.8))  # Banlanmamak için sayfa arası bekleme

                else:
                    print(f"   ⚠️ HATA! Durum Kodu: {response.status_code}. Bu kategori atlanıyor.")
                    break

            except Exception as e:
                print(f"   ❌ Bir sorun oluştu: {e}")
                break

        # Her kategoriden sonra insan taklidi için bekleme
        time.sleep(random.uniform(3.7, 5.5))

# ==========================================
# 3. AŞAMA: VERİYİ TEMİZLEME VE CSV'YE KAYDETME
# ==========================================
print(f"\n✅ Tarama Bitti! Ham ürün sayısı: {len(tum_urunler_temiz)}")

# Dinamik klasör yolu bulma (Senin istediğin Datas/ClothingStores/Vakko klasörüne)
mevcut_dosya = Path(__file__).resolve()
proje_koku = mevcut_dosya.parents[3]
hedef_klasor = proje_koku / "Datas" / "ClothingStores" / "Vakko"
hedef_klasor.mkdir(parents=True, exist_ok=True)

bugunun_tarihi = datetime.datetime.now().strftime("%Y-%m-%d")
tam_dosya_yolu = hedef_klasor / f"vakko_{bugunun_tarihi}.csv"

df = pd.DataFrame(tum_urunler_temiz)

# Çift verileri Stok Koduna göre sil (Böylece enflasyon analizin bozulmaz)
if not df.empty:
    df.drop_duplicates(subset=['Stok Kodu'], inplace=True)
    df.to_csv(tam_dosya_yolu, index=False, encoding="utf-8-sig")
    print(f"🧹 Temizlik sonrası benzersiz ürün sayısı: {len(df)}")
    print(f"📁 Dosya başarıyla kaydedildi:\n--> {tam_dosya_yolu}")
else:
    print("⚠️ Hiç ürün çekilemediği için CSV oluşturulmadı.")
