import requests
import pandas as pd
import time
import os
import sys
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
# Madame Coco, Akinon platformu üzerinde çalışan bir SPA'dır. Ürünler HTML'e
# render edilmez; sayfa açıldıktan sonra JSON API'den yüklenir. Akinon'un
# resmi belgelerine göre herhangi bir kategori URL'sinin sonuna ?format=json
# eklendiğinde tüm sayfa verisi JSON olarak döner.
#   Kaynak: https://docs.akinon.com/products/commerce
BASE_URL = "https://www.madamecoco.com"

# Atanan görev: "Home, Home Decoration, Living veya benzeri kategoriler".
# Yeni kategori eklemek için aşağıya satır eklemek yeterli.
CATEGORIES: list[dict] = [
    {"slug": "ev-yasam",     "label": "Ev & Yaşam"},
    {"slug": "dekorasyon",   "label": "Dekorasyon"},
    {"slug": "sofra",        "label": "Sofra"},
    {"slug": "mutfak",       "label": "Mutfak"},
    {"slug": "banyo",        "label": "Banyo"},
    {"slug": "yatak-odasi",  "label": "Yatak Odası"},
    {"slug": "hali-kilim",   "label": "Halı & Kilim"},
    {"slug": "kozmetik",     "label": "Kozmetik"},
    # yeni-urunler lists the whole catalogue, including products that are not
    # assigned to any menu category. It runs last so the global pk dedup keeps
    # the real category label and only unassigned products end up as "Diğer".
    {"slug": "yeni-urunler", "label": "Diğer"},
]

MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
RETRY_COUNT = 5
RETRY_DELAY = 2  # saniye
PAGE_DELAY = 0.2  # batch'ler arası küçük gecikme
MAX_PAGES_HARD_CAP = 500  # güvenlik: hiçbir kategori bunu aşmamalı
MIN_COVERAGE = 0.98

# A page that still fails after all retries means the day's file would be
# incomplete (2026-05-19 was saved with two categories missing), so the run
# aborts instead of writing a partial CSV.
failed_pages: list = []

# İlk sayfanın ham JSON'ını diske dökmek için (debug). Şablon değişirse
# bakmak için faydalı; True yaparsanız Datas/HomeGoods/MadameCoco/_debug/
# altında JSON dosyası olarak kaydedilir.
DUMP_FIRST_RESPONSE = False

# Klasör yolu (Pazarium scraper'ı ile aynı mantık)
current_script_path = os.path.abspath(__file__)
base_project_dir = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(current_script_path)
        )
    )
)
data_dir = os.path.join(base_project_dir, "Datas", "HomeGoods", "MadameCoco")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(
    data_dir, f"madamecoco_{datetime.now().strftime('%Y-%m-%d')}.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
    "X-Requested-With": "XMLHttpRequest",
}

session = requests.Session()
session.headers.update(HEADERS)


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def to_float(val) -> float | None:
    """Akinon bazen fiyatı string ('1234.56'), bazen sayı olarak döner.
    Hatasız float'a çevir."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fetch_json(category_slug: str, page_num: int) -> dict | None:
    """Belirli kategori + sayfanın JSON'ını döner. Retry yapar."""
    url = f"{BASE_URL}/{category_slug}/?format=json&page={page_num}"
    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except json.JSONDecodeError as e:
            # Beklenmedik HTML döndü - büyük ihtimalle Cloudflare/CDN bloğu
            last_err = f"JSON decode hatası: {e}"
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * 2 ** (attempt - 1))
        except Exception as e:
            last_err = e
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * 2 ** (attempt - 1))
    print(f"   [ERROR] {category_slug} sayfa {page_num} alınamadı "
          f"({RETRY_COUNT} deneme): {last_err}")
    failed_pages.append((category_slug, page_num))
    return None


def find_product_list(data: dict) -> list:
    """JSON içinden ürün listesini bul. Akinon şablonu zaman içinde
    değişebildiği için birden fazla anahtar adını dener."""
    if not isinstance(data, dict):
        return []
    for key in ("products", "product_list", "results", "items", "data"):
        val = data.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
        # bazen iç içe: {"data": {"products": [...]}}
        if isinstance(val, dict):
            for inner_key in ("products", "product_list", "results", "items"):
                inner = val.get(inner_key)
                if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                    return inner
    return []


def find_pagination_total_pages(data: dict) -> int | None:
    """Toplam sayfa sayısını JSON'dan bul (varsa)."""
    if not isinstance(data, dict):
        return None
    for key in ("pagination", "pagination_args", "page_info", "meta"):
        block = data.get(key)
        if isinstance(block, dict):
            for tp_key in ("total_pages", "totalPages", "page_count", "num_pages"):
                tp = block.get(tp_key)
                if isinstance(tp, int) and tp > 0:
                    return tp
            # total + page_size ile hesapla
            total = block.get("total") or block.get("total_records") or block.get("count")
            page_size = block.get("page_size") or block.get("limit") or block.get("per_page")
            if isinstance(total, int) and isinstance(page_size, int) and page_size > 0:
                return (total + page_size - 1) // page_size
    return None


