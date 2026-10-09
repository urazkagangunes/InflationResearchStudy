from pathlib import Path
import csv
import datetime
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
            timeout=30  # 30-second timeout — avoid infinite hang
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
            total_data.append([f"{brand} {name}".strip(), price])
            new_items += 1

        print(f"[Beymen] Page {page}: {new_items} new products")

        if new_items == 0:
            break

        page += 1

    except requests.exceptions.Timeout:
        print(f"[Beymen] Timeout on page {page}, exiting loop")
        break
    except requests.exceptions.RequestException as e:
        print(f"[Beymen] Request failed: {e}")
        break
    except ValueError as e:
        print(f"[Beymen] JSON parsing error: {e}")
        break

# --- Output directory setup ---
_THIS_DIR = Path(__file__).resolve()
_PROJECT_ROOT = next((p for p in _THIS_DIR.parents if (p / ".git").exists()), _THIS_DIR.parents[4])
out_dir = os.path.join(_PROJECT_ROOT, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "BeymenBeauty")
os.makedirs(out_dir, exist_ok=True)

_today_str = datetime.date.today().strftime("%Y-%m-%d")
csv_name = os.path.join(out_dir, f"beymen_beauty_{_today_str}.csv")
file_exists = os.path.exists(csv_name)

with open(csv_name, mode="a", newline="", encoding="utf-8-sig") as file:
    writer = csv.writer(file)
    if not file_exists:
        writer.writerow(["product_name", "price"])
    writer.writerows(total_data)

print(f"[Beymen] Saved {len(total_data)} products → {csv_name}")
