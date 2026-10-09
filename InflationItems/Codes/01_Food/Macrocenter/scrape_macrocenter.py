import requests
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
BASE_URL = "https://www.macrocenter.com.tr/rest/products/search"
PAGE_SIZE = 100
MAX_WORKERS = 5

# 1. Mevcut dosyanın (scrape_macrocenter.py) konumunu al
current_script_path = os.path.abspath(__file__)

# 2. 'Codes/Markets/Macrocenter' klasöründen 3 seviye yukarı çıkarak ana proje klasörüne ulaş
# PythonProject/Codes/Markets/Macrocenter -> PythonProject
base_project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))

# 3. Yolları bu ana dizine göre birleştir
data_dir = os.path.join(base_project_dir, "Datas", "Markets", "Macrocenter")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(data_dir, f"macrocenter_prices_{time.strftime('%Y-%m-%d')}.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.macrocenter.com.tr/",
}

# ─────────────────────────────────────────
# KATEGORİ ID → ANA KATEGORİ ADI EŞLEMESİ
# ─────────────────────────────────────────
CATEGORIES = {
    # category_id : "Ana Kategori Adı"
    30000000071332 : "Meyve & Sebze",
    30000000071351 : "Süt Ürünleri & Kahvaltılık",
    30000000070965 : "Et & Tavuk & Balık",
    30000000071031 : "Temel Gıda",
    30000000070760 : "Atıştırmalık",
    30000000071352 : "Dondurma",
    30000000070802 : "İçecek",
    30000000071422 : "Unlu Mamul & Tatlı",
    30000000071209 : "Homemade by Macrocenter",
    30000000071219 : "Temizlik",
    30000000071625 : "Kozmetik",
    30000000071280 : "Bebek Ürünleri",
    30000000071467 : "Ev & Yaşam & Evcil Hayvan",
    30000000071325 : "Çiçek & Bahçe",
    30000000070871 : "Elektronik",
}


def fetch_page(category_id, page):
    """Tek bir sayfa çeker."""
    params = {
        "category-id": category_id,
        "page-size": PAGE_SIZE,
        "page": page,
    }
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        print(f"  ! Sayfa hatası (kategori={category_id}, sayfa={page}): {e}")
        return {}


def parse_product(item, category_name):
    """Ham JSON'dan temiz ürün dict'i üretir."""
    shown_price = item.get("shownPrice", 0)
    regular_price = item.get("regularPrice", 0)
    return {
        "Category": category_name,           # Ana kategori adı
        "Subcategory": item.get("category", {}).get("name", ""),  # Alt kategori ayrı sütunda
        "Name": item.get("name", ""),
        "Brand": item.get("brand", {}).get("name", ""),
        "SKU": item.get("sku", ""),
        "Price": round(shown_price / 100, 2),
        "RegularPrice": round(regular_price / 100, 2),
        "DiscountRate": item.get("discountRate", 0),
        "UnitPrice": item.get("unitPrice", ""),
        "Status": item.get("status", ""),
        "Date": time.strftime("%Y-%m-%d"),
    }


def scrape_category(args):
    """Bir kategorinin tüm sayfalarını çeker."""
    category_id, category_name = args
    print(f"  -> Basladi: {category_name} (ID: {category_id})")

    first_page = fetch_page(category_id, 0)
    if not first_page:
        return []

    page_count = first_page.get("pageCount", 1)
    items = first_page.get("storeProductInfos", [])
    products = [parse_product(item, category_name) for item in items]

    for page in range(1, page_count):
        page_data = fetch_page(category_id, page)
        page_items = page_data.get("storeProductInfos", [])
        products.extend([parse_product(item, category_name) for item in page_items])
        time.sleep(0.1)

    print(f"  OK {category_name}: {len(products)} urun ({page_count} sayfa)")
    return products


def main():
    if not CATEGORIES:
        print("HATA: CATEGORIES dict bos. ID ve isimleri doldur.")
        return

    print(f"Toplam {len(CATEGORIES)} kategori taranacak ({MAX_WORKERS} paralel).")

    all_products = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(scrape_category, (cid, name)): name
            for cid, name in CATEGORIES.items()
        }
        for future in as_completed(futures):
            try:
                all_products.extend(future.result())
            except Exception as e:
                print(f"  ! Worker hatasi: {e}")

    if all_products:
        df = pd.DataFrame(all_products)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\nTamamlandi! {len(all_products)} urun -> {OUTPUT_FILE}")
    else:
        print("Hic urun bulunamadi.")

if __name__ == "__main__":
    main()