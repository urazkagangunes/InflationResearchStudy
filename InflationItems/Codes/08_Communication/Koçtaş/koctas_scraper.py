import time
import csv
import os
import random
import tempfile
from datetime import date, datetime
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/TechnologicalProducts/Koçtaş/koctas_scraper.py
# Veri:     InflationItems/Datas/TechnologicalProducts/Koçtaş/
REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "TechnologicalProducts" / "Koçtaş"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = [
    ("Akülü Vidalamalar",      "https://www.koctas.com.tr/elektrikli-el-aletleri/akulu-vidalamalar/c/106007",              "05", 7),
    ("Matkaplar",              "https://www.koctas.com.tr/elektrikli-el-aletleri/matkaplar/c/106001",                      "05", 7),
    ("Kırıcılar ve Deliciler", "https://www.koctas.com.tr/elektrikli-el-aletleri/kiricilar-ve-deliciler/c/106010",         "05", 7),
    ("Taşlamalar",             "https://www.koctas.com.tr/elektrikli-el-aletleri/taslamalar/c/106009",                     "05", 7),
    ("Testereler",             "https://www.koctas.com.tr/elektrikli-el-aletleri/testereler/c/106003",                     "05", 7),
    ("Zımpara ve Polisaj",     "https://www.koctas.com.tr/elektrikli-el-aletleri/zimpara-ve-polisaj/c/106004",             "05", 7),
    ("Boya Tabancaları",       "https://www.koctas.com.tr/elektrikli-el-aletleri/boya-tufangi-ve-karistiricilar/c/106006", "05", 7),
    ("Kaynak Makineleri",      "https://www.koctas.com.tr/kaynak-makineleri/inverter-kaynak-makineleri/c/106015008",       "05", 7),
]

DATE_STR    = date.today().strftime("%Y.%m.%d")
OUT_FILE    = OUT_DIR / f"koctas_{DATE_STR}.csv"
START_TIME  = None

def elapsed():
    secs = (datetime.now() - START_TIME).total_seconds()
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"

def make_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--start-minimized")
    opts.add_argument("--window-position=-2000,-2000")
    opts.add_argument("--log-level=3")
    tmp_dir = tempfile.mkdtemp()
    opts.add_argument(f"--user-data-dir={tmp_dir}")
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    })
    return uc.Chrome(options=opts, use_subprocess=True, version_main=148)

def get_total_pages(driver):
    try:
        pages = driver.find_elements(By.CSS_SELECTOR, ".pagination a, [class*='pagination'] a")
        nums = [int(p.text.strip()) for p in pages if p.text.strip().isdigit()]
        return max(nums) if nums else 1
    except Exception:
        return 1

def _wait_for_datalayer(driver, timeout=12, interval=0.5):
    """dataLayer'da product-impressions verisi olana kadar bekle."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            count = driver.execute_script("""
                var dl = window.dataLayer || [];
                var n = 0;
                dl.forEach(function(d) {
                    if (d.event === 'product-impressions' && d.ecommerce && d.ecommerce.impressions) {
                        n += d.ecommerce.impressions.length;
                    }
                });
                return n;
            """)
            if count and count > 0:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False

def parse_page(driver, url):
    driver.get(url)
    _wait_for_datalayer(driver, timeout=12, interval=0.5)
    time.sleep(random.uniform(0.3, 0.8))

    products = []
    try:
        items = driver.execute_script("""
            var dl = window.dataLayer || [];
            var imp = [];
            dl.forEach(function(d) {
                if (d.event === 'product-impressions' && d.ecommerce && d.ecommerce.impressions) {
                    imp = imp.concat(d.ecommerce.impressions);
                }
            });
            return imp;
        """)
        for it in (items or []):
            name  = it.get("name", "").strip()
            price = it.get("price", "")
            if name and price:
                try:
                    if isinstance(price, (int, float)):
                        price_f = round(float(price) / 100, 2)
                    else:
                        s = str(price).strip()
                        price_f = round(float(s.replace(".", "").replace(",", ".")) / 100, 2)
                except Exception:
                    price_f = None
                products.append({"name": name, "price": price_f})
    except Exception:
        pass
    return products

def scrape_category(driver, cat_name, base_url, max_pages):
    results = []
    try:
        prods = parse_page(driver, base_url)
        total_pages = min(get_total_pages(driver), max_pages)
        print(f"[{elapsed()}]  [{cat_name}] {total_pages} sayfa (max {max_pages})")
        print(f"[{elapsed()}]  [{cat_name}] Sayfa 1/{total_pages}: {len(prods)} ürün")

        for p in prods:
            results.append({"product_name": p["name"], "price": p["price"]})

        for page in range(2, total_pages + 1):
            time.sleep(random.uniform(1.0, 2.0))
            prods = parse_page(driver, f"{base_url}?page={page}")

            if len(prods) == 0:
                print(f"[{elapsed()}]  [{cat_name}] Sayfa {page}/{total_pages}: 0 ürün — BLOK, kategori atlanıyor")
                break

            for p in prods:
                results.append({"product_name": p["name"], "price": p["price"]})
            print(f"[{elapsed()}]  [{cat_name}] Sayfa {page}/{total_pages}: {len(prods)} ürün")

    except Exception as e:
        print(f"[{elapsed()}]  [{cat_name}] HATA: {e}")
    return results

def main():
    global START_TIME
    START_TIME = datetime.now()
    print(f"Başlangıç: {START_TIME.strftime('%H:%M:%S')}")

    if os.path.exists(OUT_FILE):
        print(f"Dosya zaten var, atlanıyor: {OUT_FILE}")
        return

    driver = make_driver()
    all_results = []

    try:
        for cat_name, url, tuik, max_pages in CATEGORIES:
            print(f"\n[{elapsed()}]  === {cat_name} başlıyor ===")
            data = scrape_category(driver, cat_name, url, max_pages)
            all_results.extend(data)
            print(f"[{elapsed()}]  ✓ {cat_name}: {len(data)} ürün")
            time.sleep(random.uniform(2.5, 4.0))
    finally:
        driver.quit()

    seen = set()
    deduped = []
    for row in all_results:
        key = row["product_name"]
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    fieldnames = ["product_name", "price"]
    with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped)

    print(f"\n[{elapsed()}]  ✓ Toplam: {len(deduped)} ürün → {OUT_FILE}")

if __name__ == "__main__":
    main()