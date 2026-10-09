import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import os

# --- Configuration ---
BASE_URL = "https://mopas.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def get_category_links():
    """Finds all department links on the homepage."""
    print("Step 1: Fetching category links from homepage...")
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=20)
        category_urls = []

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            all_links = soup.find_all("a")

            for link in all_links:
                href = link.get("href")
                if href and "/c/" in href:
                    full_url = href if href.startswith("http") else BASE_URL + href
                    if full_url not in category_urls:
                        category_urls.append(full_url)

            print(f"Found {len(category_urls)} categories.")
            return category_urls
        else:
            print("Failed to load homepage.")
            return []
    except Exception as e:
        print(f"Error fetching homepage: {e}")
        return []


def scrape_entire_market():
    """Crawls through categories and pages to scrape all products."""
    categories = get_category_links()
    if not categories:
        print("No categories found. Exiting.")
        return

    all_products_data = []

    for category_index, category_url in enumerate(categories):
        print(f"\n--- Scanning Category {category_index + 1}/{len(categories)}: {category_url} ---")
        page_num = 0
        previous_page_items = []

        while True:
            page_url = f"{category_url}?q=%3Arelevance&page={page_num}"
            print(f"  Loading Page {page_num + 1}...")

            try:
                # Safety net: If Mopaş takes longer than 20 seconds, we skip the page instead of crashing
                response = requests.get(page_url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    print(f"  Failed to load page {page_num + 1}. Moving to next category.")
                    break
            except Exception as e:
                print(f"  Server timeout or error on page {page_num + 1}. Moving to next category.")
                break

            soup = BeautifulSoup(response.content, "html.parser")
            products = soup.find_all("div", class_="card")

            if len(products) == 0:
                print(f"  No more items found on page {page_num + 1}. Category finished.")
                break

            items_scraped_this_page = 0
            current_page_items = []

            for product in products:
                try:
                    title_tag = product.find("a", class_="product-title")
                    title = title_tag.text.strip() if title_tag else ""

                    price_tag = product.find("span", class_="sale-price")
                    raw_price = price_tag.text.strip() if price_tag else ""

                    quantity_tag = product.find("p", class_="quantity")
                    quantity = quantity_tag.text.strip().replace('\xa0', ' ').replace('&nbsp;', ' ').replace('&nbsp',
                                                                                                             ' ') if quantity_tag else ""

                    if title:
                        full_name = f"{title} {quantity}".strip()
                        clean_price = raw_price.replace('₺', '').replace('.', '').replace(',', '.').strip()

                        all_products_data.append({"name": full_name, "price": clean_price})
                        current_page_items.append(full_name)
                        items_scraped_this_page += 1

                except Exception as e:
                    pass

            # --- INFINITE LOOP CHECK ---
            if current_page_items == previous_page_items:
                print(f"  Detected infinite loop. Reached true end of category.")
                break

            previous_page_items = current_page_items.copy()
            # ---------------------------

            print(f"  Scraped {items_scraped_this_page} items.")
            page_num += 1
            time.sleep(1)

    # --- Save the Final Data ---
    if all_products_data:
        df = pd.DataFrame(all_products_data)

        # Drops duplicates from promo pages
        df.drop_duplicates(subset=['name'], keep='first', inplace=True)

        today_date = datetime.now().strftime("%Y-%m-%d")

        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create a specific 'mopas' folder inside Datas/Markets
        os.makedirs("Datas/Markets/Mopas", exist_ok=True)
        filename = f"Datas/Markets/Mopas/mopas_prices_{today_date}.csv"

        df.to_csv(filename, index=False, encoding='utf-8-sig')

        print(f"\nSUCCESS! Scraped and cleaned a total of {len(df)} unique items.")
        print(f"Data saved to {filename}")
    else:
        print("\nNo data was collected.")


# Run the crawler
if __name__ == "__main__":
    scrape_entire_market()
