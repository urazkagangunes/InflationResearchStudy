# -*- coding: utf-8 -*-
"""
Created on Sat Mar 14 22:47:13 2026

@author: orenl
"""

# -*- coding: utf-8 -*-
"""
Bizim Toptan Scraper - Timestamped & Incremental
- Saves to a single CSV with the current date/time in the filename.
- Prevents infinite loops by breaking when no new products are found.
- Saves data in real-time to prevent loss.
"""

import os
import re
import csv
import time
import html
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_URL = "https://www.bizimtoptan.com.tr"
START_URL = BASE_URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

REQUEST_DELAY = 0.7
OUTPUT_DIR = "bizimtoptan_output"

# Generate filename with current date and time
current_time = datetime.now().strftime("%Y%m%d_%H%M")
PRODUCTS_CSV = os.path.join(OUTPUT_DIR, f"bizimtoptan_urunler_{current_time}.csv")

# Global set to track IDs across the entire session
global_seen_ids = set()

session = requests.Session()
session.headers.update(HEADERS)

def safe_get(url):
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp
    except Exception as e:
        print(f"\n[!] Connection Error: {url} -> {e}")
        return None

def get_soup(url):
    resp = safe_get(url)
    return BeautifulSoup(resp.text, "html.parser") if resp else None

def clean_text(text):
    if not text: return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def normalize_price(price_text):
    if not price_text: return ""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}\s*TL)", price_text, flags=re.I)
    return m.group(1).replace(" ", "") if m else clean_text(price_text)

def parse_page_count(soup):
    if not soup: return 1
    max_page = 1
    # Looking for the highest number in pagination links
    for a in soup.select("div.pager-container a, ul.pagination a"):
        text = clean_text(a.get_text())
        if text.isdigit():
            max_page = max(max_page, int(text))
    return max_page

def discover_main_categories():
    soup = get_soup(START_URL)
    if not soup: return []
    categories = []
    for a in soup.select("a.main-menu-link"):
        href = a.get("href")
        name = clean_text(a.get_text())
        if href and name:
            categories.append({"main_category": name, "url": urljoin(BASE_URL, href)})
    return categories

def discover_subcategories(main_cat_name, main_cat_url):
    soup = get_soup(main_cat_url)
    if not soup: return []
    subcategories = []
    candidates = soup.select("a.parents") or soup.select("ul.spec-list a[href]")
    for a in candidates:
        href = a.get("href")
        name = clean_text(a.get_text())
        if href and name:
            subcategories.append({
                "main_category": main_cat_name,
                "sub_category": name,
                "url": urljoin(BASE_URL, href)
            })
    # If no subcategories found, return the main category itself as a target
    return subcategories if subcategories else [{"main_category": main_cat_name, "sub_category": "", "url": main_cat_url}]

def extract_products_from_page(soup, category_text):
    products = []
    if not soup: return products
    
    # Targeting the product grid specifically to avoid sidebars/footers
    cards = soup.select("div.product-list-container div.product-box-container") 
    if not cards:
        cards = soup.select("div.product-box-container")

    for card in cards:
        pid = card.get("data-productid")
        
        # Name extraction via JSON or Alt tag
        name_tag = card.select_one("a.product-item")
        name = ""
        if name_tag and name_tag.get("data-enhanced-productclick"):
            try:
                data = json.loads(name_tag.get("data-enhanced-productclick"))
                name = data.get("item_name", "")
                if not pid: pid = data.get("item_id")
            except: pass
        
        if not name:
            img = card.select_one(".product-box-image-container img")
            name = clean_text(img.get("alt", "")) if img else ""

        price = normalize_price(card.get_text(" ", strip=True))

        if pid and (name or price):
            products.append({
                "product_id": str(pid),
                "product_name": name,
                "category": category_text,
                "price": price
            })
    return products

def append_to_csv(products):
    """Writes results to the CSV file immediately."""
    if not products: return 0
    file_exists = os.path.isfile(PRODUCTS_CSV)
    os.makedirs(os.path.dirname(PRODUCTS_CSV), exist_ok=True)
    
    written_count = 0
    with open(PRODUCTS_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "price"])
        if not file_exists:
            writer.writeheader()
        
        for p in products:
            if p["product_id"] not in global_seen_ids:
                writer.writerow(p)
                global_seen_ids.add(p["product_id"])
                written_count += 1
    return written_count

def main():
    print(f"Scraper started. File: {PRODUCTS_CSV}")
    main_cats = discover_main_categories()
    
    for m_cat in main_cats:
        try:
            subs = discover_subcategories(m_cat["main_category"], m_cat["url"])
            for sub in subs:
                cat_label = f"{sub['main_category']} > {sub['sub_category']}" if sub['sub_category'] else sub['main_category']
                print(f"\nProcessing: {cat_label}")
                
                first_page_soup = get_soup(sub["url"])
                total_pages = parse_page_count(first_page_soup)
                
                for page_num in range(1, total_pages + 1):
                    # Construct URL for pagination
                    page_url = sub["url"] if page_num == 1 else f"{sub['url']}?pagenumber={page_num}"
                    print(f"  -> Page {page_num}/{total_pages}", end="\r")
                    
                    soup = get_soup(page_url)
                    page_products = extract_products_from_page(soup, cat_label)
                    
                    # INFINITE LOOP PROTECTION:
                    # Check if any products on this page are actually new.
                    # If the page has products but 0 are new (already seen), we are likely on a loop/recommendation page.
                    new_items = [p for p in page_products if p["product_id"] not in global_seen_ids]
                    
                    if not page_products or (page_num > 1 and not new_items):
                        # Break if page is empty OR we've already recorded everything here.
                        break
                    
                    append_to_csv(page_products)
                    
        except Exception as e:
            print(f"\n[!] Error in category {m_cat['main_category']}: {e}")
            continue

    print(f"\n\nDone! Total unique products saved: {len(global_seen_ids)}")
    print(f"Final CSV: {PRODUCTS_CSV}")

if __name__ == "__main__":
    main() 