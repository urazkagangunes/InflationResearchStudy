from datetime import datetime
from dotenv import load_dotenv
import os
import csv
import requests
import sys
import traceback


# Helper function to safely parse JSON responses and handle errors
def safe_get_json(response, context=""):
    try:
        # Check for HTTP errors (4xx, 5xx)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"[HTTP ERROR] {context}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text[:1000]}")
        raise e

    try:
        # Return parsed JSON data
        return response.json()
    except ValueError:
        print(f"[JSON PARSE ERROR] {context}")
        print(f"Raw Response: {response.text[:1000]}")
        raise


def main():
    try:
        # Determine project root and define data storage directory
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        DATA_DIR = os.path.join(BASE_DIR, "Datas", "Markets", "sok_market")

        # Create directory structure if it doesn't exist
        os.makedirs(DATA_DIR, exist_ok=True)

        # Define input (ID list) and output (CSV) file paths
        DATA_PATH = os.path.join(DATA_DIR, "x-store-ids.txt")
        csv_file = os.path.join(
            DATA_DIR,
            f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
        )

        # Load environment variables from .env file
        load_dotenv()

        # Validate required environment variables for API authentication
        required_envs = [
            "X-Ecommerce-Deviceid",
            "X-Ecommerce-Sid",
            "Cookie"
        ]

        for var in required_envs:
            if not os.getenv(var):
                raise EnvironmentError(f"Missing environment variable: {var}")

        url = "https://www.sokmarket.com.tr/api/v1/search"

        # Ensure the category ID file exists before proceeding
        if not os.path.exists(DATA_PATH):
            raise FileNotFoundError(f"{DATA_PATH} not found")

        # Read category IDs from file (expects format: Name-ID)
        x_store_ids = []
        with open(DATA_PATH, "r") as f:
            for line in f:
                parts = line.strip().split("-")
                if parts:
                    x_store_ids.append(parts[-1])  # Take the last part as the ID

        if not x_store_ids:
            raise ValueError("No category IDs found in x-store-ids.txt")

        # Use requests.Session for connection pooling and better performance
        session = requests.Session()
        products = {}  # Use a dictionary with Product ID as key to prevent duplicates

        # Iterate through each category to fetch products
        for cat_id in x_store_ids:
            print(f"[INFO] Fetching category: {cat_id}")

            params = {
                "cat": cat_id,
                "page": 0,
                "size": 20,
                "pgt": "CATEGORY_LISTING"
            }

            headers = {
                "X-Store-Id": "13412",
                "X-Platform": "WEB",
                "X-Service-Type": "MARKET",
                "X-App-Version": "81200425",
                "X-Ecommerce-Deviceid": os.getenv("X-Ecommerce-Deviceid"),
                "X-Ecommerce-Sid": os.getenv("X-Ecommerce-Sid"),
                "Cookie": os.getenv("Cookie")
            }

            # Initial request to determine total pages in the category
            try:
                response = session.get(url, params=params, headers=headers, timeout=15)
                data = safe_get_json(response, context=f"Initial request for cat {cat_id}")
            except Exception:
                print(f"[ERROR] Failed initial request for category {cat_id}")
                raise

            if "page" not in data or "totalPages" not in data["page"]:
                raise KeyError(f"Unexpected response structure for category {cat_id}: {data}")

            total_pages = data["page"]["totalPages"]
            print(f"[INFO] Total pages for {cat_id}: {total_pages}")

            # Paginate through all results in the category
            for page in range(total_pages):
                params["page"] = page
                try:
                    response = session.get(url, params=params, headers=headers, timeout=15)
                    data = safe_get_json(response, context=f"Category {cat_id}, page {page}")
                except Exception:
                    print(f"[ERROR] Failed at category {cat_id}, page {page}")
                    raise

                if "results" not in data:
                    print(f"[WARNING] No 'results' key for cat {cat_id}, page {page}")
                    continue

                # Parse individual items and store in products dictionary
                for item in data["results"]:
                    try:
                        product_id = item["product"]["id"]
                        name = item["product"]["name"]
                        price = item["prices"]["original"]["value"]
                    except KeyError as e:
                        print(f"[DATA STRUCTURE ERROR] Missing key {e} in item: {item}")
                        continue

                        # Map data to product ID to ensure uniqueness
                    products[product_id] = {
                        "name": name,
                        "price": price
                    }

        print(f"[INFO] Total products collected: {len(products)}")

        # Write collected product data to a timestamped CSV file
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "price"])
            writer.writeheader()
            writer.writerows(products.values())

        print(f"[SUCCESS] Data written to {csv_file}")

    except Exception as e:
        # Catch-all for logging failures and ensuring GitHub Actions fails properly
        print("\n========== SCRAPER FAILED ==========")
        print(str(e))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()