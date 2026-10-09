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
except ImportError:
    print("undetected-chromedriver paketi bulunamadi!")
    print("pip install undetected-chromedriver beautifulsoup4 setuptools")
    sys.exit(1)

CHROME_VERSION = 145

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.join(SCRIPT_DIR, "Datas", "Ereyon")

ANA_KATEGORILER = [
    ("Kucuk Ev Aletleri",  "https://www.ereyon.com.tr/kucuk-ev-aletleri-8"),
    ("Petshop",            "https://www.ereyon.com.tr/petshop-151"),
    ("Bahce Yapi Market",  "https://www.ereyon.com.tr/yapi-market-bahce"),
    ("Kisisel Bakim",      "https://www.ereyon.com.tr/kisisel-bakim-kozmetik"),
    ("Isitma Barbeku",     "https://www.ereyon.com.tr/isitma-ve-barbekuler"),
    ("Ev Yasam Mobilya",   "https://www.ereyon.com.tr/ev-yasam-mobilya"),
    ("Anne Bebek Oyuncak", "https://www.ereyon.com.tr/anne-bebek-oyuncak-73"),
    ("Diger Kategoriler",  "https://www.ereyon.com.tr/diger-kategoriler-"),
    ("Oto Aksesuar",       "https://www.ereyon.com.tr/oto-aksesuar-206"),
    ("Kampanyalar",        "https://www.ereyon.com.tr/kampanyalar"),
]

seen_products = set()


def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile_Ereyon")
    options.add_argument("--user-data-dir=" + profile_path)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument('--log-level=3')
    driver = uc.Chrome(options=options, version_main=CHROME_VERSION)
    print("Chrome basladi.")
    return driver


def get_output_path():
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    return os.path.join(DATA_BASE_DIR, today_str + ".csv")


def save_batch(batch, file_path):
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=["Kategori", "Urun_Adi", "Fiyat"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(batch)


def scroll_until_stable(driver):
    """Urun sayisi 3 tur ust uste degismeyene kadar scroll et."""
    last_count = 0
    stable_rounds = 0
    while stable_rounds < 3:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = len(soup.select("div.productDetail"))
        print("    Yuklenen urun: " + str(count))
        if count == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_count = count


def parse_products(driver, kategori):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    cards = soup.select("div.productDetail")
    batch = []

    for card in cards:
        try:
            name_div = card.select_one("div.productName")
            name = name_div.get_text(strip=True) if name_div else None
            if not name:
                continue

            price_div = card.select_one("div.productPrice")
            if price_div:
                new_price = price_div.select_one("span.newPrice, ins, .discountedPrice")
                price = new_price.get_text(strip=True) if new_price else price_div.get_text(strip=True).split()[0]
            else:
                price = "N/A"

            key = name + "|" + price
            if key in seen_products:
                continue
            seen_products.add(key)

            batch.append({
                "Kategori": kategori,
                "Urun_Adi": name,
                "Fiyat": price
            })

        except Exception:
            continue

    return batch, soup


def get_max_page(soup):
    max_page = 1
    for a in soup.select("a[href*='sayfa=']"):
        href = a.get("href", "")
        try:
            p = int(href.split("sayfa=")[-1].split("&")[0])
            if p > max_page:
                max_page = p
        except:
            pass
    return max_page


def scrape_category(driver, kategori, base_url, file_path):
    print("\n" + "=" * 55)
    print("KATEGORI: " + kategori)
    print("=" * 55)

    total = 0
    page = 1

    while True:
        url = base_url if page == 1 else base_url + "?sayfa=" + str(page)
        print("  Sayfa " + str(page) + ": " + url)

        driver.get(url)
        time.sleep(random.uniform(3, 5))

        scroll_until_stable(driver)

        batch, soup = parse_products(driver, kategori)

        if not batch:
            print("  Urun bulunamadi, kategori bitti.")
            break

        save_batch(batch, file_path)
        total += len(batch)
        print("  " + str(len(batch)) + " yeni urun | toplam: " + str(total))

        max_page = get_max_page(soup)
        print("  Toplam sayfa: " + str(max_page))

        if page >= max_page:
            print("  Son sayfa.")
            break

        page += 1
        time.sleep(random.uniform(2, 4))

    return total


def cleanup():
    p = os.path.join(SCRIPT_DIR, "SeleniumProfile_Ereyon")
    if os.path.exists(p):
        try:
            shutil.rmtree(p)
        except:
            pass


def main():
    print("=" * 55)
    print("Ereyon.com.tr Scraper")
    print("=" * 55)
    print("Cikti: " + DATA_BASE_DIR)

    file_path = get_output_path()
    driver = setup_driver()

    try:
        for kategori, url in ANA_KATEGORILER:
            scrape_category(driver, kategori, url, file_path)
            time.sleep(random.uniform(4, 7))

    except KeyboardInterrupt:
        print("\nDurduruldu.")

    finally:
        driver.quit()
        cleanup()
        print("\n" + "=" * 55)
        print("TAMAMLANDI!")
        print("Toplam benzersiz urun: " + str(len(seen_products)))
        print("Dosya: " + file_path)
        print("=" * 55)


if __name__ == "__main__":
    main()