def extract_product(item: dict, category_label: str) -> dict | None:
    """Tek bir ürün dict'inden istenen alanları çıkar."""
    # İsim
    name = (item.get("name") or item.get("title") or item.get("product_name") or "").strip()
    if not name:
        return None

    # Stok kontrolü: stokta yoksa atla
    in_stock = item.get("in_stock")
    if in_stock is None:
        in_stock = item.get("is_in_stock")
    if in_stock is False:
        return None

    # Gift cards are vouchers with a fixed face value, not goods.
    if (item.get("attributes") or {}).get("Gift_card"):
        return None

    # Liste fiyatı: retail_price ve price normalde aynı değeri taşır
    # (her ikisi de liste/orijinal fiyat). İndirim ayrı yerde tutulur.
    retail_raw = (
        item.get("retail_price")
        or item.get("retailPrice")
        or item.get("price")
    )
    price = to_float(retail_raw)
    if price is None:
        return None

    # Akinon keeps the pre-sale price in retail_price and the selling price in
    # price, so a markdown shows up only as price < retail_price.
    discounted_price: float | None = to_float(item.get("price"))

    # İndirimli fiyat: basket_offers[].listing_kwargs.discounted_total_price
    # quantity birim sayısıdır; birim fiyatı için bölünmesi gerek (genelde 1).
    # Birden çok offer varsa en düşük birim fiyatı tercih ederiz.
    # client_types boş olmayan offer'lar segment-spesifik olduğu için atlanır
    # (genel kullanıcının göreceği fiyatı yansıtmaz).
    basket_offers = item.get("basket_offers") or []
    if isinstance(basket_offers, list):
        for offer in basket_offers:
            if not isinstance(offer, dict):
                continue
            client_types = offer.get("client_types")
            if client_types:  # boş değilse segment-özel
                continue
            kw = offer.get("listing_kwargs") or {}
            if not isinstance(kw, dict):
                continue
            disc_total = to_float(kw.get("discounted_total_price"))
            qty_raw = kw.get("quantity") or 1
            try:
                qty = int(qty_raw)
            except (ValueError, TypeError):
                qty = 1
            if disc_total is None or qty <= 0:
                continue
            unit = round(disc_total / qty, 2)
            if discounted_price is None or unit < discounted_price:
                discounted_price = unit

    # İndirimli fiyat liste fiyatına eşit veya yüksekse indirim yok demektir
    if discounted_price is not None and discounted_price >= price:
        discounted_price = None

    # Dedup için kullanılacak benzersiz tanımlayıcı
    pk = item.get("pk") or item.get("id") or item.get("absolute_url")

    return {
        "name": name,
        "category": category_label,
        "price": price,
        "discounted_price": discounted_price,
        "_pk": pk,
    }


def parse_products(data: dict, category_label: str) -> list[dict]:
    items = find_product_list(data)
    out = []
    for item in items:
        rec = extract_product(item, category_label)
        if rec is not None:
            out.append(rec)
    return out


def diagnose_response(data, slug: str) -> None:
    """İlk sayfada ürün bulamazsak durumu anlamak için debug bilgisi yaz."""
    print(f"   [DEBUG] {slug} JSON yapısı incelemesi:")
    if not isinstance(data, dict):
        print(f"            Yanıt dict değil, tip: {type(data).__name__}")
        return
    print(f"            Üst seviye anahtarlar: {list(data.keys())[:20]}")
    # İlk seviyede bir liste var mı bak
    for k, v in data.items():
        if isinstance(v, list) and v:
            print(f"            '{k}' bir liste, {len(v)} eleman, "
                  f"ilk eleman tipi: {type(v[0]).__name__}")
            if isinstance(v[0], dict):
                print(f"            ilk elemanın anahtarları: "
                      f"{list(v[0].keys())[:25]}")
        elif isinstance(v, dict):
            print(f"            '{k}' bir dict, anahtarlar: "
                  f"{list(v.keys())[:15]}")


