"""
eveshop_scraper.py — Eve Shop Günlük Ürün Fiyat Scraper'ı

eveshop.com.tr Shopify altyapısı kullanır.
Açık JSON API kullanılır:
  GET /products.json?limit=250&page=N
"""

import asyncio
import aiohttp
import csv
import os
import random
from datetime import datetime

BASE_URL = "https://www.eveshop.com.tr"
PRODUCTS_ENDPOINT = f"{BASE_URL}/products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PAGE_LIMIT = 250
DELAY_RANGE = (0.3, 0.7)


def get_save_path():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(this_dir, "..", "..", "..", ".."))
    datas_dir = os.path.join(project_root, "InflationItems", "Datas", "Cosmetics", "Eveshop")
    os.makedirs(datas_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(datas_dir, f"eveshop_{today}.csv")


async def fetch_page(session, page):
    params = {"limit": PAGE_LIMIT, "page": page}
    try:
        async with session.get(
            PRODUCTS_ENDPOINT,
            params=params,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                print(f"  Sayfa {page}: HTTP {resp.status}")
                return None
            data = await resp.json(content_type=None)
            return data.get("products", [])
    except Exception as e:
        print(f"  Sayfa {page} hata: {type(e).__name__}: {e}")
        return None


async def run():
    save_path = get_save_path()
    if os.path.exists(save_path):
        print(f"⛔ Bugünün dosyası zaten mevcut: {save_path}")
        return

    all_items = []
    seen = set()
    page = 1

    print("🚀 Eveshop scraper başladı (Shopify JSON API)...")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while True:
            products = await fetch_page(session, page)

            if products is None:
                print(f"  Sayfa {page} alınamadı, duruyorum.")
                break

            if not products:
                print(f"  Sayfa {page}: boş — tamamlandı.")
                break

            for p in products:
                title = p.get("title", "N/A").strip()
                product_type = p.get("product_type", "")
                variants = p.get("variants", [])
                for v in variants:
                    sku = v.get("sku", "") or str(v.get("id", ""))
                    key = f"{title}|{sku}"
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        price = float(v.get("price", 0))
                    except (ValueError, TypeError):
                        price = 0.0

                    all_items.append({
                        "product_name": title,
                        "variant": v.get("title", ""),
                        "category": product_type,
                        "price": price,
                    })

            print(f"  Sayfa {page}: {len(products)} ürün (toplam: {len(all_items)})")
            page += 1
            await asyncio.sleep(random.uniform(*DELAY_RANGE))

    if not all_items:
        print("❌ Hiç ürün çekilemedi.")
        return

    with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "variant", "category", "price"])
        writer.writeheader()
        writer.writerows(all_items)

    print(f"\n✅ {len(all_items)} satır → {save_path}")


if __name__ == "__main__":
    asyncio.run(run())
