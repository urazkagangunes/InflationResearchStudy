import datetime
import os
from pathlib import Path
import pandas as pd
import requests
from bs4 import BeautifulSoup

print("🚀 Ortopedi İstanbul Canlı Scraper Başlatılıyor...\n")

# ==========================================
# 1. AŞAMA: CANLI SİTEDEN VERİ ÇEKME
# ==========================================
url = "https://www.ortopediistanbul.com.tr/ortopedi-ameliyat-fiyat-listesi"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "tr,tr-TR;q=0.9,en-US;q=0.8,en;q=0.7"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 200:
        html_metni = response.content
        print("✅ Canlı siteye başarıyla bağlanıldı. Veriler işleniyor...")
    else:
        print(f"❌ HATA: Canlı siteye ulaşılamadı. Durum Kodu: {response.status_code}")
        exit()
except Exception as e:
    print(f"❌ Bağlantı hatası oluştu: {e}")
    exit()

# ==========================================
# 2. AŞAMA: REHBER HTML YAPISINA GÖRE PARS ETME
# ==========================================
soup = BeautifulSoup(html_metni, "html.parser")
tablo = soup.find("table", class_="table")

tum_hizmetler = []

if tablo:
    satirlar = tablo.find_all("tr")

    for satir in satirlar:
        hucreler = satir.find_all(["td", "th"])

        # En az 3 sütun (Hizmet Adı, SGK'lı, SGK'sız) araması
        if len(hucreler) < 3:
            continue

        hizmet_adi = hucreler[0].get_text(strip=True)
        sgk_li_fiyat = hucreler[1].get_text(strip=True)
        sgk_siz_fiyat = hucreler[2].get_text(strip=True)

        # Kaynak koddaki kategori başlıklarını ve tablo başlığını süzme
        if (not hizmet_adi or
                hizmet_adi.endswith(":") or
                "Fiyatları" in hizmet_adi or
                "Hastalarda" in sgk_li_fiyat):
            continue

        # Görünmez karakter temizliği (Source koddaki \xa0 ve zero-width temizliği için)
        sgk_li_fiyat = sgk_li_fiyat.replace("\xa0", "").replace("‌", "").strip()
        sgk_siz_fiyat = sgk_siz_fiyat.replace("\xa0", "").replace("‌", "").strip()

        # Sütun formatına uygun hale getirme (product-name, product-price)
        if sgk_li_fiyat and "karşılanmıyor" not in sgk_li_fiyat:
            tum_hizmetler.append({
                "product-name": f"{hizmet_adi} (SGK'lı)",
                "product-price": sgk_li_fiyat
            })

        if sgk_siz_fiyat:
            tum_hizmetler.append({
                "product-name": f"{hizmet_adi} (SGK'sız)",
                "product-price": sgk_siz_fiyat
            })
else:
    print("❌ HATA: Canlı sayfada beklenen fiyat tablosu bulunamadı!")
    exit()

# ==========================================
# 3. AŞAMA: VAKKO'DAN KOPYALANAN YOL AYARLARI VE KAYIT
# ==========================================
mevcut_dosya = Path(__file__).resolve()
proje_koku = mevcut_dosya.parents[3]  # Klasör hiyerarşine göre [3] değerini koruduk

# Senden istenen hedef klasör yapısı
hedef_klasor = proje_koku / "Datas" / "Health" / "Diagnostic&Surgical Services"
hedef_klasor.mkdir(parents=True, exist_ok=True)

bugunun_tarihi = datetime.datetime.now().strftime("%Y-%m-%d")
tam_dosya_yolu = hedef_klasor / f"ortopedi_istanbul_{bugunun_tarihi}.csv"

df = pd.DataFrame(tum_hizmetler)

if not df.empty:
    # Sadece istenen iki sütun
    sutun_sirasi = ["product-name", "product-price"]
    df = df[sutun_sirasi]

    # Mükerrer kayıt temizliği
    df.drop_duplicates(subset=['product-name'], inplace=True)

    # Standart virgül ayracıyla kayıt
    df.to_csv(tam_dosya_yolu, index=False, sep=',', encoding="utf-8-sig")
    print(f"\n🧹 Temizlik sonrası toplam benzersiz veri sayısı: {len(df)}")
    print(f"📁 Dosya başarıyla kaydedildi:\n--> {tam_dosya_yolu}")
else:
    print("⚠️ Sayfadan geçerli bir fiyat verisi ayıklanamadı.")