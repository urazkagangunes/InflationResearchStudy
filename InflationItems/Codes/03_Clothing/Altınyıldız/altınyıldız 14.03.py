# -*- coding: utf-8 -*-
"""
Altınyıldız Classics Scraper
"""

import time
import re
import os
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# -------------------------
# 1. FILE SETUP & RESUME LOGIC
# -------------------------
current_date = datetime.now().strftime("%Y-%m-%d")

# Both files now use the current date so they reset on a new day!
CSV_FILE = f"altinyildiz_tum_urunler_{current_date}.csv"
COMPLETED_CATS_FILE = f"tamamlanan_kategoriler_{current_date}.txt"

all_products_dict = {}
completed_categories = set()

# Load already completed categories for TODAY
if os.path.exists(COMPLETED_CATS_FILE):
    with open(COMPLETED_CATS_FILE, "r", encoding="utf-8") as f:
        completed_categories = set(line.strip() for line in f if line.strip())
    print(f"Kaldığı yerden devam ediliyor... {len(completed_categories)} kategori zaten tamamlanmış.")

# Load existing products from TODAY'S CSV
if os.path.exists(CSV_FILE):
    try:
        df_existing = pd.read_csv(CSV_FILE)
        for _, row in df_existing.iterrows():
            cats = set(row['kategori'].split(' | ')) if pd.notna(row['kategori']) else set()
            all_products_dict[row['url']] = {
                "id": str(row.get('id', '')),
                "urun": row['urun'],
                "fiyat": row['fiyat'],
                "kategori": cats,
                "url": row['url']
            }
        print(f"Önceki veriler yüklendi. Veritabanında {len(all_products_dict)} eşsiz ürün bulunuyor.\n")
    except Exception as e:
        print(f"Önceki veriler yüklenirken bir hata oluştu: {e}\n")

def save_current_progress():
    """Converts the dictionary to a DataFrame and safely saves to CSV."""
    data_to_save = []
    for url, p_data in all_products_dict.items():
        row = p_data.copy()
        row['kategori'] = " | ".join(row['kategori'])
        data_to_save.append(row)

    df = pd.DataFrame(data_to_save)
    
    try:
        df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
    except PermissionError:
        print(f"\n⚠️ UYARI: '{CSV_FILE}' şu anda başka bir programda (örn. Excel) açık!")
        print("Lütfen dosyayı kapatın. Veri kaybetmemek için 10 saniye bekleyip tekrar deneyeceğim...")
        time.sleep(10)
        
        try:
            df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
            print("Dosya kapatıldı, başarıyla kaydedildi.")
        except PermissionError:
            backup_file = CSV_FILE.replace(".csv", "_yedek.csv")
            df.to_csv(backup_file, index=False, encoding="utf-8-sig")
            print(f"Dosya hâlâ açık! Veriler geçici olarak '{backup_file}' dosyasına kaydedildi.")

def extract_product_id(url):
    """Extracts the product slug from the URL."""
    try:
        slug = url.rstrip("/").split("/")[-1]
        if slug.endswith("-p"):
            return slug[:-2]
        return slug
    except:
        return "Unknown"

# -------------------------
# 2. SETUP DRIVER
# -------------------------
print("Tarayıcı başlatılıyor...")

options = Options()
options.page_load_strategy = 'eager'

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(45)

base_url = "https://www.altinyildizclassics.com/"
driver.get(base_url)
time.sleep(5)

# -------------------------
# 3. COLLECT CATEGORIES
# -------------------------
links = driver.find_elements(By.TAG_NAME, "a")
categories = set()

for l in links:
    try:
        href = l.get_attribute("href")
        if href and "-c" in href and "altinyildizclassics.com" in href:
            categories.add(href)
    except:
        continue

categories = list(categories)
print("Toplam Kategori sayısı:", len(categories))

# -------------------------
# 4. SCRAPE CATEGORIES
# -------------------------
for cat in categories:
    if cat in completed_categories:
        print(f"\nAtlanıyor (Önceden Tamamlanmış): {cat}")
        continue

    print("\nKategori:", cat)

    page = 1
    seen_in_category = set()

    while True:
        url = cat if page == 1 else f"{cat}{'&' if '?' in cat else '?'}pagenumber={page}"

        # --- RETRY MECHANISM ---
        max_retries = 3
        products = []
        for attempt in range(max_retries):
            try:
                driver.get(url)
                time.sleep(4)
                products = driver.find_elements(By.CLASS_NAME, "ac-pc")
                break 
            except Exception as e:
                print(f"Bağlantı hatası (Deneme {attempt + 1}/{max_retries}). 5 saniye bekleniyor...")
                time.sleep(5)
                if attempt == max_retries - 1:
                    print("Sayfa yüklenemedi. Bu sayfa atlanıyor.")
        # -----------------------

        print(f"Sayfa {page} → {len(products)} ürün")

        if len(products) == 0:
            print("Ürün yok, kategori bitti")
            break

        new_found = 0

        for p in products:
            try:
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")

                if not link or link in seen_in_category:
                    continue

                seen_in_category.add(link)
                new_found += 1

                if link in all_products_dict:
                    all_products_dict[link]["kategori"].add(cat)
                    continue

                name = link.rstrip("/").split("/")[-1]
                product_id = extract_product_id(link)

                price = "NA"
                for selector in [".ac-pc__price", "[class*='price']"]:
                    try:
                        price = p.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if price:
                            break
                    except:
                        pass

                all_products_dict[link] = {
                    "id": product_id,
                    "urun": name,
                    "fiyat": price,
                    "kategori": {cat},
                    "url": link
                }

            except:
                continue

        if new_found == 0:
            print("Yeni ürün gelmedi, kategori bitti")
            break

        try:
            count_text = driver.find_element(By.CLASS_NAME, "product-count").text
            total_products = int(re.findall(r"\d+", count_text)[0])
            if page == 1:
                print("Toplam ürün:", total_products)

            if len(seen_in_category) >= total_products:
                print("Toplam ürün sayısına ulaşıldı")
                break
        except:
            pass

        page += 1

    # -------------------------
    # 5. SAVE AFTER EACH CATEGORY
    # -------------------------
    completed_categories.add(cat)
    
    with open(COMPLETED_CATS_FILE, "a", encoding="utf-8") as f:
        f.write(cat + "\n")

    save_current_progress()
    print(f"Ara Kayıt: {cat} bitti, veriler kaydedildi.")

driver.quit()
print(f"\nScraping Tamamlandı! Toplam çekilen eşsiz ürün: {len(all_products_dict)}")