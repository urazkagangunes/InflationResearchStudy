import re
from pathlib import Path

# 1. XML DOSYASINI OKUMA
# __file__ ile kodun çalıştığı klasörü bulup, içindeki XML dosyasını hedefliyoruz
mevcut_klasor = Path(__file__).parent
xml_dosya_yolu = mevcut_klasor / "vakko_categories.xml"

print(f"XML dosyası okunuyor: {xml_dosya_yolu.name}...")

try:
    with open(xml_dosya_yolu, "r", encoding="utf-8") as dosya:
        xml_metni = dosya.read()
except FileNotFoundError:
    print("HATA: vakko_categories.xml dosyası bulunamadı! Lütfen kodla aynı klasörde olduğundan emin ol.")
    exit()

# 2. KATEGORİLERİ AYIKLAMA (REGEX SİHRİ)
kategoriler = {
    "Kadin": [],
    "Erkek": [],
    "Shoes_Bags": [],
    "Diger": []
}

# <loc> etiketleri arasındaki URL'leri bul
linkler = re.findall(r'<loc>(.*?)</loc>', xml_metni)

for link in linkler:
    link = link.strip()

    # -c- sonrasındaki ID'yi yakala
    match = re.search(r'-c-([a-zA-Z0-9_-]+)/?$', link)

    if match:
        kat_id = match.group(1)

        # Süzgeç: Outlet'leri şimdilik hariç tutarak Ana Kategorilere dağıt
        if "/kadin" in link and "/outlet" not in link:
            if kat_id not in kategoriler["Kadin"]:
                kategoriler["Kadin"].append(kat_id)

        elif "/erkek" in link and "/outlet" not in link:
            if kat_id not in kategoriler["Erkek"]:
                kategoriler["Erkek"].append(kat_id)

        elif ("/ayakkabi-canta" in link or "/shoes-bags" in link) and "/outlet" not in link:
            if kat_id not in kategoriler["Shoes_Bags"]:
                kategoriler["Shoes_Bags"].append(kat_id)
        else:
            kategoriler["Diger"].append(f"{kat_id} ({link})")

# 3. SONUÇLARI PİLOT ÇIKTI OLARAK VER
print("\n--- KADIN KATEGORİ ID'LERİ ---")
print('"' + '", "'.join(kategoriler['Kadin']) + '"\n')

print("--- ERKEK KATEGORİ ID'LERİ ---")
print('"' + '", "'.join(kategoriler['Erkek']) + '"\n')

print("--- AYAKKABI & ÇANTA KATEGORİ ID'LERİ ---")
print('"' + '", "'.join(kategoriler['Shoes_Bags']) + '"\n')

print(
    f"Toplam {len(kategoriler['Kadin']) + len(kategoriler['Erkek']) + len(kategoriler['Shoes_Bags'])} adet temiz ID bulundu!")