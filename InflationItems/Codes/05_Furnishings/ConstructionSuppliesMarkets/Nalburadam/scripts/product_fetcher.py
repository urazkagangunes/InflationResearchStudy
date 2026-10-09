"""
product_fetcher.py — Paginates and scrapes products from Nalburadam categories.
"""

import time
import random
import logging
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config

logger = logging.getLogger(__name__)

def create_session():
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    retries = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def clean_price(price_str):
    if not price_str:
        return 0.0
    # Example: "31.500,00 TL" or "50,00 TL"
    price_str = price_str.upper().replace("TL", "").replace(" ", "").strip()
    price_str = price_str.replace(".", "").replace(",", ".")
    try:
        return float(price_str)
    except ValueError:
        return 0.0

def fetch_products_for_category(category_dict, session=None, limit_pages=0):
    cat_id = category_dict["id"]
    cat_url = category_dict["url"]
    name = category_dict["name"]
    req_session = session or create_session()
    
    products = []
    page = 1
    last_page_skus = set()
    
    adaptive_delay = config.REQUEST_DELAY
    consecutive_successes = 0
    consecutive_429s = 0
    
    logger.info(f"Starting {name}...")
    
    while True:
        if limit_pages > 0 and page > limit_pages:
            logger.info(f"Reached limit of {limit_pages} pages for {name}.")
            break
            
        url = f"{cat_url}?sayfa={page}" if page > 1 else cat_url
        logger.debug(f"[{name}] Fetching page {page}: {url}")
        
        try:
            resp = req_session.get(url, timeout=15)
            resp.raise_for_status()
            
            if resp.status_code == 200:
                consecutive_successes += 1
                consecutive_429s = 0
                if consecutive_successes >= 3 and adaptive_delay > config.REQUEST_DELAY * 0.5:
                    adaptive_delay *= 0.9
                    
        except Exception as e:
            logger.error(f"[{name}] Error fetching page {page}: {e}")
            if "429" in str(e):
                consecutive_429s += 1
                consecutive_successes = 0
                adaptive_delay = min(adaptive_delay * 2.0, 10.0)
                time.sleep(adaptive_delay)
                # Retry same page on 429
                continue
            else:
                break
            
        soup = BeautifulSoup(resp.text, 'lxml')
        
        items = soup.select('.showcase')
        if not items:
            logger.info(f"Page {page}: 0 items from {name}. Ending.")
            break
            
        current_page_skus = set()
        new_products_found = False
        
        for item in items:
            price_div = item.select_one('.showcase-price-new')
            if not price_div:
                continue
                
            add_btn = item.select_one('.add-to-cart-button')
            sku = add_btn['data-product-id'] if add_btn and add_btn.has_attr('data-product-id') else None
            
            a_tag = item.select_one('.showcase-title a')
            if not sku and a_tag:
                sku = a_tag['href'].split('-')[-1]
            if not sku:
                continue
                
            current_page_skus.add(sku)
            
            title = a_tag.text.strip() if a_tag else ""
            
            brand_a = item.select_one('.showcase-brand a')
            brand = brand_a.text.strip() if brand_a else ""
            
            price_val = clean_price(price_div.text)
            
            old_price_div = item.select_one('.showcase-price-old')
            old_price_val = price_val
            if old_price_div and old_price_div.text.strip():
                old_val_cleaned = clean_price(old_price_div.text)
                if old_val_cleaned > 0:
                    old_price_val = old_val_cleaned
                    
            discount_rate = 0.0
            if old_price_val > price_val and old_price_val > 0:
                discount_rate = round(((old_price_val - price_val) / old_price_val) * 100, 2)

            products.append({
                "product_name": title,
                "price": price_val,
                "id": sku,
                "sku": sku,
                "brand": brand,
                "category": name,
                "regular_price": old_price_val,
                "discount_rate": discount_rate,
                "unit": "PIECE",
                "status": "IN_SALE"
            })
            new_products_found = True
            
        if items:
            logger.info(f"  Page {page}: {len(items)} items")
            
        # Stop condition
        # If the page contents exactly match the previous page, we've likely hit the end 
        # (some sites return last page repeatedly)
        if current_page_skus == last_page_skus or not new_products_found:
            logger.info(f"Page {page}: same items as previous for {name}. Ending.")
            break
            
        # Nalburadam custom validation: verify if sayfa parameter effectively worked
        # Since testing ?sayfa=2 returned identical results in manual test for short lists,
        # we still check `current_page_skus == last_page_skus`.
            
        last_page_skus = current_page_skus
        page += 1
        
        # Normal distribution sleep (mean = config.REQUEST_DELAY, stdev = 0.4)
        # Ensure delay is at least config.REQUEST_FLOOR to avoid negative values or too fast scraping
        final_delay = max(config.REQUEST_FLOOR, random.normalvariate(config.REQUEST_DELAY, 0.4))
        time.sleep(final_delay)
        
    logger.info(f"{name} | {len(products)} items across {page-1} pages")
    return products