# -----------------------------------------------------------------------------
# SCRAPING
# -----------------------------------------------------------------------------
def scrape_category(category: dict) -> list[dict]:
    slug = category["slug"]
    label = category["label"]

    print(f"\n>> Kategori: {label}  ({BASE_URL}/{slug}/?format=json)")

    # --- Sayfa 1 ---
    data = fetch_json(slug, 1)
    if data is None:
        print(f"   [HATA] {slug} sayfa 1 alınamadı, kategori atlanıyor.")
        return []

    # Debug dump (isteğe bağlı)
    if DUMP_FIRST_RESPONSE:
        debug_dir = os.path.join(data_dir, "_debug")
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, f"{slug}_page1.json")
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   [DEBUG] İlk yanıt {debug_file} dosyasına yazıldı.")

    page1_products = parse_products(data, label)
    # Check the raw list: a first page of only out-of-stock items is not an
    # empty category.
    if not find_product_list(data):
        print(f"   [UYARI] Sayfa 1'de ürün bulunamadı.")
        diagnose_response(data, slug)
        return []

    total_pages = find_pagination_total_pages(data)
    if total_pages:
        print(f"   [sayfa   1] {len(page1_products)} ürün "
              f"(toplam {total_pages} sayfa)")
    else:
        print(f"   [sayfa   1] {len(page1_products)} ürün "
              f"(toplam sayfa belirsiz, boş sayfa görene kadar gidilecek)")

    all_products = list(page1_products)
    seen_pks: set = {p["_pk"] for p in all_products if p["_pk"] is not None}
    # The site counts out-of-stock items and gift cards too, which are not
    # kept, so coverage is measured on the raw listing.
    total_count = (data.get("pagination") or {}).get("total_count")
    listed = {item.get("pk") for item in find_product_list(data)}

    # --- Sayfa 2+ ---
    if total_pages and total_pages > MAX_PAGES_HARD_CAP:
        failed_pages.append((slug, f"{total_pages} > {MAX_PAGES_HARD_CAP}"))

    if total_pages and total_pages > 1:
        # Bilinen toplam: paralel batch çek
        remaining_pages = list(range(2, min(total_pages, MAX_PAGES_HARD_CAP) + 1))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_page = {
                executor.submit(fetch_json, slug, p): p for p in remaining_pages
            }
            for future in as_completed(future_to_page):
                p = future_to_page[future]
                page_data = future.result()
                if page_data is None:
                    continue
                listed |= {item.get("pk") for item in find_product_list(page_data)}
                new_products = parse_products(page_data, label)
                added = 0
                for prod in new_products:
                    pk = prod["_pk"]
                    if pk is not None and pk in seen_pks:
                        continue
                    if pk is not None:
                        seen_pks.add(pk)
                    all_products.append(prod)
                    added += 1
                print(f"   [sayfa {p:>3}] {len(new_products)} ürün, {added} yeni")
    else:
        # Bilinmeyen toplam: batch'lerle ilerle, boş gelene kadar
        page = 2
        found_end = False
        while not found_end and page <= MAX_PAGES_HARD_CAP:
            batch = list(range(page, min(page + MAX_WORKERS, MAX_PAGES_HARD_CAP + 1)))
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_page = {
                    executor.submit(fetch_json, slug, p): p for p in batch
                }
                results = {}
                for future in as_completed(future_to_page):
                    p = future_to_page[future]
                    results[p] = future.result()

            for p in batch:
                page_data = results.get(p)
                if page_data is None:
                    found_end = True
                    break
                listed |= {item.get("pk") for item in find_product_list(page_data)}
                new_products = parse_products(page_data, label)
                if not new_products:
                    found_end = True
                    print(f"   [sayfa {p:>3}] boş -> kategori sonu")
                    break
                added = 0
                for prod in new_products:
                    pk = prod["_pk"]
                    if pk is not None and pk in seen_pks:
                        continue
                    if pk is not None:
                        seen_pks.add(pk)
                    all_products.append(prod)
                    added += 1
                print(f"   [sayfa {p:>3}] {len(new_products)} ürün, {added} yeni")

            page += MAX_WORKERS
            time.sleep(PAGE_DELAY)

    print(f"   -> Toplam {len(all_products)} benzersiz ürün ({label}), "
          f"listede {len(listed)}/{total_count}")
    # The runner counts any CSV as success, so a partial catalogue must not
    # produce one.
    if total_count and len(listed) < MIN_COVERAGE * total_count:
        failed_pages.append((slug, f"{len(listed)}/{total_count} listed"))
    return all_products


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("=" * 70)
    print(f"Madame Coco Home Goods Scraper  |  {today_str}")
    print(f"Kategoriler: {[c['label'] for c in CATEGORIES]}")
    print(f"Çıktı: {OUTPUT_FILE}")
    print("=" * 70)

    all_products: list[dict] = []
    seen_pks_global: set = set()

    for category in CATEGORIES:
        cat_products = scrape_category(category)
        for p in cat_products:
            pk = p["_pk"]
            if pk is not None and pk in seen_pks_global:
                continue  # aynı ürün başka kategoride zaten var
            if pk is not None:
                seen_pks_global.add(pk)
            all_products.append(p)

    if failed_pages:
        print(f"\n[FATAL] Alınamayan sayfalar: {failed_pages}; eksik CSV yazılmadı.")
        sys.exit(1)

    if not all_products:
        print("\n[FATAL] Hiç ürün çıkarılamadı.")
        return

    df = pd.DataFrame(all_products)
    df = df[["name", "category", "price", "discounted_price"]]
    df = df.sort_values(["category", "name"]).reset_index(drop=True)

    # price is the list price; the customer pays the discounted one when there is one.
    out = pd.DataFrame({
        "product_name": df["name"],
        "price": df["discounted_price"].fillna(df["price"]),
    })
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"TAMAMLANDI")
    print(f"   Toplam ürün: {len(df)}")
    for cat, count in df["category"].value_counts().items():
        n_disc = int(df[(df["category"] == cat) &
                        df["discounted_price"].notna()].shape[0])
        print(f"   - {cat}: {count} ürün ({n_disc} indirimli)")
    print(f"   Çıktı: {OUTPUT_FILE}")
    print(f"   Süre: {elapsed:.1f} sn")
    print("=" * 70)


if __name__ == "__main__":
    main()