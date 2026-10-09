"""
Cagri Market Price Scraper
GitHub: InflationResearchStudy/Codes/Markets/Cagri/cagri_scraper.py
Data: InflationResearchStudy/Datas/Markets/Cagri/
"""

import requests
import pandas as pd
import json
import time
from datetime import datetime
from pathlib import Path
import sys

# ========== CONFIGURATION ==========
BASE_API_URL = "https://api.cagri.com/product/product/all/WEB"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://www.cagri.com",
    "referer": "https://www.cagri.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 0.5

# All categories
CATEGORIES = [
    {"name": "Meyve Sebze", "slug": "meyve-sebze"},
    {"name": "Et Tavuk Balık", "slug": "et-tavuk-balik"},
    {"name": "Süt Kahvaltılık", "slug": "sut-kahvaltilik"},
    {"name": "Temel Gıda", "slug": "temel-gida"},
    {"name": "İçecekler", "slug": "icecekler"},
    {"name": "Atıştırmalık", "slug": "atistirmalik"},
    {"name": "Sağlıklı Yaşam", "slug": "saglikli-yasam-urunleri"},
    {"name": "Deterjan Temizlik", "slug": "deterjan-temizlik"},
    {"name": "Kişisel Bakım", "slug": "kisisel-bakim-kozmetik"},
    {"name": "Prezervatif", "slug": "prezervatif"},
    {"name": "Kağıt Ürünleri", "slug": "kagit-urunleri"},
    {"name": "Ev ve Yaşam", "slug": "ev-ve-yasam"},
    {"name": "Bebek Ürünleri", "slug": "bebek-urunleri"},
    {"name": "Evcil Hayvan", "slug": "evcil-hayvan"},
    {"name": "Çağrı Ekstra", "slug": "cagri-ekstra"},
    {"name": "Superfresh Donuk", "slug": "superfresh-donuk"},
    {"name": "Danet Ramazan", "slug": "danet-ile-ramazan-lezzeti"},
]

# ========== DATA PATH ==========
# This will create Datas/Markets/Cagri folder in the same directory as the script
DATA_PATH = Path("Datas/Markets/Cagri")
DATA_PATH.mkdir(parents=True, exist_ok=True)

# ========== FUNCTIONS ==========
def fetch_products(slug, page=1):
    """Fetch products from API"""
    params = {"page": page, "limit": 48, "sort": "id,asc"}
    payload = {
        "brand_ids": [], "category_ids": [], "codes": [], "grammageList": [],
        "literList": [], "pieceList": [], "sizeList": [], "tag_id": 0,
        "slug": slug, "wawlabs": False, "name": "", "groupFilter": True
    }

    try:
        response = requests.post(
            BASE_API_URL, 
            headers=HEADERS, 
            params=params, 
            json=payload, 
            timeout=REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error {slug} page {page}: {response.status_code}")
            return None
    except Exception as e:
        print(f"  Error {slug} page {page}: {e}")
        return None

def scrape_all():
    """Scrape all categories"""
    all_products = []
    scan_time = datetime.now()
    
    print("\n" + "="*50)
    print("CAGRI MARKET SCRAPER STARTED")
    print(f"Date: {scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    for cat in CATEGORIES:
        page = 1
        cat_count = 0
        print(f"\n{cat['name']}...", end="", flush=True)
        
        while True:
            response = fetch_products(cat['slug'], page)
            
            if not response or 'data' not in response or not response['data']:
                break
            
            for item in response['data']:
                # Price
                price = None
                if item.get('selling_price') is not None:
                    price = float(item['selling_price'])
                elif item.get('purchase_price') is not None:
                    price = float(item['purchase_price'])
                
                # URL
                url = None
                if item.get('seo', {}).get('slug'):
                    url = f"https://www.cagri.com/{item['seo']['slug']}"
                
                product = {
                    'category': cat['name'],
                    'product_name': item.get('name', ''),
                    'price_tl': price,
                    'unit': item.get('unit_price_info', ''),
                    'product_code': item.get('code', ''),
                    'product_url': url,
                    'date': scan_time.strftime('%Y-%m-%d'),
                    'time': scan_time.strftime('%H:%M:%S'),
                    'in_stock': 'Yes' if item.get('stock', 0) > 0 else 'No'
                }
                all_products.append(product)
                cat_count += 1
            
            # Pagination
            total_pages = response.get('totalPages', 0)
            if total_pages and page >= total_pages:
                break
                
            page += 1
            time.sleep(SLEEP_BETWEEN_REQUESTS)
        
        print(f" {cat_count} products", flush=True)
    
    print(f"\n{'='*50}")
    print(f"TOTAL: {len(all_products)} products")
    print("="*50)
    
    return all_products

def save_data(products):
    """Save data to CSV"""
    if not products:
        print("\nNo products to save!")
        return
    
    df = pd.DataFrame(products)
    
    # 1. Daily snapshot (with timestamp)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    daily_file = DATA_PATH / f"cagri_products_{timestamp}.csv"
    df.to_csv(daily_file, index=False, encoding='utf-8-sig')
    print(f"\nSaved: {daily_file}")
    
    # 2. History file (all products)
    history_file = DATA_PATH / "cagri_all_products.csv"
    
    if history_file.exists():
        existing_df = pd.read_csv(history_file, encoding='utf-8-sig')
        
        # Combine and remove duplicates (same product on same day)
        combined = pd.concat([existing_df, df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=['category', 'product_name', 'price_tl', 'date'], 
            keep='last'
        )
        
        combined.to_csv(history_file, index=False, encoding='utf-8-sig')
        print(f"Updated: {history_file}")
        print(f"Total history: {len(combined)} records")
    else:
        df.to_csv(history_file, index=False, encoding='utf-8-sig')
        print(f"Created: {history_file}")
    
    # Category summary
    print(f"\nCATEGORY SUMMARY:")
    for cat in df['category'].unique():
        count = len(df[df['category'] == cat])
        print(f"  {cat}: {count} products")

def main():
    """Main function"""
    start = time.time()
    
    try:
        products = scrape_all()
        
        if products:
            save_data(products)
            elapsed = time.time() - start
            print(f"\nTime: {elapsed:.1f} seconds")
            print("Done!")
        else:
            print("\nNo products found!")
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
