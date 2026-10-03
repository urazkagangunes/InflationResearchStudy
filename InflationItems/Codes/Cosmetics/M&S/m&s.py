import csv, os, re, time, random, shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPT_DIR, "Datas", "M&S")
PROFILE_DIR = os.path.join(SCRIPT_DIR, "SeleniumProfile_MS")
URL         = "https://www.marksandspencer.com.tr/list/?layout=4&category_ids=84"

seen = set()


def driver_ac():
    opts = uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--headless=new")
    opts.add_argument("--log-level=3")
    d = uc.Chrome(options=opts)
    d.set_page_load_timeout(60)
    return d


def get_csv_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    tarih = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return os.path.join(OUT_DIR, f"ms_cosmetics_{tarih}.csv")


def temizle(raw):
    if not raw: return ""
    raw = raw.replace("TL","").replace("₺","").replace("\xa0"," ").strip()
    m = re.search(r"[\d.,]+", raw)
    return m.group(0) if m else ""


def scroll_son(driver, bekle=2.0, max_tur=80):
    son, stable = driver.execute_script("return document.body.scrollHeight"), 0
    for _ in range(max_tur):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(bekle)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == son:
            stable += 1
            if stable >= 3: break
        else:
            stable, son = 0, yeni


def parse(soup):
    
    batch = []
    isimler = soup.select("a.product-item__name")
    fiyatlar = soup.select("pz-price")

    
    for isim_el, fiyat_el in zip(isimler, fiyatlar):
        isim  = isim_el.get_text(" ", strip=True)
        fiyat = temizle(fiyat_el.get_text(" ", strip=True))
        if not isim or not fiyat: continue
        key = (isim.lower(), fiyat)
        if key in seen: continue
        seen.add(key)
        batch.append({"urun_adi": isim, "fiyat": fiyat})
    return batch


def max_sayfa(soup):
    mx = 1
    for a in soup.select("a[href]"):
        m = re.search(r"[?&]page=(\d+)", a.get("href",""))
        if m: mx = max(mx, int(m.group(1)))
    for el in soup.select("li.pager-item, li.page-item, .pagination li"):
        t = el.get_text(strip=True)
        if t.isdigit(): mx = max(mx, int(t))
    return mx


def main():
    csv_path = get_csv_path()
    print("=" * 55)
    print("  M&S TR Kozmetik Scraper")
    print("=" * 55)
    print(f"  Çıktı: {csv_path}\n")

    driver   = driver_ac()
    tum_batch = []
    sayfa    = 1

    try:
        while True:
            url = URL if sayfa == 1 else f"{URL}&page={sayfa}"
            print(f"  Sayfa {sayfa}: {url}")
            driver.get(url)
            time.sleep(8)       # JS render için bekle
            scroll_son(driver)
            time.sleep(2)

            soup  = BeautifulSoup(driver.page_source, "html.parser")
            batch = parse(soup)

            if not batch:
                print("  ⚠️  Ürün bulunamadı, duruyorum.")
                break

            tum_batch.extend(batch)
            print(f"  ✅ {len(batch)} ürün (toplam: {len(tum_batch)})")

            maks = max_sayfa(soup)
            if sayfa >= maks: break
            sayfa += 1
            time.sleep(random.uniform(2, 4))

    except KeyboardInterrupt:
        print("\nDurduruldu.")
    finally:
        driver.quit()
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)

    if tum_batch:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["urun_adi","fiyat"])
            w.writeheader()
            w.writerows(tum_batch)
        print(f"\n✅ {len(tum_batch)} ürün → {csv_path}")
    else:
        print("\n❌ Hiç ürün çekilemedi.")


if __name__ == "__main__":
    main()
