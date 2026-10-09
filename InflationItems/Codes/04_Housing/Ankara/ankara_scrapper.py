import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# Ankara'nın tüm ilçeleri - sahibinden.com URL formatı
CITIES = {
    "ankara-akyurt": "Ankara_Akyurt",
    "ankara-altindag": "Ankara_Altindag",
    "ankara-ayas": "Ankara_Ayas",
    "ankara-bala": "Ankara_Bala",
    "ankara-beypazari": "Ankara_Beypazari",
    "ankara-camlidere": "Ankara_Camlidere",
    "ankara-cankaya": "Ankara_Cankaya",
    "ankara-cubuk": "Ankara_Cubuk",
    "ankara-elmadag": "Ankara_Elmadag",
    "ankara-etimesgut": "Ankara_Etimesgut",
    "ankara-evren": "Ankara_Evren",
    "ankara-golbasi": "Ankara_Golbasi",
    "ankara-gudul": "Ankara_Gudul",
    "ankara-haymana": "Ankara_Haymana",
    "ankara-kahramankazan": "Ankara_Kahramankazan",
    "ankara-kalecik": "Ankara_Kalecik",
    "ankara-kecioren": "Ankara_Kecioren",
    "ankara-kizilcahamam": "Ankara_Kizilcahamam",
    "ankara-mamak": "Ankara_Mamak",
    "ankara-nallihan": "Ankara_Nallihan",
    "ankara-polatli": "Ankara_Polatli",
    "ankara-pursaklar": "Ankara_Pursaklar",
    "ankara-sereflikochishar": "Ankara_Sereflikochisar",
    "ankara-sincan": "Ankara_Sincan",
    "ankara-yenimahalle": "Ankara_Yenimahalle",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Desktop'a kaydet - izin sorunu yaşamamak için
DATA_BASE_DIR = os.path.join(
    os.path.expanduser("~"), "Desktop", "Datas", "HousesRent", "Ankara"
)


def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def scrape_city(driver, city_url_name, folder_name):
    url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50"

    print(f"\nLoading {url}...")
    driver.get(url)

    all_scraped_data = []
    page_num = 1

    while True:
        time.sleep(2.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
        room_index = resolve_rooms_index(soup)

        # CAPTCHA / LOGIN check
        if not listings:
            print("\n" + "=" * 50)
            print("ACTION REQUIRED: No listings found.")
            print("Likely CAPTCHA or login page appeared.")
            print("1. Check the Chrome window and solve CAPTCHA or log in.")
            print("2. Wait until listings appear.")
            print(f"Current URL: {driver.current_url}")
            print("=" * 50)
            input("After you can see listings, press ENTER here...")

            max_checks = 10
            for attempt in range(1, max_checks + 1):
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
                if listings:
                    break
                print(f"Still no listings (check {attempt}/{max_checks}). Refreshing page...")
                driver.refresh()

            if not listings:
                print(f"Still no listings for {folder_name}. Skipping.")
                break

        print(f"Scraping {folder_name} page {page_num} (50 per page)...")

        for row in listings:
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                price_raw = price_elem.text.strip() if price_elem else "N/A"
                price = normalize_price(price_raw)

                location_elem = row.select_one(".searchResultsLocationValue")
                district = (
                    location_elem.text.strip().replace("\n", " ")
                    if location_elem
                    else "N/A"
                )

                attributes = row.select(".searchResultsAttributeValue")
                rooms = extract_rooms(attributes, room_index)

                if price is not None and district != "N/A":
                    all_scraped_data.append(
                        {"District": district, "Rooms": rooms, "Price": price}
                    )
            except Exception as exc:
                print(f"Row parse error: {exc}")
                continue

        # Sonraki sayfa
        next_button = soup.find("a", title="Sonraki")
        if next_button and "href" in next_button.attrs:
            next_url = "https://www.sahibinden.com" + next_button["href"]
            driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(2, 4))
        else:
            print(f"Finished all pages for {folder_name}.")
            break

    if all_scraped_data:
        save_to_csv(folder_name, all_scraped_data)
    else:
        print(f"No data found for {folder_name}, skipping save.")


def resolve_rooms_index(soup):
    headers = [
        th.get_text(strip=True)
        for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")
    ]
    for idx, header in enumerate(headers):
        header_norm = header.lower().replace("ı", "i")
        if "oda" in header_norm:
            return idx
    return None


def extract_rooms(attributes, room_index):
    if room_index is not None and len(attributes) > room_index:
        return attributes[room_index].text.strip()
    if len(attributes) > 1:
        return attributes[1].text.strip()
    if len(attributes) == 1:
        return attributes[0].text.strip()
    return "N/A"


def save_to_csv(folder_name, data):
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{today_str}.csv")

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        writer.writeheader()
        writer.writerows(data)

    print(f"✓ Saved {len(data)} records to {file_path}")


def normalize_price(price_text):
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower()
    cleaned = cleaned.replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        if "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) > 1 and all(part.isdigit() for part in parts):
                if all(len(part) == 3 for part in parts[1:]):
                    cleaned = "".join(parts)
    try:
        return float(cleaned)
    except ValueError:
        return None


def main():
    driver = setup_driver()
    try:
        total = len(CITIES)
        for i, (city_url_name, folder_name) in enumerate(CITIES.items(), 1):
            print(f"\n{'='*50}")
            print(f"[{i}/{total}] Scraping {folder_name}...")
            print(f"{'='*50}")
            scrape_city(driver, city_url_name, folder_name)
            # İlçeler arası bekleme - ban yememek için
            wait = random.uniform(5, 10)
            print(f"Waiting {wait:.1f}s before next district...")
            time.sleep(wait)
    finally:
        driver.quit()
        print("\nAll done!")


if __name__ == "__main__":
    main()