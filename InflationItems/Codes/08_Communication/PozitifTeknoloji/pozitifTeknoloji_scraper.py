import requests
import pandas as pd
import time
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
# Pozitif Teknoloji (pt.com.tr), WooCommerce/WordPress üzerinde çalışır.
# Sayfalar server-side render edilir; HTML doğrudan parse edilebilir.
# Tüm site teknoloji ürünleri sattığı için kategori bazlı filtreye gerek yok.
BASE_URL = "https://www.pt.com.tr"

# Kategoriler "leaf" seviyesinde tutuldu - böylece her ürün anlamlı bir
# kategori etiketi alır (örn. "MacBook Air", "iPhone 17 Pro").
# Yeni kategori eklemek/çıkarmak için aşağıyı düzenleyin.
CATEGORIES: list[dict] = [
    # Mac
    {"slug": "macbook-neo",         "label": "MacBook Neo"},
    {"slug": "macbook-air",         "label": "MacBook Air"},
    {"slug": "macbook-pro",         "label": "MacBook Pro"},
    {"slug": "imac",                "label": "iMac"},
    {"slug": "mac-mini",            "label": "Mac mini"},
    {"slug": "mac-studio",          "label": "Mac Studio"},
    {"slug": "mac-ekranlar",        "label": "Mac Ekranlar"},
    {"slug": "mac-aksesuarlari",    "label": "Mac Aksesuarları"},

    # iPad
    {"slug": "ipad-9-nesil",        "label": "iPad (9. nesil)"},
    {"slug": "ipad-11-a16",         "label": "iPad 11 (A16)"},
    {"slug": "ipad-air-11-m4",      "label": "iPad Air 11 (M4)"},
    {"slug": "ipad-air-11-m3",      "label": "iPad Air 11 (M3)"},
    {"slug": "ipad-air-11-m2",      "label": "iPad Air 11 (M2)"},
    {"slug": "ipad-air-13-m4",      "label": "iPad Air 13 (M4)"},
    {"slug": "ipad-air-13-m3",      "label": "iPad Air 13 (M3)"},
    {"slug": "ipad-mini-a17-pro",   "label": "iPad Mini (A17 Pro)"},
    {"slug": "ipad-pro-11-m4",      "label": "iPad Pro 11 (M4)"},
    {"slug": "ipad-pro-11-m5",      "label": "iPad Pro 11 (M5)"},
    {"slug": "ipad-pro-13-m5",      "label": "iPad Pro 13 (M5)"},
    {"slug": "ipad-kalem",          "label": "iPad Kalem"},
    {"slug": "ipad-klavye",         "label": "iPad Klavye"},
    {"slug": "ipad-aksesuarlari",   "label": "iPad Aksesuarları"},

    # iPhone
    {"slug": "iphone-17e",          "label": "iPhone 17e"},
    {"slug": "iphone-air",          "label": "iPhone Air"},
    {"slug": "iphone-17",           "label": "iPhone 17"},
    {"slug": "iphone-17-pro",       "label": "iPhone 17 Pro"},
    {"slug": "iphone-17-pro-max",   "label": "iPhone 17 Pro Max"},
    {"slug": "iphone-16e",          "label": "iPhone 16e"},
    {"slug": "iphone-16",           "label": "iPhone 16"},
    {"slug": "iphone-16-plus",      "label": "iPhone 16 Plus"},
    {"slug": "iphone-15",           "label": "iPhone 15"},
    {"slug": "iphone-aksesuarlari", "label": "iPhone Aksesuarları"},

    # Apple Watch
    {"slug": "series-11",           "label": "Apple Watch Series 11"},
    {"slug": "se-3",                "label": "Apple Watch SE 3"},
    {"slug": "ultra-3",             "label": "Apple Watch Ultra 3"},

    # AirPods
    {"slug": "airpods-4",           "label": "AirPods 4"},
    {"slug": "airpods-pro",         "label": "AirPods Pro"},
    {"slug": "airpods-max",         "label": "AirPods Max"},

    # TV ve Ev
    {"slug": "apple-tv",            "label": "Apple TV"},
    {"slug": "homepod",             "label": "HomePod"},
    {"slug": "homepod-mini",        "label": "HomePod Mini"},

    # Aksesuarlar
    {"slug": "airtag-ve-aksesuarlari",       "label": "AirTag ve Aksesuarları"},
    {"slug": "depolama",                     "label": "Depolama"},
    {"slug": "monitor-ekranlar",             "label": "Monitör & Ekranlar"},
    {"slug": "mouse-ve-klavyeler",           "label": "Mouse ve Klavyeler"},
    {"slug": "guc-aksesuarlari",             "label": "Güç Aksesuarları"},
    {"slug": "kiliflar-ve-koruyucu-urunler", "label": "Kılıflar ve Koruyucu Ürünler"},
    {"slug": "cantalar",                     "label": "Çantalar"},
    {"slug": "kulakliklar-ve-hoparlorler",   "label": "Kulaklıklar ve Hoparlörler"},
    {"slug": "kalemler",                     "label": "Kalemler"},
    {"slug": "yazici-ve-projeksiyon",        "label": "Yazıcı ve Projeksiyon"},

    # Yazılım Lisans
    {"slug": "microsoft-lisans",    "label": "Microsoft Lisans"},

    # NOT: Outlet (refurbished/yenilenmiş) ve Fırsat kategorileri varsayılan
    # olarak dahil edilmedi. Outlet ürünleri ikinci el / yenilenmiş olduğu
    # için enflasyon analizini yanıltabilir. Eklemek istersen aşağıdaki
    # satırları yorumdan çıkar:
    # {"slug": "mac-outlet",      "label": "Mac Outlet"},
    # {"slug": "ipad-outlet",     "label": "iPad Outlet"},
    # {"slug": "iphone-outlet",   "label": "iPhone Outlet"},
    # {"slug": "watch-outlet",    "label": "Watch Outlet"},
    # {"slug": "aksesuar-outlet", "label": "Aksesuar Outlet"},
]

