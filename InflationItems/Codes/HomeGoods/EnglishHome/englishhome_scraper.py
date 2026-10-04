"""
englishhome_scraper.py — English Home Günlük Ürün Fiyat Scraper'ı

Ticimax altyapısı. Kategori sayfasındaki productsModel'den kategori/etiket
id'si okunur; ürünler sitenin kendi ürün listesi API'sinden
(/api/product/GetProductList) sabit sıralamayla sayfa sayfa çekilir.
Tarayıcı gerekmez.

Gereksinimler:
    pip install requests

Kullanım:
    python englishhome_scraper.py

Çıktı:
    englishhome_YYYY-MM-DD.csv  →  product_name | price
"""

import csv
import json
import logging
import math
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/HomeGoods/EnglishHome/englishhome_scraper.py
# Veri:     InflationItems/Datas/HomeGoods/EnglishHome/
REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "EnglishHome"
OUT_DIR.mkdir(parents=True, exist_ok=True)

import requests

# ── Konfigürasyon ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.englishhome.com"
LIST_API = f"{BASE_URL}/api/product/GetProductList"

# Hocanın talimatı: Home, Home Decoration, Living kategorileri
# Kozmetik dahil — farklı COICOP kodu ile mapping'lenir
CATEGORIES = [
    {"name": "Yatak Odası",       "slug": "c-yatak-odasi"},
    {"name": "Sofra",             "slug": "c-sofra"},
    {"name": "Mutfak",            "slug": "c-mutfak"},
    {"name": "Küçük Ev Aletleri", "slug": "c-kucuk-ev-aletleri"},
    {"name": "Dekorasyon",        "slug": "c-dekorasyon"},
    {"name": "Banyo",             "slug": "c-banyo"},
    {"name": "Kozmetik",          "slug": "c-kisisel-bakim-kozmetik"},
    {"name": "Halı&Kilim",        "slug": "c-hali-kilim"},
    {"name": "Çeyiz Ürünleri",    "slug": "c-ceyiz-listesi"},
    {"name": "Hediye",            "slug": "yeni-ev-hediyesi"},
]

REQUEST_TIMEOUT = 40
MAX_RETRIES     = 4
RETRY_STATUS    = {429, 500, 502, 503, 504}
DEFAULT_WORKERS = 3
MIN_COVERAGE    = 0.98

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# The site's default order (KATEGORISIRA) has ties, so page contents shift
# between requests: on 2026-09-28 paging c-sofra that way skipped 5 % of it.
# uk.ID (the site's "Yeni Gelenler" order) is unique, hence stable.
ORDER_BY        = "uk.ID"
ORDER_DIRECTION = "DESC"

# Same filter the site's own product list sends, so totalProductCount equals
# the count shown on the category page.
BASE_FILTER = {
    "CategoryIdList": [], "BrandIdList": [], "SupplierIdList": [],
    "TagIdList": [], "TagId": -1, "FilterObject": [], "MinStockAmount": -1,
    "IsShowcaseProduct": -1, "IsOpportunityProduct": -1, "FastShipping": -1,
    "IsNewProduct": -1, "IsBestSeller": -1, "IsDiscountedProduct": -1,
    "IsShippingFree": -1, "IsProductCombine": -1, "MinPrice": 0,
    "MaxPrice": 0, "Point": -1, "SearchKeyword": "", "StrProductIds": "",
    "IsSimilarProduct": False, "RelatedProductId": 0, "ProductKeyword": "",
    "PageContentId": 0, "StrProductIDNotEqual": "", "IsVariantList": -1,
    "IsVideoProduct": -1, "ShowBlokVideo": -1,
    "VideoSetting": {"ShowProductVideo": -1, "AutoPlayVideo": -1},
    "ShowList": 1, "VisibleImageCount": 0, "ShowCounterProduct": -1,
    "ImageSliderActive": True, "ProductListPageId": 0,
    "ShowGiftHintActive": False, "IsInStock": False, "IsPriceRequest": True,
    "IsProductListPage": True, "NonStockShowEnd": 1,
}

# productsModel.pageType → filter field holding the page's id
PAGE_TYPE_FILTER = {1: "CategoryIdList", 2: "BrandIdList", 5: "TagIdList"}

# Fiyat regex: "₺499,99" veya "₺1.199,99"  veya "499,99" veya "1.199,99"
_PRICE_RE = re.compile(r"[₺]?([\d]{1,3}(?:\.[\d]{3})*,\d{2})")

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── CSV dosya koruması ────────────────────────────────────────────────────────

def _check_existing(csv_path: str):
    """Bugünün CSV'si zaten varsa çalıştırmayı durdur."""
    if os.path.exists(csv_path):
        logger.error(
            f"⛔ DURDURULDU: '{csv_path}' zaten mevcut!\n"
            f"   Bugün ikinci kez çalıştırıyorsunuz."
        )
        sys.exit(0)

# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET with a 1-3 s polite delay; retries 429/5xx and network errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(random.uniform(1, 3))
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            reason = type(exc).__name__
        else:
            if resp.status_code not in RETRY_STATUS:
                resp.raise_for_status()
                return resp
            reason = f"HTTP {resp.status_code}"
        logger.warning(f"  {reason}: {url} (deneme {attempt}/{MAX_RETRIES})")
        if attempt < MAX_RETRIES:
            time.sleep(5 * 2 ** (attempt - 1))
    raise RuntimeError(f"{url}: {MAX_RETRIES} denemede alınamadı")

# ── Fiyat parse ───────────────────────────────────────────────────────────────

def parse_price(text: str) -> float | None:
    """'₺1.199,99' veya '1.199,99' → 1199.99 float. Bulamazsa None."""
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    try:
        value = float(matches[0].replace(".", "").replace(",", "."))
        return value if value > 0 else None
    except ValueError:
        return None


def product_price(item: dict) -> float | None:
    """Müşterinin ödediği fiyat (KDV dahil).

    productCartPriceStr = sepet fiyatı ("sepette ek indirim" varsa en düşük),
    productPriceOriginalStr = kartta görünen indirimli fiyat (discountPriceSpan).
    productSellPriceStr üstü çizili liste fiyatıdır, kullanılmaz.
    """
    for key in ("productCartPriceStr", "productPriceOriginalStr"):
        price = parse_price(item.get(key) or "")
        if price:
            return price
    return None


def product_name(item: dict) -> str:
    # The card's title attribute, used as product_name before, drops quotes;
    # keep that form so names still match earlier files.
    return re.sub(r"[\"']", "", item.get("name") or "").strip()

# ── Kategori scraper ──────────────────────────────────────────────────────────

def get_page_model(session: requests.Session, slug: str) -> dict:
    """Kategori/etiket sayfasındaki productsModel (pageType, targetId)."""
    html = _get(session, f"{BASE_URL}/{slug}").text
    start = html.index("{", html.index("var productsModel"))
    model, _ = json.JSONDecoder().raw_decode(html, start)
    return model


def fetch_page(session: requests.Session, model: dict, page: int) -> dict:
    field = PAGE_TYPE_FILTER[model["pageType"]]
    list_filter = dict(BASE_FILTER, **{field: [model["targetId"]]})
    paging = {
        "PageItemCount": 0,
        "PageNumber": page,
        "OrderBy": ORDER_BY,
        "OrderDirection": ORDER_DIRECTION,
    }
    params = {
        "c": "trtry0000",
        "FilterJson": json.dumps(list_filter, separators=(",", ":")),
        "PagingJson": json.dumps(paging, separators=(",", ":")),
        "CreateFilter": "false",
        "TransitionOrder": 0,
        "PageType": model["pageType"],
        "PageId": model["targetId"],
    }
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/"}
    data = _get(session, LIST_API, params=params, headers=headers).json()
    if data.get("isError"):
        raise RuntimeError(f"API hatası: {data.get('errorMessage')}")
    return data


def scrape_category(category: dict) -> list[dict]:
    """Bir kategorinin tüm sayfalarını API'den çeker."""
    cat_name = category["name"]
    session = requests.Session()
    session.headers.update(HEADERS)

    logger.info(f"▶ Kategori: {cat_name}")
    model = get_page_model(session, category["slug"])

    all_products = []
    seen_ids = set()
    page, total_pages, total_items = 1, 1, None

    failed_pages = []

    while page <= total_pages:
        try:
            data = fetch_page(session, model, page)
        except Exception as exc:
            logger.error(f"  {cat_name} sayfa {page}: alınamadı ({exc})")
            failed_pages.append(page)
            page += 1
            continue

        total_items = data.get("totalProductCount") or 0
        per_page = data.get("productCountPerPage") or 1
        total_pages = math.ceil(total_items / per_page)
        items = data.get("products") or []

        for item in items:
            product_id = str(item.get("productId") or "")
            name = product_name(item)
            price = product_price(item)
            if not product_id or not name or price is None:
                continue
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            all_products.append({
                "product_name": name,
                "price":        price,
                "product_id":   product_id,
            })

        if page % 10 == 0 or page == total_pages:
            logger.info(f"  Sayfa {page}/{total_pages}: toplam {len(all_products)} ürün")

        if not items:
            break
        page += 1

    problems = []
    if failed_pages:
        problems.append(f"alınamayan sayfalar: {failed_pages}")
    if total_items and len(all_products) < MIN_COVERAGE * total_items:
        problems.append(
            f"kapsama {len(all_products)}/{total_items} "
            f"({len(all_products) / total_items:.1%})"
        )
    if problems:
        raise RuntimeError(f"{cat_name} eksik: " + "; ".join(problems))

    logger.info(f"  ✓ {cat_name}: {len(all_products)}/{total_items} ürün\n")
    return all_products

