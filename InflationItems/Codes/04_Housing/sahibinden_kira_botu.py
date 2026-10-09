# -*- coding: utf-8 -*-
"""
Created on Sun Mar  1 09:50:56 2026

@author: orenl
"""

import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# --- YAPILANDIRMA ---
CITIES = {
    "eskisehir-kiralik": "Eskisehir",
    "bolu": "Bolu",
    "bartin": "Bartin",
    "zonguldak": "Zonguldak",
}

# Verilerin kaydedileceği ana klasör (GitHub'da kolay erişim için mevcut dizin)
DATA_BASE_DIR = "Guncel_Veriler"


def setup_driver():
    options = uc.ChromeOptions()
    # Bilgisayarında test ederken ilk başta headless (arka plan) modunu kapatabilirsin 
    # (Hata alıp almadığını görmek için başına # koydum)
    # options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # version_main=145 ekleyerek uyumsuzluğu gideriyoruz
    driver = uc.Chrome(options=options, version_main=145) 
    return driver

def normalize_price(price_text):
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned: return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            cleaned = "".join(parts)
    try:
        return float(cleaned)
    except:
        return None

def resolve_rooms_index(soup):
    headers = [th.get_text(strip=True) for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("ı", "i"):
            return idx
    return None

def extract_rooms(attributes, room_index):
    if room_index is not None and len(attributes) > room_index:
        return attributes[room_index].text.strip()
    return "N/A"

def save_to_csv(city_folder, data):
    today_str = datetime.now().strftime("%Y-%m-%d")
    # Klasör yapısı: Guncel_Veriler/Eskisehir/
    target_dir = os.path.join(DATA_BASE_DIR, city_folder)
    os.makedirs(target_dir, exist_ok=True)

    # Dosya adı: Eskisehir_2024-05-20.csv
    file_name = f"{city_folder}_{today_str}.csv"
    file_path = os.path.join(target_dir, file_name)

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ Kaydedildi: {file_path}")

def scrape_city(driver, city_url_name, folder_name):
    url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50"
    print(f"\n--- {folder_name} Taranıyor... ---")
    driver.get(url)
    time.sleep(5) # Sayfanın yüklenmesi için bekleme

    all_data = []
    soup = BeautifulSoup(driver.page_source, "html.parser")
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    
    if not listings:
        print(f"⚠️ {folder_name} için veri bulunamadı. (Engel/Captcha olabilir)")
        return

    room_index = resolve_rooms_index(soup)

    for row in listings:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price = normalize_price(price_elem.text.strip()) if price_elem else None
            
            loc_elem = row.select_one(".searchResultsLocationValue")
            district = loc_elem.text.strip().replace("\n", " ") if loc_elem else "N/A"
            
            attrs = row.select(".searchResultsAttributeValue")
            rooms = extract_rooms(attrs, room_index)

            if price:
                all_data.append({"District": district, "Rooms": rooms, "Price": price})
        except:
            continue

    if all_data:
        save_to_csv(folder_name, all_data)

def main():
    driver = setup_driver()
    try:
        for url_name, folder_name in CITIES.items():
            scrape_city(driver, url_name, folder_name)
            time.sleep(random.uniform(5, 10)) # Ban yememek için bekleme
    finally:
        driver.quit()

if __name__ == "__main__":
    main()