MAX_WORKERS = 5             # bir kategori içindeki paralel sayfa indirici
CATEGORY_WORKERS = 8        # eş zamanlı işlenecek kategori sayısı
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2  # saniye
PAGE_DELAY = 0.2
MAX_PAGES_PER_CATEGORY = 30  # güvenlik üst sınırı

# Stokta olmayan ürünleri atla (Tükendi badge'ı taşıyan kartlar)
SKIP_OUT_OF_STOCK = True

# Klasör yolu (önceki scraper'larla aynı mantık)
current_script_path = os.path.abspath(__file__)
base_project_dir = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(current_script_path)
        )
    )
)
data_dir = os.path.join(
    base_project_dir, "Datas", "TechnologicalProducts", "PozitifTeknoloji"
)
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(
    data_dir, f"pozitifTeknoloji_{datetime.now().strftime('%Y-%m-%d')}.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}

session = requests.Session()
session.headers.update(HEADERS)


# -----------------------------------------------------------------------------
# REGEX / FİYAT PARSE
# -----------------------------------------------------------------------------
# Türkçe fiyat formatları:
#   "30.999₺"      -> 30999.00 (. binlik ayracı)
#   "1.234,56 ₺"   -> 1234.56  (. binlik, , ondalık)
#   "999,99 TL"    -> 999.99
#   "999 ₺"        -> 999.00
PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?:₺|TL)",
    re.IGNORECASE
)


def _normalize_price_string(raw: str) -> str:
    """'1.234,56' / '30.999' / '999,99' -> standart float string."""
    if "." in raw and "," in raw:
        # Hem . hem , -> . binlik, , ondalık
        return raw.replace(".", "").replace(",", ".")
    if "," in raw:
        # Sadece , -> ondalık (Türkçe)
        return raw.replace(",", ".")
    # Sadece . (veya hiçbiri):
    # "30.999" gibi tam binlik formatıysa noktayı kaldır
    if re.match(r"^\d{1,3}(?:\.\d{3})+$", raw):
        return raw.replace(".", "")
    return raw


def parse_all_prices(text: str) -> list[float]:
    """Verilen metindeki tüm fiyat değerlerini float listesi olarak döndürür."""
    prices: list[float] = []
    if not text:
        return prices
    for match in PRICE_RE.finditer(text):
        cleaned = _normalize_price_string(match.group(1))
        try:
            prices.append(float(cleaned))
        except ValueError:
            continue
    return prices


