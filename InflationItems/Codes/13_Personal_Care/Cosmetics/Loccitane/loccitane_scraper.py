from pathlib import Path
"""
loccitane_scraper.py — L'Occitane Turkey Daily Product Price Scraper

loccitane.com.tr runs on Shopify.
Uses the public JSON endpoint:
  GET /collections/all/products.json?limit=250&page=N

No headless browser required, fast and reliable.
"""

import asyncio
import aiohttp
import csv
import os
import random
from datetime import datetime

BASE_URL = "https://www.loccitane.com.tr"
PRODUCTS_ENDPOINT = f"{BASE_URL}/collections/all/products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PAGE_LIMIT = 250
DELAY_RANGE = (0.3, 0.8)


def get_save_path():
    this_dir = Path(__file__).resolve()
    project_root = next((p for p in this_dir.parents if (p / ".git").exists()), this_dir.parents[5])
    datas_dir = os.path.join(project_root, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "LOccitane")
    os.makedirs(datas_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(datas_dir, f"LOccitane_{today}.csv")


async def fetch_page(session, page):
    params = {"limit": PAGE_LIMIT, "page": page}
    try:
        async with session.get(
            PRODUCTS_ENDPOINT,
            params=params,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                print(f"  Page {page}: HTTP {resp.status}")
                return None
            data = await resp.json(content_type=None)
            return data.get("products", [])
    except Exception as e:
        print(f"  Page {page} error: {type(e).__name__}: {e}")
        return None


async def run():
    save_path = get_save_path()

    if os.path.exists(save_path):
        print(f"⛔ File already exists for today: {save_path}")
        return

    all_items = []
    seen = set()
    page = 1

    print("🚀 L'Occitane TR scraper started (Shopify JSON API)...")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while True:
            products = await fetch_page(session, page)

            if products is None:
                print(f"  Could not load page {page}, stopping.")
                break

            if not products:
                print(f"  Page {page}: empty — finished.")
                break

            for p in products:
                title = p.get("title", "N/A").strip()
                variants = p.get("variants", [])
                for v in variants:
                    sku = v.get("sku", "") or v.get("id", "")
                    key = f"{title}|{sku}"
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        price = float(v.get("price", 0))
                    except (ValueError, TypeError):
                        price = 0.0
                    all_items.append({
                        "title": title,
                        "variant": v.get("title", ""),
                        "price": price,
                    })

            print(f"  Page {page}: {len(products)} products (total: {len(all_items)})")
            page += 1
            await asyncio.sleep(random.uniform(*DELAY_RANGE))

    if not all_items:
        print("❌ No products collected.")
        return

    with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price", "variant"])
        writer.writeheader()
        for item in all_items:
            writer.writerow({
                "product_name": item["title"],
                "price": item["price"],
                "variant": item["variant"],
            })

    print(f"\n✅ {len(all_items)} records → {save_path}")


if __name__ == "__main__":
    asyncio.run(run())