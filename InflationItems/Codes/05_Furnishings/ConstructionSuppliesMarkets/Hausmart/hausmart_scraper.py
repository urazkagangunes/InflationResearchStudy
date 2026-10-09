"""
hausmart_scraper.py
-------------------
Hausmart.com.tr günlük ürün fiyat scraper'ı.
Selenium + headless Chrome kullanır (site ürünleri JavaScript ile yüklüyor).

Gereksinimler:
    pip install selenium webdriver-manager beautifulsoup4 lxml

Kullanım:
    python hausmart_scraper.py

Çıktı:
    hausmart_YYYY-MM-DD.csv  →  item_name | price | category | date
"""

import csv
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/ConstructionSuppliesMarkets/Hausmart/hausmart_scraper.py
# Veri:     InflationItems/Datas/ConstructionSuppliesMarkets/Hausmart/
REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / ".git").exists()), Path(__file__).resolve().parents[5])
OUT_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "ConstructionSuppliesMarkets" / "Hausmart"
OUT_DIR.mkdir(parents=True, exist_ok=True)

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASE_URL = "https://www.hausmart.com.tr"

CATEGORIES = [
    {"name": "Yapı Market & Bahçe",  "url": f"{BASE_URL}/yapi-market-bahce"},
    {"name": "Ev Yaşam",             "url": f"{BASE_URL}/ev-yasam-hepsiburada"},
    {"name": "Banyo",                 "url": f"{BASE_URL}/banyo"},
    {"name": "Makina-El Aletleri",    "url": f"{BASE_URL}/makina-el-aletleri"},
    {"name": "Eviye",                 "url": f"{BASE_URL}/evye"},
    {"name": "Boya",                  "url": f"{BASE_URL}/boya"},
    {"name": "Bataryalar",            "url": f"{BASE_URL}/bataryalar-uygun-kalite"},
    {"name": "Oto Bakım & Aksesuar",  "url": f"{BASE_URL}/oto-bakim-aksesuar-trendyol"},
    {"name": "İş Güvenliği",          "url": f"{BASE_URL}/is-guvenligi-amazon"},
]

PAGE_LOAD_TIMEOUT = 30
PRODUCT_WAIT      = 20    # JS render için max bekleme (saniye)
POST_LOAD_SLEEP   = 3.0   # Render sonrası ek bekleme (saniye)
BASE_DELAY        = 1.5
JITTER_MIN        = 0.6
JITTER_MAX        = 1.8
DEFAULT_WORKERS   = 3

# Fiyat regex: "8.085,00 TL" veya "622,96 TL"
_PRICE_RE = re.compile(r"([\d]{1,3}(?:\.[\d]{3})*,\d{2})\s*TL")

# Kesinlikle ürün olmayan path sonekleri
_SKIP_PATH_PREFIXES = (
    "/hesabim", "/sepet", "/uye-", "/siparis", "/yardim",
    "/iletisim", "/hakkimizda", "/gizlilik", "/kullanici",
    "/sss", "/havale", "/cdn-cgi", "/https/", "/arama",
    "/tumu-c-",
)

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DRIVER FACTORY
# ---------------------------------------------------------------------------

def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=tr-TR")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver

# ---------------------------------------------------------------------------
# PRICE PARSER
# ---------------------------------------------------------------------------

def extract_last_price(text: str) -> float | None:
    """
    String içindeki son "X.XXX,XX TL" pattern'ını float'a çevirir.
    İndirimli ürünlerde sonuncu eşleşme = satış fiyatı.
    Fiyat yoksa None döner → stokta yok → CSV'ye alınmaz.
    """
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    try:
        value = float(matches[-1].replace(".", "").replace(",", "."))
        return value if value > 0 else None
    except ValueError:
        return None

# ---------------------------------------------------------------------------
# URL NORMALIZER
# ---------------------------------------------------------------------------

def normalize_href(href: str) -> str | None:
    """
    Hem tam URL hem relative path kabul eder, canonical tam URL döndürür.

    Qukasoft HTML'inde href'ler tam URL olarak gelir:
        href="https://www.hausmart.com.tr/urun-slug"
    Ama bazı elementlerde relative de olabilir:
        href="/urun-slug"
    İkisini de handle ediyoruz.
    """
    if not href:
        return None

    # Tam URL — BASE_URL ile başlamalı
    if href.startswith("https://") or href.startswith("http://"):
        if not href.startswith(BASE_URL):
            return None   # başka domain
        path = href[len(BASE_URL):]
    elif href.startswith("/"):
        path = href
    else:
        return None  # javascript:, mailto: vb.

    # Navigasyon path'lerini filtrele
    if any(path.startswith(p) for p in _SKIP_PATH_PREFIXES):
        return None

    # Çok kısa path → kategori ana sayfası, ürün değil
    if len(path) < 8:
        return None

    return BASE_URL + path

# ---------------------------------------------------------------------------
# PAGE PARSER
# ---------------------------------------------------------------------------