# -----------------------------------------------------------------------------
# FETCH
# -----------------------------------------------------------------------------
def fetch_page(slug: str, page_num: int) -> str | None:
    """WooCommerce sayfa URL'i: /slug/ (1. sayfa) veya /slug/page/N/ (N>1)."""
    if page_num == 1:
        url = f"{BASE_URL}/{slug}/"
    else:
        url = f"{BASE_URL}/{slug}/page/{page_num}/"

    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                return None  # Sayfa yok - kategori bitti veya slug hatalı
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * attempt)
    print(f"   [ERROR] {slug} sayfa {page_num} alınamadı: {last_err}")
    return None


# -----------------------------------------------------------------------------
# PARSE
# -----------------------------------------------------------------------------
def get_total_pages(soup: BeautifulSoup) -> int:
    """WooCommerce pagination'dan toplam sayfa sayısını çıkar."""
    max_page = 1
    for el in soup.select(".page-numbers, .pagination a, .pagination span"):
        text = el.get_text(strip=True)
        if text.isdigit():
            n = int(text)
            if n > max_page:
                max_page = n
    return max_page


def is_out_of_stock(card) -> bool:
    """WooCommerce ürün kartı stokta olmayan ürün mü?"""
    classes = card.get("class") or []
    for c in classes:
        cl = c.lower()
        if "outofstock" in cl or "out-of-stock" in cl:
            return True
    # PT teması "Tükendi" badge'ı yerleştirir
    if card.select_one(".out-of-stock, .stok-yok, .tukendi"):
        return True
    text = card.get_text(" ", strip=True)
    if "Tükendi" in text or "Stokta yok" in text:
        return True
    return False


def parse_products(html: str, category_label: str) -> list[dict]:
    """Bir kategori sayfasındaki ürün kartlarını parse eder."""
    soup = BeautifulSoup(html, "lxml")

    # WooCommerce default: <ul class="products"> <li class="product">
    cards = soup.select("ul.products li.product")
    if not cards:
        cards = soup.select(".products .product")
    if not cards:
        # Bazı temalar farklı yapı kullanabilir
        cards = soup.select("[class*=product-item], [class*=product-card]")

    products: list[dict] = []
    for card in cards:
        if SKIP_OUT_OF_STOCK and is_out_of_stock(card):
            continue

        # Ürün adı: WooCommerce standart başlık class'ları
        name_el = (
            card.select_one("h2.woocommerce-loop-product__title")
            or card.select_one("h3.woocommerce-loop-product__title")
            or card.select_one(".woocommerce-loop-product__title")
            or card.select_one("h2")
            or card.select_one("h3")
            or card.select_one(".product-title")
        )
        name = name_el.get_text(strip=True) if name_el else None

        # Yedek: ürün linkinin metnine bak
        if not name:
            link = card.select_one("a.woocommerce-LoopProduct-link, a[href]")
            if link:
                # Sadece fiyat içermeyen text node'ları topla
                texts = [
                    t.strip() for t in link.stripped_strings
                    if t.strip() and not PRICE_RE.search(t)
                ]
                if texts:
                    name = " ".join(texts)

        if not name:
            continue

        # Fiyat: karttaki tüm fiyatları topla, en düşüğünü al.
        # İndirimli ürünlerde <del> orijinal, <ins> satış fiyatı içerir;
        # min(prices) doğal olarak satış fiyatını seçer.
        prices_in_card = parse_all_prices(card.get_text(" ", strip=True))
        if not prices_in_card:
            continue
        price = min(prices_in_card)

        # Dedup için ürün URL slug'ı
        link_el = card.select_one("a[href]")
        slug = None
        if link_el:
            href = link_el.get("href", "").strip()
            if href:
                # add-to-cart linkini değil ürün sayfası linkini al
                if "add-to-cart" in href:
                    for alt in card.select("a[href]"):
                        h = alt.get("href", "")
                        if h and "add-to-cart" not in h:
                            href = h
                            break
                slug = href.rstrip("/").split("/")[-1].split("?")[0]

        products.append({
            "name": name,
            "category": category_label,
            "price": price,
            "_slug": slug,
        })

    return products


