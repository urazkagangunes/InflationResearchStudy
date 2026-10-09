
"""
A101.com.tr - Kapida Odeme API Scraper
Rio API ile dogrudan urun verisi ceker — tarayici gerekmez.

Kurulum:
    pip install requests beautifulsoup4 pandas

Kullanim:
    python a101_scraper.py
"""

import time
import datetime
import requests
import pandas as pd

# ─────────────────────────────────────────────────────────
BASE_URL   = "https://www.a101.com.tr"
RIO_BASE   = "https://rio.a101.com.tr/dbmk89vnr/CALL"
STORE_ID   = "VS032"          # Varsayilan magaza (Istanbul)
OUTPUT_CSV = f"a101_kapida_{datetime.date.today()}.csv"

# Scrape edilecek ana kategoriler — bos birakirsan HEPSINI ceker
# Ornek: ["C05", "C01"]  veya  []  (tum kategoriler)
ONLY_CATEGORY_IDS: list[str] = []   # bos = hepsi
# ─────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.a101.com.tr/",
    "Origin": "https://www.a101.com.tr",
}

session = requests.Session()
session.headers.update(HEADERS)


def rio_get(path: str, extra_params: str = "") -> dict:
    """
    Rio API'ye GET ister, JSON doner.
    extra_params: '&id=C05' gibi ek parametre string'i
    """
    base = "channel=SLOT&__culture=tr-TR&__platform=web&data=e30%3D&__isbase64=true"
    url = f"{RIO_BASE}/{path}?{base}{extra_params}"
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def get_main_categories() -> list[dict]:
    """Kök sayfadaki tüm ana kategorileri döndürür."""
    url = (
        f"https://rio.a101.com.tr/dbmk89vnr/CALL/Homepage/getHome/Homepage"
        f"?platform=WEB&storeId={STORE_ID}&type=SLOT"
        f"&__culture=tr-TR&__platform=web&data=e30%3D&__isbase64=true"
    )
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.json().get("categories", [])


def get_category_with_products(category_id: str) -> dict:
    """
    Bir ana/alt kategori için hem alt kategori listesini
    hem de ürünleri döndüren endpoint.
    Yanıt: { id, name, children: [ { id, name, products: [...] } ] }
    """
    return rio_get(
        f"Store/getProductsByCategory/{STORE_ID}",
        extra_params=f"&id={category_id}",
    )


def parse_product(raw: dict, ana_kategori: str, alt_kategori: str) -> dict | None:
    """
    Ham ürün dict'ini temizlenmiş satıra dönüştürür.
    API yapısı:
      raw.id               -> ürün ID
      raw.attributes.name  -> ürün adı
      raw.attributes.seoUrl-> ürün URL
      raw.attributes.brand -> marka
      raw.images[]         -> resimler (imageType=product olanı al)
      raw.price.normalStr  -> normal fiyat
      raw.price.discountedStr -> indirimli fiyat
      raw.stock            -> stok
    """
    attrs = raw.get("attributes", {})
    name  = attrs.get("name", "").strip()
    if not name:
        return None

    price_block    = raw.get("price", {})
    normal_str     = price_block.get("normalStr", "")
    discounted_str = price_block.get("discountedStr", "")
    is_discounted  = price_block.get("normal", 0) != price_block.get("discounted", 0)

    # Resim: imageType=product olanı tercih et
    image_url = ""
    for img in raw.get("images", []):
        if img.get("imageType") == "product":
            image_url = img.get("url", "")
            break
    if not image_url and raw.get("images"):
        image_url = raw["images"][0].get("url", "")

    seo_url    = attrs.get("seoUrl", "")
    if seo_url and not seo_url.startswith("http"):
        seo_url = f"{BASE_URL}{seo_url}"

    product_id = str(raw.get("id", ""))
    brand      = attrs.get("brand", "")
    stock      = raw.get("stock", 0)
    barcodes   = attrs.get("barcodes", [])
    barcode    = barcodes[0] if barcodes else ""

    return {
        "ana_kategori": ana_kategori,
        "alt_kategori": alt_kategori,
        "marka":        brand,
        "ad":           name,
        "fiyat":        discounted_str or normal_str,
        "normal_fiyat": normal_str,
        "indirimli":    "Evet" if is_discounted else "Hayir",
        "stok":         stock,
        "urun_id":      product_id,
        "barkod":       barcode,
        "resim_url":    image_url,
        "url":          seo_url,
    }


