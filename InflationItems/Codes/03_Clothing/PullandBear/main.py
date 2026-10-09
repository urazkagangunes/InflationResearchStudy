import csv
import time
import sys
from datetime import datetime
from config import OUTPUT_FILE
from category_fetcher import get_all_category_ids
from product_fetcher import get_product_ids_for_category, get_products_detail, extract_name_price


def scrape_all():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pull & Bear Turkey scraper started")

    print("Fetching categories...")
    category_ids = get_all_category_ids()

    if not category_ids:
        print("ERROR: No categories found. Exiting.")
        sys.exit(1)

    print(f"Total categories: {len(category_ids)}")

    all_results = {}

    for idx, cat_id in enumerate(category_ids, 1):
        print(f"[{idx}/{len(category_ids)}] Category {cat_id}...", end=" ", flush=True)

        product_ids = get_product_ids_for_category(cat_id)
        if not product_ids:
            print("no products")
            continue

        print(f"{len(product_ids)} products", end=" ", flush=True)

        products = get_products_detail(product_ids, cat_id)

        count = 0
        for product in products:
            if not product:
                continue
            row = extract_name_price(product)
            if row and row["name"] and row["name"] not in all_results:
                all_results[row["name"]] = row["price"]
                count += 1

        print(f"→ {count} new")
        time.sleep(0.5)

    print(f"\nWriting {len(all_results)} products to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "shown_price"])
        for name, price in all_results.items():
            writer.writerow([name, f"{price:.2f}"])

    print(f"Done! {len(all_results)} unique products saved.")


if __name__ == "__main__":
    scrape_all()