# -----------------------------------------------------------------------------
# SCRAPE
# -----------------------------------------------------------------------------
def scrape_category(category: dict) -> tuple[list[dict], list[str]]:
    """Bir kategoriyi indirir. Paralel çalışmada print'ler birbirine
    karışmasın diye output'u doğrudan yazmak yerine bir liste olarak döner."""
    slug = category["slug"]
    label = category["label"]
    log: list[str] = []

    log.append(f"\n>> Kategori: {label}  ({BASE_URL}/{slug}/)")

    html1 = fetch_page(slug, 1)
    if not html1:
        log.append(f"   [HATA] {slug} sayfa 1 alınamadı / yok, atlanıyor.")
        return [], log

    soup1 = BeautifulSoup(html1, "lxml")
    page1_products = parse_products(html1, label)

    if not page1_products:
        log.append(f"   [UYARI] {slug} sayfasında ürün bulunamadı.")
        return [], log

    total_pages = get_total_pages(soup1)
    if total_pages > 1:
        log.append(f"   [sayfa   1] {len(page1_products)} ürün ({total_pages} sayfa)")
    else:
        log.append(f"   [sayfa   1] {len(page1_products)} ürün")

    all_products = list(page1_products)
    seen_slugs: set = {p["_slug"] for p in all_products if p["_slug"]}

    if total_pages > 1:
        remaining = list(range(2, min(total_pages, MAX_PAGES_PER_CATEGORY) + 1))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_page, slug, p): p for p in remaining}
            for future in as_completed(futures):
                p = futures[future]
                page_html = future.result()
                if not page_html:
                    continue
                new_products = parse_products(page_html, label)
                added = 0
                for prod in new_products:
                    s = prod["_slug"]
                    if s and s in seen_slugs:
                        continue
                    if s:
                        seen_slugs.add(s)
                    all_products.append(prod)
                    added += 1
                log.append(f"   [sayfa {p:>3}] {len(new_products)} ürün, {added} yeni")

    log.append(f"   -> Toplam {len(all_products)} benzersiz ürün ({label})")
    return all_products, log


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("=" * 70)
    print(f"Pozitif Teknoloji Scraper  |  {today_str}")
    print(f"Kategori sayısı: {len(CATEGORIES)}  |  Eş zamanlı: {CATEGORY_WORKERS}")
    print(f"Çıktı: {OUTPUT_FILE}")
    print("=" * 70)

    all_products: list[dict] = []
    seen_global: set = set()

    # Kategoriler paralel işleniyor. Her kategorinin log satırları kendi
    # bütünlüğünü korumak için bir liste içinde toplanır ve future tamamlanınca
    # tek seferde yazdırılır - böylece çıktı kategoriler arası karışmaz.
    completed = 0
    with ThreadPoolExecutor(max_workers=CATEGORY_WORKERS) as executor:
        futures = {
            executor.submit(scrape_category, cat): cat for cat in CATEGORIES
        }
        for future in as_completed(futures):
            cat = futures[future]
            completed += 1
            try:
                cat_products, log = future.result()
            except Exception as e:
                print(f"\n>> Kategori: {cat['label']}  [HATA: {e}]")
                continue

            # Bu kategorinin log'unu tek blok halinde yaz (ilerleme prefiksiyle)
            for line in log:
                print(line)
            print(f"   ({completed}/{len(CATEGORIES)} kategori tamamlandı)")

            # Global dedup
            for p in cat_products:
                s = p["_slug"]
                if s and s in seen_global:
                    continue
                if s:
                    seen_global.add(s)
                all_products.append(p)

    if not all_products:
        print("\n[FATAL] Hiç ürün çıkarılamadı.")
        return

    df = pd.DataFrame(all_products)
    df = df[["name", "category", "price"]]
    df = df.sort_values(["category", "name"]).reset_index(drop=True)

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"TAMAMLANDI")
    print(f"   Toplam ürün: {len(df)}")
    print(f"   Kategori dağılımı:")
    for cat, count in df["category"].value_counts().items():
        print(f"      {cat}: {count}")
    print(f"   Çıktı: {OUTPUT_FILE}")
    print(f"   Süre: {elapsed:.1f} sn")
    print("=" * 70)


if __name__ == "__main__":
    main()