# ── Plausibility (data-error) filtresi ────────────────────────────────────────
# English Home'un kendi sitesi zaman zaman bazı ürünlerde hatalı/şişik fiyat
# servis ediyor (aynı ürün Trendyol/LCW'de ve bizim geçmiş verimizde ~5× düşük;
# 2026-05-31'de doğrulandı). Bir ürünün fiyatı bir önceki güne göre bu faktör
# bandı dışına çıkıyorsa, yanlış fiyatı CSV'ye yazmak yerine o ürünü ATLARIZ —
# böylece günlük CSV temiz kalır (paylaşılan ulusal pipeline için de güvenli).
PLAUSIBLE_MIN = 0.25   # fiyat 1/4'ün altına düştüyse → hatalı
PLAUSIBLE_MAX = 4.0    # fiyat 4 katından fazla arttıysa → hatalı


def _load_prev_prices(days_back: int = 7) -> dict:
    """Son birkaç günün CSV'lerinden BİRLEŞİK {product_name: price} bazı döner.

    En yeni günden geriye doğru gider, her ürün için ilk (en yeni) bulunan fiyatı
    kullanır. Tek bir günün kısa/eksik scrape'i bazı zayıflatıp glitch ürünlerin
    filtreden kaçmasına yol açmasın diye birden çok gün birleştirilir.
    """
    prices = {}
    for back in range(1, days_back + 1):
        d = date.today() - timedelta(days=back)
        f = OUT_DIR / f"englishhome_{d}.csv"
        if not f.exists():
            continue
        try:
            with open(f, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    name = row.get("product_name")
                    if not name or name in prices:   # daha yeni gün zaten yazdı
                        continue
                    try:
                        prices[name] = float(row["price"])
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            logger.warning(f"Önceki gün okunamadı ({f.name}): {e}")
    if prices:
        logger.info(f"Plausibility bazı: son {days_back} günden {len(prices)} ürün")
    else:
        logger.info("Plausibility bazı bulunamadı — filtre uygulanmadan devam.")
    return prices


def _apply_plausibility_filter(products: list) -> list:
    """Fiyatı düne göre mantıksız değişen ürünleri (site hatası) eler."""
    prev = _load_prev_prices()
    if not prev:
        return products
    kept, dropped = [], 0
    for p in products:
        base = prev.get(p["product_name"])
        if base and base > 0:
            ratio = p["price"] / base
            if not (PLAUSIBLE_MIN <= ratio <= PLAUSIBLE_MAX):
                dropped += 1
                continue
        kept.append(p)
    if dropped:
        logger.warning(
            f"⚠️ Plausibility filtresi: {dropped} ürün mantıksız fiyat (siteden "
            f"gelen hatalı/aşırı değer) nedeniyle atlandı. Kalan: {len(kept)}"
        )
    return kept


# ── Ana çalıştırıcı ───────────────────────────────────────────────────────────

def main():
    today_str = str(date.today())
    csv_path = OUT_DIR / f"englishhome_{today_str}.csv"

    _check_existing(csv_path)

    logger.info("=" * 55)
    logger.info(f"  English Home Scraper — {today_str}")
    logger.info(f"  Kategori: {len(CATEGORIES)} | Worker: {DEFAULT_WORKERS}")
    logger.info("=" * 55)

    fieldnames = ["product_name", "price"]
    all_products = []
    global_seen = set()
    failed = []

    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as executor:
        future_to_cat = {
            executor.submit(scrape_category, cat): cat
            for cat in CATEGORIES
        }
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_products = future.result()

                new_count = 0
                for p in cat_products:
                    key = p["product_id"]
                    if key not in global_seen:
                        global_seen.add(key)
                        all_products.append(p)
                        new_count += 1

                logger.info(
                    f"  [{cat['name']}] merge edildi → +{new_count} ürün "
                    f"(genel toplam: {len(all_products)})"
                )

                if new_count < len(cat_products):
                    logger.info(
                        f"  Cross-category dedup: {len(cat_products) - new_count} "
                        f"duplicate atlandı"
                    )

            except Exception as exc:
                logger.error(f"  [{cat['name']}] Hata: {exc}")
                failed.append(cat["name"])

    # The runner counts any CSV with 2+ lines as success, so a partial scrape
    # must not leave one behind.
    if failed:
        logger.error(
            f"  EKSİK VERİ: {', '.join(failed)} tamamlanamadı; CSV yazılmadı."
        )
        sys.exit(1)

    # CSV kaydet
    all_products.sort(key=lambda p: (p["product_name"], p["product_id"]))

    # Site kaynaklı hatalı/şişik fiyatları yazmadan önce ele (düne göre mantıksız
    # sıçrayanlar atlanır → CSV temiz kalır).
    all_products = _apply_plausibility_filter(all_products)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_products)

    logger.info("=" * 55)
    logger.info(f"  TAMAMLANDI — {len(all_products)} ürün → '{csv_path}'")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()