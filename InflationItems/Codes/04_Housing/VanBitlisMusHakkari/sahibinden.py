import os
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# ============================================================
# Doğu Anadolu İlleri İçin Optimize Edilmiş Fiyat Aralıkları
# ============================================================
EAST_REGION_BRACKETS = [
    (0, 12000),
    (12001, 15000),
    (15001, 18000),
    (18001, 22000),
    (22001, 28000),
    (28001, 35000),
    (35001, 9999999),
]

# Türkiye'deki büyük şehirler - bu şehirlerden gelen ilanlar filtrelenir
BLACKLIST_CITIES = [
    'istanbul', 'ankara', 'izmir', 'bursa', 'antalya', 'adana',
    'konya', 'kocaeli', 'mersin', 'aydin', 'manisa', 'samsun',
    'gaziantep', 'eskisehir', 'tekirdag', 'trabzon', 'malatya',
    'kayseri', 'erzurum', 'diyarbakir', 'sanliurfa', 'mardin',
    'batman', 'siirt', 'sirnak', 'elazig', 'tunceli', 'bingol',
    'agri', 'igdir', 'kars', 'ardahan', 'erzincan', 'bayburt',
    'rize', 'artvin', 'giresun', 'ordu', 'sinop', 'kastamonu',
    'zonguldak', 'bartin', 'karabuk', 'bolu', 'duzce', 'sakarya',
    'yalova', 'canakkale', 'balikesir', 'kutahya', 'afyonkarahisar',
    'usak', 'denizli', 'mugla', 'isparta', 'burdur', 'konya',
    'karaman', 'nigde', 'aksaray', 'nevsehir', 'kirsehir', 'yozgat',
    'corum', 'amasya', 'tokat', 'sivas', 'kahramanmaras', 'osmaniye',
    'hatay', 'adiyaman', 'kilis', 'urfa', 'gumushane', 'kirklareli',
    'edirne', 'cerkezkoy', 'catalca', 'silivri', 'pendik', 'kartal',
    'maltepe', 'kadikoy', 'uskudar', 'besiktas', 'sisli', 'beyoglu',
    'fatih', 'eyupsultan', 'kagithane', 'sariyer', 'buyukcekmece',
    'kucukcekmece', 'esenyurt', 'bagcilar', 'bahcelievler', 'bakirkoy',
    'zeytinburnu', 'gungoren', 'esenler', 'sultangazi', 'gaziosmanpasa',
    'arnavutkoy', 'basaksehir', 'avcilar', 'beylikduzu', 'cerkezkoy',
    'golcuk', 'izmit', 'gebze', 'kusadasi', 'bodrum', 'fethiye',
    'alanya', 'side', 'belek', 'kas', 'marmaris', 'cesme', 'kusadasi'
]

