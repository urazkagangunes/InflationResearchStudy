import os
import sys
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup

os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
except ImportError:
    print("Gerekli paketler bulunamadi!")
    print("pip install undetected-chromedriver beautifulsoup4 selenium")
    sys.exit(1)

CUSTOM_OUTPUT_DIR = None
CHROME_VERSION = 145

GENERAL_BRACKETS = [
    (0, 12000),
    (12001, 15000),
    (15001, 18000),
    (18001, 22000),
    (22001, 28000),
    (28001, 35000),
    (35001, 9999999),
]

CITIES = {
    'isparta': 'Isparta',
    'burdur': 'Burdur',
    'igdir': 'Igdir',
    'agri': 'Agri',
    'ardahan': 'Ardahan',
    'batman': 'Batman',
    'siirt': 'Siirt',
    'sirnak': 'Sirnak',
    'kastamonu': 'Kastamonu',
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if CUSTOM_OUTPUT_DIR:
    DATA_BASE_DIR = CUSTOM_OUTPUT_DIR
else:
    DATA_BASE_DIR = os.path.join(
        SCRIPT_DIR,
        "Datas", "HouseRent",
        "Isparta_Burdur_Igdir_Agri_Ardahan_Batman_Siirt_Sirnak_Kastamonu"
    )

_profile_counter = 0


def setup_driver():
    global _profile_counter
    _profile_counter += 1
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile_" + str(_profile_counter))
    options.add_argument("--user-data-dir=" + profile_path)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument('--log-level=3')
    try:
        if CHROME_VERSION:
            driver = uc.Chrome(options=options, version_main=CHROME_VERSION)
        else:
            driver = uc.Chrome(options=options)
    except Exception as e:
        print("Chrome baslatma hatasi: " + str(e))
        raise
    print("Chrome basladi.")
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    print("Chrome kapatildi.")


def is_bot_page(page_source, soup):
    blocked_keywords = [
        "tarayicinizi kontrol ediyoruz",
        "tarayıcınızı kontrol ediyoruz",
        "baglantiniz kontrol ediliyor",
        "bağlantınız kontrol ediliyor",
        "basili tutun",
        "basılı tutun",
    ]
    has_keyword = any(kw in page_source.lower() for kw in blocked_keywords)
    has_listings = bool(soup.select("#searchResultsTable tbody tr.searchResultsItem"))
    return has_keyword and not has_listings


def is_login_page(page_source):
    login_keywords = [
        "sign in with email",
        "sign in with google",
        "log in to sahibinden",
    ]
    return any(kw in page_source.lower() for kw in login_keywords)


def wait_for_login(driver, url=None):
    print("\n" + "!" * 50)
    print("  LOGIN GEREKIYOR! Lutfen tarayicida giris yapin.")
    print("  Giris yaptiktan sonra scraper otomatik devam edecek.")
    print("!" * 50)
    while True:
        time.sleep(3)
        if not is_login_page(driver.page_source):
            print("  Giris yapildi, devam ediliyor...")
            time.sleep(2)
            if url:
                driver.get(url)
                time.sleep(random.uniform(4, 7))
            return


def handle_bot_protection(driver, max_attempts=5):
    debug_path = os.path.join(SCRIPT_DIR, "bot_page_debug.html")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"  DEBUG: Bot sayfasi HTML kaydedildi -> {debug_path}")

    if is_login_page(driver.page_source):
        wait_for_login(driver)
        return "ok"

    attempt = 0
    while attempt < max_attempts:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        if not is_bot_page(page_source, soup):
            return "ok"

        attempt += 1
        is_hold_type = "basili tutun" in page_source.lower() or "basılı tutun" in page_source.lower()

        if is_hold_type:
            print(f"  [BASILI TUT] Bot korumasi tespit edildi (Deneme {attempt}/{max_attempts}).")
            print("  15 saniye bekleniyor...")
            time.sleep(15)

            try:
                btn = None
                selectors = [
                    "button",
                    "div[class*='button']",
                    "div[class*='btn']",
                    "div[class*='hold']",
                    "div[class*='press']",
                    "[class*='challenge']",
                    "[class*='verify']",
                ]
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            if el.is_displayed() and el.size['width'] > 50:
                                btn = el
                                break
                        if btn:
                            break
                    except Exception:
                        continue

                if not btn:
                    btn = driver.find_element(By.TAG_NAME, "body")

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(1)

                actions = ActionChains(driver)
                actions.move_to_element(btn)
                actions.pause(0.5)
                actions.click_and_hold(btn)
                actions.pause(6)
                actions.release(btn)
                actions.perform()

                print("  Butona 6 sn basildi ve birakildi.")

            except Exception as e:
                print(f"  Hold hatasi: {e}")
                try:
                    driver.execute_script("""
                        var els = document.querySelectorAll('button, div[class*="btn"], div[class*="hold"], div[class*="press"]');
                        var btn = null;
                        for (var i = 0; i < els.length; i++) {
                            if (els[i].offsetWidth > 50) { btn = els[i]; break; }
                        }
                        if (!btn) btn = document.body;
                        btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    """)
                    time.sleep(6)
                    driver.execute_script("""
                        var els = document.querySelectorAll('button, div[class*="btn"], div[class*="hold"], div[class*="press"]');
                        var btn = null;
                        for (var i = 0; i < els.length; i++) {
                            if (els[i].offsetWidth > 50) { btn = els[i]; break; }
                        }
                        if (!btn) btn = document.body;
                        btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                        btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    """)
                    print("  JavaScript mousedown/mouseup uygulandi.")
                except Exception as e2:
                    print(f"  JavaScript hold hatasi: {e2}")

        else:
            print(f"  [DEVAM ET] Bot korumasi tespit edildi (Deneme {attempt}/{max_attempts}).")
            print("  15 saniye bekleniyor...")
            time.sleep(15)

            clicked = False
            try:
                btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "btn-continue"))
                )
                btn.click()
                clicked = True
                print("  'Devam Et' butonuna tiklandi (ID ile).")
            except Exception:
                pass

            if not clicked:
                try:
                    driver.execute_script(
                        "document.getElementById('btn-continue').click();"
                    )
                    clicked = True
                    print("  'Devam Et' JS ile tiklandi.")
                except Exception as e:
                    print(f"  Tiklama hatasi: {e}")

            if not clicked:
                print("  'Devam Et' butonu bulunamadi, 5 saniye bekleniyor...")
                time.sleep(5)
                continue

        time.sleep(5)
        new_source = driver.page_source
        new_soup = BeautifulSoup(new_source, 'html.parser')
        if not is_bot_page(new_source, new_soup):
            print("  Bot korumasi asildi!")
            return "ok"
        else:
            print("  Hala bot sayfasindayiz, tekrar deneniyor...")

    print(f"  UYARI: {max_attempts} denemede bot korumasi asilamadi. Bu sayfa duraklatiliyor.")
    return "blocked"


