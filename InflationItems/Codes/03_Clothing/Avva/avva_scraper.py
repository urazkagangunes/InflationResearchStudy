import os
import time
import random
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 1. Configuration & Paths
CATEGORIES = [
    "https://www.avva.com.tr/erkek-ev-ve-ic-giyim",
    "https://www.avva.com.tr/erkek-canta-valiz",
    "https://www.avva.com.tr/erkek-saat",
    "https://www.avva.com.tr/erkek-aksesuar",
    "https://www.avva.com.tr/erkek-sort",
    "https://www.avva.com.tr/erkek-ayakkabi",
    "https://www.avva.com.tr/erkek-esofman-alti",
    "https://www.avva.com.tr/erkek-ceket",
    "https://www.avva.com.tr/takim-elbise",
    "https://www.avva.com.tr/erkek-esofman-takimi",
    "https://www.avva.com.tr/erkek-kazak",
    "https://www.avva.com.tr/polar",
    "https://www.avva.com.tr/erkek-sweatshirt",
    "https://www.avva.com.tr/erkek-pantolon",
    "https://www.avva.com.tr/erkek-triko-t-shirt",
    "https://www.avva.com.tr/erkek-t-shirt",
    "https://www.avva.com.tr/erkek-gomlek/gomlek-ceket",
    "https://www.avva.com.tr/erkek-mont"
]

DATA_DIR = "Datas/ClothingStores/Avva"
os.makedirs(DATA_DIR, exist_ok=True)
current_date = datetime.now().strftime("%Y-%m-%d")
file_path = os.path.join(DATA_DIR, f"avva_{current_date}.csv")

def scrape_avva():
    # Initialize Undetected Chromedriver
    options = uc.ChromeOptions()
    options.add_argument("--headless") # Run without window for automation
    driver = uc.Chrome(options=options)
    
    all_products = []

    try:
        for base_url in CATEGORIES:
            category_name = base_url.split('/')[-1]
            print(f"--- Scraping Category: {category_name} ---")
            
            # Scrape first 3 pages (Adjust range as needed)
            for page in range(1, 4):
                url = f"{base_url}?pg={page}"
                driver.get(url)
                
                # Wait for products to load (Update selector based on site inspection)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_for_all_elements_located((By.CLASS_NAME, "product-item"))
                    )
                except:
                    print(f"No more products or timeout on page {page}")
                    break

                # Extract items
                items = driver.find_elements(By.CLASS_NAME, "product-item")
                for item in items:
                    try:
                        name = item.find_element(By.CLASS_NAME, "product-name").text.strip()
                        price = item.find_element(By.CLASS_NAME, "product-price").text.strip()
                        
                        all_products.append({
                            "Date": current_date,
                            "Category": category_name,
                            "Product Name": name,
                            "Price": price
                        })
                    except Exception as e:
                        continue
                
                print(f"Finished page {page}")
                time.sleep(random.uniform(2, 5)) # Anti-ban delay

    finally:
        driver.quit()

    # Save to CSV
    df = pd.DataFrame(all_products)
    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"Successfully saved data to {file_path}")

if __name__ == "__main__":
    scrape_avva()
