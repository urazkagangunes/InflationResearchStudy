import os
import time
import csv
import json
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from camoufox.sync_api import Camoufox

# --- DOSYA YOLLARI ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
DATAS_DIR = os.path.join(_PROJECT_ROOT, "InflationItems", "Datas", "Cosmetics", "Watsons")
os.makedirs(DATAS_DIR, exist_ok=True)
MASTER_DB_PATH = os.path.join(DATAS_DIR, "watsons_master_db.json")
SITEMAP_CACHE_PATH = os.path.join(DATAS_DIR, "sitemap_cache.json")


def get_cookies():
    print("🔄 Camoufox ile tarayıcı açılıyor (Akamai Bypass)...")
    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        page.goto("https://www.watsons.com.tr/", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        cookies = {c['name']: c['value'] for c in page.context.cookies()}
        return cookies


def run_poc_scraper():
    print("⏳ Dosyalar yükleniyor...")

    # 1. JSON'ları Yükle
    if not os.path.exists(SITEMAP_CACHE_PATH):
        print("❌ sitemap_cache.json bulunamadı! Önce sitemap'i indirmelisin.")
        return

    with open(SITEMAP_CACHE_PATH, "r", encoding="utf-8") as f:
        sitemap_data = json.load(f)

    master_db = {}
    if os.path.exists(MASTER_DB_PATH):
        with open(MASTER_DB_PATH, "r", encoding="utf-8") as f:
            master_db = json.load(f)

    today_str = datetime.now().strftime("%Y-%m-%d")
    csv_file = os.path.join(DATAS_DIR, f"{today_str}_watsons_fiyatlar.csv")

    total_items = len(sitemap_data)
    print(f"🚀 PoC Sunum Modu Başladı! Toplam {total_items} ürün işlenecek.\n")

    # Çerezleri al ve Session kur
    session_cookies = get_cookies()
    client = requests.Session(impersonate="chrome")

    scraped = 0
    skipped = 0

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'name', 'normal_price'])
        writer.writeheader()

        for idx, (url, sitemap_date) in enumerate(sitemap_data.items(), start=1):

            # --- AKILLI ATLAMA (CACHE) ---
            if url in master_db and master_db[url].get('lastmod') == sitemap_date:
                item = master_db[url]
                writer.writerow({'url': url, 'name': item['name'], 'normal_price': item['price']})
                skipped += 1

                # Terminalde donmadığını göstermek için her 100 atlamada bir bilgi bas
                if skipped % 100 == 0:
                    print(f"⏩ [HIZLI GEÇİŞ] {skipped} ürün Master DB'den kopyalandı...")
                continue

            # --- YENİ VEYA GÜNCELLENMİŞ ÜRÜN (SCRAPE) ---
            try:
                res = client.get(url, cookies=session_cookies, timeout=10)

                if res.status_code == 403:
                    print("\n⛔ 403 Blok Yedik! Çerez tazeleniyor...")
                    session_cookies = get_cookies()
                    time.sleep(2)
                    continue  # Döngüyü kırma, çerez yenileyip bir sonrakine geç

                soup = BeautifulSoup(res.text, 'html.parser')
                name, price = "N/A", "N/A"

                for script in soup.find_all('script', type='application/ld+json'):
                    if script.string and url in script.string:
                        data = json.loads(script.string)
                        for entry in data.get('@graph', []):
                            if entry.get('@type') == 'Product':
                                name = entry.get('name', 'N/A')
                                break

                price_el = soup.select_one('span.price__default-value')
                if price_el:
                    price = price_el.text.strip()

                print(f"✅ [ÇEKİLDİ] {name[:40]}... -> {price}")

                # Veritabanlarını güncelle
                master_db[url] = {"lastmod": sitemap_date, "name": name, "price": price}
                writer.writerow({'url': url, 'name': name, 'normal_price': price})
                scraped += 1
                f.flush()

                # Hocaya gösterilecek prototip olduğu için DB'yi sık sık kaydet
                if scraped % 10 == 0:
                    with open(MASTER_DB_PATH, "w", encoding="utf-8") as db_f:
                        json.dump(master_db, db_f, indent=4, ensure_ascii=False)

                time.sleep(0.3)  # Saygılı bekleme süresi

            except Exception as e:
                print(f"❌ [HATA] {url.split('/')[-1]}: {e}")

    # İşlem bittiğinde son halini kaydet
    with open(MASTER_DB_PATH, "w", encoding="utf-8") as db_f:
        json.dump(master_db, db_f, indent=4, ensure_ascii=False)

    print(f"\n🎉 İşlem Tamamlandı! Hoca için sunum dosyası hazır:")
    print(f"   -> Toplam Hızlı Atlanan: {skipped}")
    print(f"   -> Toplam Yeni Çekilen: {scraped}")
    print(f"   -> Çıktı Dosyası: {csv_file}")


if __name__ == "__main__":
    run_poc_scraper()
