import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime
import time
import os
import random

# --- Configuration ---
categories = [
    "elbise-c-0005", "bluz-c-0008", "kazak-c-0012", "pantolon-c-0013",
    "dis-giyim-c-0037", "ceket-c-0017", "gomlek-c-0009", "yelek-c-0032",
    "etek-c-0014", "hirka-c-0018", "tulum-c-0006", "sweatshirt-c-0011",
    "tisort-c-0010", "atlet-c-0036", "sort-c-0015", "ayakkabi-c-0021",
    "canta-c-0020", "aksesuar-c-0022"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- Setup Robust Session ---
# This tells the script to automatically retry 3 times if it hits a timeout or a bad server response (like 500 or 503)
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1.5, # Wait 1.5s, then 3s, then 4.5s between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
session.mount('https://', HTTPAdapter(max_retries=retries))


# --- Scraping Function ---
def scrape_adl_api(category_slug):
    category_data = []
    page = 0

    parts = category_slug.split('-c-')
    category_name = parts[0]
    category_id = parts[1]

    while True:
        api_url = f"https://api.adl.com.tr/occ/v2/adl/products/search?fields=FULL%2Cfacets%2Cbreadcrumbs%2Cpagination(DEFAULT)%2Csorts(DEFAULT)%2CfreeTextSearch%2CcurrentQuery&query=%3Arelevance%3AallCategories%3A{category_id}&pageSize=24&lang=tr&curr=TRY&currentPage={page}"

        print(f"  -> Fetching API: {category_name} (Page {page})")

        try:
            # Using the robust session, and increasing the timeout to 10 seconds to connect, 30 seconds to read.
            response = session.get(api_url, headers=headers, timeout=(10, 30))

            if response.status_code != 200:
                print(f"  -> Failed. Server returned status: {response.status_code}. Skipping page.")
                page += 1
                continue # Skip this page but keep trying the next ones

            json_data = response.json()

        except requests.exceptions.Timeout:
            # We only get here if the adapter fails all 3 retries
            print(f"  -> [ERROR] Request completely timed out on page {page} after retries. Skipping page.")
            page += 1
            continue
        except requests.exceptions.RequestException as e:
            print(f"  -> [ERROR] Network error occurred on page {page}: {e}")
            page += 1
            continue
        except ValueError:
            print(f"  -> [ERROR] Failed to parse JSON on page {page}.")
            page += 1
            continue

        if "products" not in json_data or len(json_data["products"]) == 0:
            print(f"  -> No more products found in {category_name}. Moving to next category.")
            break # It's safe to break here because we've naturally hit the end

        for product in json_data["products"]:
            try:
                name = product.get("name", "No Name")
                price_dict = product.get("price", {})
                current_price = price_dict.get("value", 0.0)

                category_data.append({
                    'Product Name': name,
                    'Price': current_price,
                    'Category': category_name
                })
            except Exception as e:
                print(f"  -> Error parsing product JSON: {e}")

        pagination = json_data.get("pagination", {})
        total_pages = pagination.get("totalPages", 1)

        if page >= total_pages - 1:
            print(f"  -> Reached the final page ({total_pages}) for {category_name}.")
            break

        page += 1

        sleep_time = random.uniform(2.5, 5.0)
        time.sleep(sleep_time)

    return category_data


# --- Main Execution ---
print("API Scraping started...")

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
save_dir = os.path.join(project_root, 'Datas', 'ClothingStores', 'adL')
os.makedirs(save_dir, exist_ok=True)

today_date = datetime.now().strftime('%Y-%m-%d')
filename = os.path.join(save_dir, f'adL_{today_date}.csv')

if os.path.exists(filename):
    print(f"Found existing file for today ({filename}). Overwriting to start fresh...")
    os.remove(filename)

total_scraped = 0

for category in categories:
    print(f"\n--- Starting: {category} ---")

    data = scrape_adl_api(category)

    if data:
        df = pd.DataFrame(data)
        file_exists = os.path.isfile(filename)
        df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
        total_scraped += len(data)
        print(f"  -> [PARTIAL SAVE] Saved {len(data)} items to CSV. (Total so far: {total_scraped})")
    else:
        print(f"  -> No data found for {category}, nothing to save.")

    cat_sleep_time = random.uniform(5.0, 10.0)
    print(f"  -> Resting for {cat_sleep_time:.1f} seconds before the next category...")
    time.sleep(cat_sleep_time)

print(f"\nSUCCESS! Scraping complete. A total of {total_scraped} products are safely saved in: {filename}")