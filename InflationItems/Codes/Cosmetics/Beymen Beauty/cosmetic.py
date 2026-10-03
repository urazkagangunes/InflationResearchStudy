
import pandas as pd
import datetime
import csv
import os
import requests

month = datetime.date.today().month
day = datetime.date.today().day

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.beymen.com/tr"
}

total_data = []
seen_product_ids = set()
page = 1

while True:
    try:
        response = requests.get(
            f"https://www.beymen.com/tr/Product/GetFilteredProductList_V2"
            f"?currentFacets=marka_3,cinsiyet_6,alt-kategori_564,urun-cesidi_4,renk_23,surdurulebilir-urunler_81,koleksiyon-adi_72,fiyat_26,urun-ailesi_67"
            f"&urunSayisi=48&categoryId=30894&includeFacets=&includeDocuments=true"
            f"&currentScrollCount=1&siralama=akillisiralama&sayfa={page}",
            headers=headers,
            timeout=30  # 30 saniye timeout — sonsuz bekleme yok
        )
        response.raise_for_status()
        data = response.json()

        products = data.get("Data", {}).get("ProductListingItemList", [])
        if not products:
            break

        new_items = 0
        for item in products:
            pid = item.get("ProductId")
            if pid in seen_product_ids:
                continue
            seen_product_ids.add(pid)

            brand = item.get("BrandName", "")
            name = item.get("DisplayName", "")
            price = item.get("ActualPrice", "")
            total_data.append([f"{brand} {name}", price])
            new_items += 1

        print(f"[Beymen] Sayfa {page}: {new_items} yeni ürün")

        if new_items == 0:
            break

        page += 1

    except requests.exceptions.Timeout:
        print(f"[Beymen] Timeout — sayfa {page}, çıkılıyor")
        break
    except requests.exceptions.RequestException as e:
        print(f"[Beymen] Request failed: {e}")
        break
    except ValueError as e:
        print(f"[Beymen] JSON error: {e}")
        break

# --- Çıktı dizini (Linux/Mac/Windows uyumlu) ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "..", ".."))
out_dir = os.path.join(_PROJECT_ROOT, "InflationItems", "Datas", "Cosmetics", "BeymenBeauty")
os.makedirs(out_dir, exist_ok=True)

csv_name = os.path.join(out_dir, f"beymen_{month}-{day}.csv")
with open(csv_name, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(total_data)

print(f"[Beymen] Kaydedildi: {len(total_data)} ürün → {csv_name}")