def parse_products(html: str, category_name: str, date_str: str) -> list[dict]:
    """
    Render edilmiş HTML'den ürünleri çıkarır.

    Ürün tespiti:
      1. Anchor'ın text'inde geçerli TL fiyatı var mı?  → navigasyon/banner eleme
      2. Ürün adı: anchor[title] → img[title] → img[alt] → fallback yok

    NOT: a[href][title] selectoru Qukasoft'ta bazı ürün kartlarını atlıyordu.
    Bu kartlarda title anchor'da değil içindeki <img> tag'inde bulunur.
    Şimdi a[href] ile tüm anchor'lar taranıp title fallback zinciriyle çözülüyor.
    """
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    products: list[dict] = []

    for anchor in soup.select("a[href]"):
        raw_href = anchor.get("href", "").strip()

        canonical = normalize_href(raw_href)
        if canonical is None:
            continue
        if canonical in seen:
            continue

        raw_text = anchor.get_text(separator=" ", strip=True)
        price = extract_last_price(raw_text)

        # Fiyat yoksa → stokta yok veya navigasyon → atla
        if price is None:
            continue

        # Ürün adı: anchor[title] → img[title] → img[alt]
        title = anchor.get("title", "").strip()
        if not title:
            img = anchor.find("img")
            if img:
                title = img.get("title", "").strip() or img.get("alt", "").strip()

        if not title:
            continue

        seen.add(canonical)
        products.append({
            "canonical":    canonical,
            "product_name": title,
            "price":        price,
        })

    return products

# ---------------------------------------------------------------------------
# CATEGORY SCRAPER
# ---------------------------------------------------------------------------

def scrape_category(category: dict, driver: webdriver.Chrome, date_str: str) -> dict[str, dict]:
    """
    Bir kategorinin tüm sayfalarını ?sayfa=N ile dolaşır.
    """
    cat_name = category["name"]
    cat_url  = category["url"]

    seen_canonicals: set[str] = set()
    results: dict[str, dict]  = {}
    page = 1

    logger.info(f"[{cat_name}] Başlatılıyor → {cat_url}")

    while True:
        url = cat_url if page == 1 else f"{cat_url}?sayfa={page}"

        try:
            driver.get(url)

            # JS ürün render'ını bekle:
            # "TL" içeren herhangi bir anchor yeterli — @title şartı kaldırıldı,
            # bazı ürün kartlarında title anchor'da değil img'de bulunur.
            WebDriverWait(driver, PRODUCT_WAIT).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[contains(., 'TL')]")
                )
            )
            # Lazy-load: viewport dışındaki kartları tetiklemek için scroll
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            driver.execute_script("window.scrollTo(0, 0);")
            # Tüm ürünlerin render tamamlanması için ek bekleme
            time.sleep(POST_LOAD_SLEEP)

        except Exception:
            logger.info(f"[{cat_name}] Sayfa {page}: timeout → pagination bitti.")
            break

        page_products = parse_products(driver.page_source, cat_name, date_str)

        if not page_products:
            logger.info(f"[{cat_name}] Sayfa {page}: ürün bulunamadı → pagination bitti.")
            break

        page_canonicals = {p["canonical"] for p in page_products}
        if page_canonicals.issubset(seen_canonicals):
            logger.info(f"[{cat_name}] Sayfa {page}: içerik tekrarlı → pagination bitti.")
            break

        new_count = 0
        for p in page_products:
            c = p["canonical"]
            if c not in seen_canonicals:
                seen_canonicals.add(c)
                results[c] = p
                new_count += 1

        logger.info(f"[{cat_name}] Sayfa {page}: +{new_count} ürün (toplam: {len(results)})")

        page += 1
        time.sleep(BASE_DELAY * random.uniform(JITTER_MIN, JITTER_MAX))

    logger.info(f"[{cat_name}] Tamamlandı → {len(results)} benzersiz ürün.")

    # Name-level dedup: aynı kategori içinde aynı Product Name farklı URL'lerle
    # gelebilir (varyant listelemeleri). Fiyat serisini tutarlı tutmak için
    # en düşük fiyatlı kaydı tut (= aktif satış fiyatı).
    name_best: dict[str, dict] = {}
    for p in results.values():
        name = p["product_name"]
        if name not in name_best or p["price"] < name_best[name]["price"]:
            name_best[name] = p

    removed = len(results) - len(name_best)
    if removed:
        logger.info(f"[{cat_name}] Name-level dedup: {removed} varyant kaydı silindi.")

    return name_best

# ---------------------------------------------------------------------------
# WORKER
# ---------------------------------------------------------------------------

def worker(category: dict, date_str: str) -> dict[str, dict]:
    """Her thread kendi Chrome driver'ını açar ve kapatır."""
    driver = create_driver()
    try:
        return scrape_category(category, driver, date_str)
    finally:
        driver.quit()

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = OUT_DIR / f"hausmart_{date_str}.csv"

    logger.info(f"Hausmart scraper başlatılıyor → {date_str}")
    logger.info(f"Kategori: {len(CATEGORIES)} | Worker: {DEFAULT_WORKERS}")

    # Cross-category global dedup KALDIRILDI.
    # Aynı ürün URL'si birden fazla kategori listesinde çıkabilir (Hausmart yapısı).
    # Her kategori bağımsız fiyat serisi oluşturduğundan, tüm category-level sonuçlar
    # ayrı satır olarak tutulur. Dedup yalnızca kategori içinde (scrape_category) yapılır.
    all_products: list[dict] = []

    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as executor:
        future_to_cat = {
            executor.submit(worker, cat, date_str): cat
            for cat in CATEGORIES
        }
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_results = future.result()
                all_products.extend(cat_results.values())
                logger.info(
                    f"[{cat['name']}] merge edildi → +{len(cat_results)} ürün "
                    f"(genel toplam: {len(all_products)})"
                )
            except Exception as exc:
                logger.error(f"[{cat['name']}] Hata: {exc}")

    final = sorted(
        all_products,
        key=lambda p: p["product_name"],
    )

    fieldnames = ["product_name", "price"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(final)

    logger.info(f"✓ Tamamlandı: {csv_path} → {len(final)} ürün kaydedildi.")


if __name__ == "__main__":
    main()