CITIES = {
    'van': {
        'name': 'Van',
        'brackets': EAST_REGION_BRACKETS,
        'valid_districts': [
            'van', 'tuşba', 'ipekyolu', 'edremit', 'erciş', 'gevaş',
            'gürpınar', 'muradiye', 'özalp', 'başkale', 'çatak',
            'çaldıran', 'saray', 'bahçesaray', 'merkez'
        ]
    },
    'bitlis': {
        'name': 'Bitlis',
        'brackets': EAST_REGION_BRACKETS,
        'valid_districts': [
            'bitlis', 'adilcevaz', 'ahlat', 'güroymak', 'hizan',
            'mutki', 'tatvan', 'merkez'
        ]
    },
    'mus': {
        'name': 'Muş',
        'brackets': EAST_REGION_BRACKETS,
        'valid_districts': [
            'muş', 'bulanık', 'hasköy', 'korkut', 'malazgirt',
            'varto', 'merkez'
        ]
    },
    'hakkari': {
        'name': 'Hakkari',
        'brackets': EAST_REGION_BRACKETS,
        'valid_districts': [
            'hakkari', 'yüksekova', 'şemdinli', 'çukurca',
            'derecik', 'merkez'
        ]
    }
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/Tum_Ilanlar/"))

_profile_counter = 0


def normalize_text(text):
    """Türkçe karakterleri normalize eder, küçük harfe çevirir."""
    text = text.lower()
    replacements = {
        'ı': 'i', 'İ': 'i', 'ğ': 'g', 'Ğ': 'g',
        'ü': 'u', 'Ü': 'u', 'ş': 's', 'Ş': 's',
        'ö': 'o', 'Ö': 'o', 'ç': 'c', 'Ç': 'c'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def is_valid_listing(district_text, valid_districts):
    """
    İki katmanlı filtre:
    1. Kara liste kontrolü - büyük şehirlerden gelen ilanları atar
    2. Beyaz liste kontrolü - sadece geçerli ilçeleri kabul eder
    """
    district_normalized = normalize_text(district_text)

    # Katman 1: Kara liste - başka büyük şehirlerden geliyorsa at
    for blacklisted in BLACKLIST_CITIES:
        if blacklisted in district_normalized:
            return False

    # Katman 2: Beyaz liste - geçerli ilçelerden biri değilse at
    if valid_districts:
        for valid in valid_districts:
            if normalize_text(valid) in district_normalized:
                return True
        return False

    return True


def setup_driver():
    global _profile_counter
    _profile_counter += 1

    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, f"SeleniumProfile_{_profile_counter}")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')

    try:
        driver = uc.Chrome(options=options, version_main=145)
    except Exception as e:
        print(f"⚠️ Versiyon hatası: {e}. Otomatik mod deneniyor...")
        driver = uc.Chrome(options=options)

    print(f"🚀 Chrome instance #{_profile_counter} başlatıldı. (Görünür Mod)")
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except:
        pass
    print("🔒 Chrome kapatıldı.")


def save_to_csv_incremental(data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    file_path = os.path.join(DATA_BASE_DIR, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["City", "District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
    print(f"✅ {len(data_batch)} kayıt '{today_str}.csv' dosyasına eklendi.")


def scrape_city(driver, city_url_name, city_display_name, brackets, valid_districts=None):
    print(f"\n{'=' * 50}")
    print(f"ŞEHİR BAŞLATILDI: {city_display_name.upper()}")
    print(f"{'=' * 50}")

    total_saved = 0
    total_skipped = 0

    for min_price, max_price in brackets:
        print(f"\n>>> Aralık: {min_price} - {max_price} TL")
        page_num = 1
        url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )

        driver.get(url)
        time.sleep(random.uniform(6, 9))

        while True:
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                if "giriş yap" in page_source.lower() or "captcha" in page_source.lower():
                    print("🛑 Bot korumasına takıldık! Lütfen tarayıcıda manuel işlemi tamamla...")
                    time.sleep(15)
                    continue
                else:
                    print(f"  Bu aralıkta (Sayfa {page_num}) ilan bulunamadı.")
                    break

            print(f"  Sayfa {page_num} taranıyor... ({len(listings)} ilan bulundu)")
            bracket_data = []

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    # Filtre kontrolü
                    if not is_valid_listing(district, valid_districts):
                        print(f"  ⛔ Atlandı → {district}")
                        total_skipped += 1
                        continue

                    if price != "N/A":
                        bracket_data.append({
                            "City": city_display_name,
                            "District": district,
                            "Rooms": rooms,
                            "Price": price
                        })

                except Exception as e:
                    print(f"  ❌ Satır parse hatası: {e}")
                    continue

            if bracket_data:
                save_to_csv_incremental(bracket_data)
                total_saved += len(bracket_data)

            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                time.sleep(random.uniform(4, 7))
            else:
                break

    print(f"\n📊 {city_display_name} TAMAMLANDI")
    print(f"   ✅ Kaydedilen: {total_saved} ilan")
    print(f"   ⛔ Atlanan:    {total_skipped} ilan (yanlış şehir)")

    return driver


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            try:
                shutil.rmtree(os.path.join(SCRIPT_DIR, item))
            except:
                pass


def main():
    print("🏠 Sahibinden.com Kiralık İlan Scraper Başlatılıyor...")
    print(f"📁 Veri klasörü: {DATA_BASE_DIR}\n")

    driver = setup_driver()

    try:
        for city_key, city_info in CITIES.items():
            driver = scrape_city(
                driver,
                city_url_name=city_key,
                city_display_name=city_info['name'],
                brackets=city_info['brackets'],
                valid_districts=city_info.get('valid_districts')
            )
            print(f"\n--- {city_info['name']} bitti, sonraki şehre geçiliyor... ---")
            time.sleep(random.uniform(10, 15))

    finally:
        close_driver(driver)
        cleanup_profiles()
        print("\n🎉 Tüm şehirler tamamlandı!")


if __name__ == "__main__":
    main()