def get_page_with_bot_check(driver, url):
    driver.get(url)
    time.sleep(random.uniform(4, 7))

    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    if is_login_page(page_source):
        wait_for_login(driver, url)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

    if is_bot_page(page_source, soup):
        result = handle_bot_protection(driver)
        if result == "blocked":
            return None, "blocked"
        page_source = driver.page_source

    return page_source, "ok"


def save_to_csv_incremental(data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    file_path = os.path.join(DATA_BASE_DIR, today_str + "_Dailyrents.csv")
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=["City", "District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
    print(str(len(data_batch)) + " kayit eklendi -> " + file_path)


def parse_listings(soup, city_display_name):
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    batch = []
    for row in listings:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price = price_elem.text.strip() if price_elem else "N/A"

            location_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

            attributes = row.select(".searchResultsAttributeValue")
            rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

            if price != "N/A":
                batch.append({
                    "City": city_display_name,
                    "District": district,
                    "Rooms": rooms,
                    "Price": price
                })
        except Exception as e:
            print("  Satir hatasi: " + str(e))
            continue
    return batch


def scrape_city(driver, city_url_name, city_display_name):
    print("\n" + "=" * 50)
    print("SEHIR: " + city_display_name.upper())
    print("=" * 50)

    total_saved = 0

    for min_price, max_price in GENERAL_BRACKETS:
        print("\n>>> Aralik: " + str(min_price) + " - " + str(max_price) + " TL")
        page_num = 1
        url = (
            "https://www.sahibinden.com/kiralik/" + city_url_name +
            "?pagingSize=50&price_min=" + str(min_price) + "&price_max=" + str(max_price)
        )

        page_source, status = get_page_with_bot_check(driver, url)
        if status == "blocked":
            print("  Bu aralik atlaniyor, bir sonraki araliga geciliyor.")
            continue

        while True:
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                print("  Sayfa " + str(page_num) + ": ilan bulunamadi, sonraki araliga geciliyor.")
                break

            print("  Sayfa " + str(page_num) + " -> " + str(len(listings)) + " ilan bulundu")
            batch = parse_listings(soup, city_display_name)

            if batch:
                save_to_csv_incremental(batch)
                total_saved += len(batch)

            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                page_source, status = get_page_with_bot_check(driver, next_url)
                if status == "blocked":
                    print("  Sonraki sayfa bot korumasinda takildi. Bu aralik burada duruyor.")
                    break
                page_num += 1
            else:
                break

    print("\n" + city_display_name + " TAMAMLANDI - Toplam kaydedilen: " + str(total_saved))
    return driver


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            try:
                shutil.rmtree(os.path.join(SCRIPT_DIR, item))
            except Exception:
                pass


def main():
    print("=" * 50)
    print("Sahibinden.com Kiralik Ilan Scraper")
    print("=" * 50)
    print("Cikti klasoru: " + DATA_BASE_DIR)
    print("Sehir sayisi : " + str(len(CITIES)))

    driver = setup_driver()

    try:
        for city_key, city_name in CITIES.items():
            driver = scrape_city(driver, city_key, city_name)
            print("\n--- " + city_name + " bitti, sonraki sehre geciliyor... ---")
            time.sleep(random.uniform(10, 15))

    except KeyboardInterrupt:
        print("\nKullanici tarafindan durduruldu.")

    finally:
        close_driver(driver)
        cleanup_profiles()
        print("\nTum sehirler tamamlandi!")


if __name__ == "__main__":
    main()
