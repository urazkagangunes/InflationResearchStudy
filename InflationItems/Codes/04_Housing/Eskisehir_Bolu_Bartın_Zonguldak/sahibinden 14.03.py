# -*- coding: utf-8 -*-
"""
Created on Sat Mar 14 13:32:57 2026

@author: orenl
"""

# -*- coding: utf-8 -*-
"""
Updated Script for Sahibinden Scraping
- Automatically handles login redirects by clearing cookies, opening a new tab, and resuming.
- Saves data to a separate CSV file for EACH city.
- Extracts Unique Listing IDs to track price changes.
"""

import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# Yeni Şehirler ve İlçeleri
CITIES_DATA = {
    "Eskisehir": {
        "eskisehir-odunpazari": "Eskisehir_Odunpazari",
        "eskisehir-tepebasi": "Eskisehir_Tepebasi",
        "eskisehir-alpu": "Eskisehir_Alpu",
        "eskisehir-beylikova": "Eskisehir_Beylikova",
        "eskisehir-cifteler": "Eskisehir_Cifteler",
        "eskisehir-gunyuzu": "Eskisehir_Gunyuzu",
        "eskisehir-han": "Eskisehir_Han",
        "eskisehir-inonu": "Eskisehir_Inonu",
        "eskisehir-mahmudiye": "Eskisehir_Mahmudiye",
        "eskisehir-mihalalgazi": "Eskisehir_Mihalgazi",
        "eskisehir-mihaliccik": "Eskisehir_Mihaliccik",
        "eskisehir-saricakaya": "Eskisehir_Saricakaya",
        "eskisehir-seyitgazi": "Eskisehir_Seyitgazi",
        "eskisehir-sivrihisar": "Eskisehir_Sivrihisar",
    },
    "Bolu": {
        "bolu-merkez": "Bolu_Merkez",
        "bolu-dortdivan": "Bolu_Dortdivan",
        "bolu-gerede": "Bolu_Gerede",
        "bolu-goynuk": "Bolu_Goynuk",
        "bolu-kibriscik": "Bolu_Kibriscik",
        "bolu-mengen": "Bolu_Mengen",
        "bolu-mudurnu": "Bolu_Mudurnu",
        "bolu-seben": "Bolu_Seben",
        "bolu-yenicaga": "Bolu_Yenicaga",
    },
    "Bartin": {
        "bartin-merkez": "Bartin_Merkez",
        "bartin-amasra": "Bartin_Amasra",
        "bartin-kurucasile": "Bartin_Kurucasile",
        "bartin-ulus": "Bartin_Ulus",
    },
    "Zonguldak": {
        "zonguldak-merkez": "Zonguldak_Merkez",
        "zonguldak-alapli": "Zonguldak_Alapli",
        "zonguldak-caycuma": "Zonguldak_Caycuma",
        "zonguldak-devrek": "Zonguldak_Devrek",
        "zonguldak-eregli": "Zonguldak_Eregli",
        "zonguldak-gokcebey": "Zonguldak_Gokcebey",
        "zonguldak-kilimli": "Zonguldak_Kilimli",
        "zonguldak-kozlu": "Zonguldak_Kozlu",
    }
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Datas", "HousesRent")

def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=145)
    return driver

def human_scroll(driver):
    """Simulates a human scrolling down the page."""
    try:
        total_height = int(driver.execute_script("return document.body.scrollHeight"))
        for i in range(1, total_height, random.randint(300, 600)):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(random.uniform(0.1, 0.4))
    except Exception:
        pass

