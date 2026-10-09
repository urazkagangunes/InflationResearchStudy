import os
import csv
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# User provided categories
CATEGORIES = [
    "https://nalburtek.com/hirdavat-ve-nalbur",
    "https://nalburtek.com/goz-koruyucular",
    "https://nalburtek.com/yapi-market",
    "https://nalburtek.com/el-aletleri",
    "https://nalburtek.com/silikon-mastik-kopuk-cesitleri"
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "Datas", "Nalburtek")

def setup_driver():
    options = uc.ChromeOptions()
    # Use a profile to avoid detection and maintain session if needed
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile_Nalburtek")
    options.add_argument(f"--user-data-dir={profile_path}")
    # Based on previous session, version 145 was used
    driver = uc.Chrome(options=options, version_main=145)
    return driver

def normalize_price(price_text):
    if not price_text:
        return None
    # Extract number and handle Turkish currency formatting (1.234,56 -> 1234.56)
    cleaned = re.sub(r"[^\d,\.]", "", price_text)
    if not cleaned:
        return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None

def scrape_category(driver, category_url):
    all_products = []
    page_num = 1
    
    print(f"\n[Category] Starting: {category_url}")
    
    while True:
        target_url = f"{category_url}?p={page_num}" if page_num > 1 else category_url
        print(f"  Scraping Page {page_num}: {target_url}")
        
        driver.get(target_url)
        time.sleep(random.uniform(3, 5)) # Wait for load
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Check for products
        product_items = soup.select("li.product")
        if not product_items:
            print(f"    No products found on page {page_num}. Ending category.")
            break
            
        for item in product_items:
            try:
                # Name & Link
                title_elem = item.select_one(".woocommerce-LoopProduct-link-title span")
                link_elem = item.select_one("a.woocommerce-LoopProduct-link-title")
                name = title_elem.text.strip() if title_elem else "N/A"
                url = link_elem["href"] if link_elem else "N/A"
                
                # Brand (often found in attributes or text patterns)
                # In standard themes, brand might be elsewhere, but we'll try to find it
                brand = "N/A"
                brand_elem = item.select_one(".marka-line a") # Educated guess based on common themes
                if brand_elem:
                    brand = brand_elem.text.strip()
                
                # Price
                price_container = item.select_one(".price")
                sale_price = "N/A"
                reg_price = "N/A"
                
                if price_container:
                    ins_elem = price_container.select_one("ins .woocommerce-Price-amount")
                    del_elem = price_container.select_one("del .woocommerce-Price-amount")
                    
                    if ins_elem:
                        sale_price = normalize_price(ins_elem.text)
                        if del_elem:
                            reg_price = normalize_price(del_elem.text)
                    else:
                        amount_elem = price_container.select_one(".woocommerce-Price-amount")
                        if amount_elem:
                            sale_price = normalize_price(amount_elem.text)
                            reg_price = sale_price

                # Stok Kodu
                stok_kodu = "N/A"
                stok_elem = item.get_text().split("Stok Kodu :")
                if len(stok_elem) > 1:
                    stok_kodu = stok_elem[1].split("\n")[0].strip()

                all_products.append({
                    "Name": name,
                    "Brand": brand,
                    "SalePrice": sale_price,
                    "RegularPrice": reg_price,
                    "StockCode": stok_kodu,
                    "URL": url,
                    "CategoryURL": category_url
                })
            except Exception as e:
                print(f"    Error parsing product: {e}")
                continue

        # Check for Next Page
        # Pagination usually has a 'next' link or specific ul.page-numbers
        next_page = soup.select_one("a.next.page-numbers")
        if next_page:
            page_num += 1
        else:
            # Fallback check: check if there's a link for page_num + 1
            if soup.find("a", string=str(page_num + 1)):
                page_num += 1
            else:
                print(f"    No more pages found for this category.")
                break
                
    return all_products

def save_to_csv(data):
    if not data:
        print("No data to save.")
        return
        
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(DATA_BASE_DIR, f"Nalburtek_Products_{today_str}.csv")
    
    fieldnames = ["Name", "Brand", "SalePrice", "RegularPrice", "StockCode", "URL", "CategoryURL"]
    
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        
    print(f"\n✓ Saved {len(data)} products to {file_path}")

def main():
    driver = setup_driver()
    all_scraped_data = []
    
    try:
        for cat_url in CATEGORIES:
            try:
                cat_data = scrape_category(driver, cat_url)
                all_scraped_data.extend(cat_data)
            except Exception as e:
                print(f"Error scraping category {cat_url}: {e}")
                
        save_to_csv(all_scraped_data)
    finally:
        driver.quit()
        print("\nScraping complete!")

if __name__ == "__main__":
    main()