def scrape_main_category(cat: dict) -> list[dict]:
    """
    Ana kategori -> getProductsByCategory çağır.
    Dönen children (alt kategoriler) üzerinden ürünleri topla.
    """
    ana_id   = cat["id"]
    ana_name = cat["name"]
    print(f"\n[{ana_id}] {ana_name}")

    try:
        data = get_category_with_products(ana_id)
    except Exception as e:
        print(f"  ! Hata: {e}")
        return []

    children = data.get("children", [])
    all_products: list[dict] = []
    seen_ids: set = set()

    if not children:
        # Alt kategori yok, ürünler doğrudan üst seviyede
        products_raw = data.get("products", [])
        print(f"  (alt kategori yok) {len(products_raw)} urun")
        for raw in products_raw:
            pid = raw.get("id", raw.get("barcode", ""))
            if pid and pid in seen_ids:
                continue
            seen_ids.add(pid)
            parsed = parse_product(raw, ana_name, ana_name)
            if parsed:
                all_products.append(parsed)
    else:
        print(f"  {len(children)} alt kategori bulundu")
        for ch in children:
            alt_id   = ch["id"]
            alt_name = ch["name"]
            products_raw = ch.get("products", [])

            new_count = 0
            for raw in products_raw:
                pid = raw.get("id", raw.get("barcode", ""))
                if pid and pid in seen_ids:
                    continue
                seen_ids.add(pid)
                parsed = parse_product(raw, ana_name, alt_name)
                if parsed:
                    all_products.append(parsed)
                    new_count += 1

            print(f"    [{alt_id}] {alt_name}: {len(products_raw)} urun ({new_count} yeni)")
            time.sleep(0.3)

    print(f"  Toplam: {len(all_products)} urun")
    return all_products


def main():
    print("=" * 65)
    print("  A101 Kapida Scraper — Rio API Modu")
    print(f"  Magaza: {STORE_ID}")
    print("=" * 65)

    # 1) Ana kategorileri cek
    print("\n[1] Ana kategoriler aliniyor...")
    main_cats = get_main_categories()
    print(f"  Toplam {len(main_cats)} ana kategori")

    # Filtrele (bos = hepsi)
    if ONLY_CATEGORY_IDS:
        main_cats = [c for c in main_cats if c["id"] in ONLY_CATEGORY_IDS]
        print(f"  Filtre sonrasi: {len(main_cats)} kategori")

    # 2) Her ana kategoriyi tara
    print("\n[2] Urunler cekiliyor...")
    all_products: list[dict] = []

    for i, cat in enumerate(main_cats, 1):
        print(f"\n  [{i}/{len(main_cats)}]", end="")
        items = scrape_main_category(cat)
        all_products.extend(items)
        time.sleep(0.5)

    # 3) CSV
    print(f"\n{'=' * 65}")
    if not all_products:
        print("  Hic urun bulunamadi!")
        return

    df = pd.DataFrame(all_products)
    cols = ["ana_kategori", "alt_kategori", "marka", "ad", "fiyat", "normal_fiyat",
            "indirimli", "stok", "urun_id", "barkod", "resim_url", "url"]
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    df.drop_duplicates(subset=["urun_id"], inplace=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"  Tamamlandi!")
    print(f"  Toplam urun          : {len(df)}")
    print(f"  Ana kategori sayisi  : {df['ana_kategori'].nunique()}")
    print(f"  Alt kategori sayisi  : {df['alt_kategori'].nunique()}")
    print(f"  Dosya                : {OUTPUT_CSV}")
    print("=" * 65)


if __name__ == "__main__":
    main()