def append_to_csv(csv_path, data):
    """Appends data to the specific city's CSV file."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    file_exists = os.path.isfile(csv_path)
    
    with open(csv_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Listing_ID", "City", "District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)

def scrape_city(driver, city_main_name, city_url_name, folder_name, csv_path):
    current_url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50"
    page_num = 1
    bypass_attempts = 0

    while current_url:
        print(f"\nLoading {folder_name} Page {page_num}...")
        driver.get(current_url)
        time.sleep(random.uniform(3.0, 5.0))

        # Check if we got redirected to the login page
        if "giris" in driver.current_url.lower() or "login" in driver.current_url.lower() or "guvenlik" in driver.current_url.lower():
            bypass_attempts += 1
            
            if bypass_attempts > 3:
                print("\n" + "!" * 60)
                print(f"🚨 HARD LIMIT DETECTED! Sahibinden is refusing to show this page to a guest.")
                print("Please log into an account manually in the opened Chrome window.")
                print("!" * 60)
                input("Press ENTER here ONLY AFTER you have successfully logged in...")
                bypass_attempts = 0
                continue # Try loading the page again after they press enter
            
            print(f"\n🚨 Block Detected (Attempt {bypass_attempts}/3). Trying to bypass...")
            print("Clearing cookies and switching to a fresh tab...")
            
            # 1. Clear cookies
            driver.delete_all_cookies()
            # 2. Open a new blank tab
            driver.execute_script("window.open('');")
            # 3. Switch focus to the OLD tab
            driver.switch_to.window(driver.window_handles[0])
            # 4. Close the OLD tab
            driver.close()
            # 5. Switch focus back to the NEW tab
            driver.switch_to.window(driver.window_handles[0])
            
            time.sleep(random.uniform(2.0, 4.0))
            continue # Restart the loop, which will try to driver.get(current_url) again
        
        # If we successfully loaded the page without being blocked, reset the counter
        bypass_attempts = 0
        human_scroll(driver)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
        room_index = resolve_rooms_index(soup)
        page_scraped_data = []

        if not listings:
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
            
            if not listings:
                if "giris" not in driver.current_url.lower():
                    print(f"⚠️ No rental listings found for {folder_name} on this page. Moving on.")
                    break # Genuinely empty page, break the while loop

        for row in listings:
            try:
                listing_id = row.get("data-id", "").strip()
                if not listing_id:
                    continue 

                price_elem = row.select_one(".searchResultsPriceValue")
                price_raw = price_elem.text.strip() if price_elem else "N/A"
                price = normalize_price(price_raw)

                location_elem = row.select_one(".searchResultsLocationValue")
                district = location_elem.text.strip().replace("\n", " ") if location_elem else "N/A"

                attributes = row.select(".searchResultsAttributeValue")
                rooms = extract_rooms(attributes, room_index)

                if price is not None and district != "N/A":
                    page_scraped_data.append({
                        "Listing_ID": listing_id,
                        "City": city_main_name,
                        "District": district, 
                        "Rooms": rooms, 
                        "Price": price
                    })
            except Exception as exc:
                continue

        if page_scraped_data:
            append_to_csv(csv_path, page_scraped_data)
            print(f"✓ Saved {len(page_scraped_data)} records for {folder_name} (Page {page_num}) to {os.path.basename(csv_path)}.")

        # Handle Pagination
        next_button = soup.find("a", title="Sonraki")
        if next_button and "href" in next_button.attrs:
            # Update current_url to the next page and loop again
            current_url = "https://www.sahibinden.com" + next_button["href"]
            page_num += 1
            time.sleep(random.uniform(4.0, 7.5)) 
        else:
            # No next button found, we are done with this district
            current_url = None

def resolve_rooms_index(soup):
    headers = [th.get_text(strip=True) for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")]
    for idx, header in enumerate(headers):
        header_norm = header.lower().replace("ı", "i")
        if "oda" in header_norm: return idx
    return None

def extract_rooms(attributes, room_index):
    if room_index is not None and len(attributes) > room_index: return attributes[room_index].text.strip()
    if len(attributes) > 1: return attributes[1].text.strip()
    return "N/A"

def normalize_price(price_text):
    if not price_text or price_text == "N/A": return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned: return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        if "," in cleaned: cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]): cleaned = "".join(parts)
    try: return float(cleaned)
    except: return None

def main():
    driver = setup_driver()
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        for city_main_name, districts in CITIES_DATA.items():
            city_csv_path = os.path.join(DESKTOP_PATH, f"{city_main_name}_{today_str}.csv")
            
            print(f"\n🚀 STARTING CITY: {city_main_name.upper()}")
            print(f"Data for {city_main_name} will be saved to: {city_csv_path}")
            
            for i, (city_url_name, folder_name) in enumerate(districts.items(), 1):
                print(f"\n[{i}/{len(districts)}] Moving to {folder_name}...")
                scrape_city(driver, city_main_name, city_url_name, folder_name, city_csv_path)
                
                wait = random.uniform(8.0, 15.0)
                print(f"Sleeping for {wait:.2f} seconds before next district...")
                time.sleep(wait)
                
    except KeyboardInterrupt:
        print("\nScript manually stopped! Your data up to this point is safely saved in the respective city CSVs.")
    finally:
        driver.quit()
        print("\nAll tasks completed! Check your HousesRent folder for the separate city files.")

if __name__ == "__main__":
    main()