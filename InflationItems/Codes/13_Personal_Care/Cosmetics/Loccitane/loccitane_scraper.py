from pathlib import Path
"""
loccitane_scraper.py — L'Occitane Turkey Daily Product Price Scraper

loccitane.com.tr runs on Shopify.
Uses the public JSON endpoint:
  GET /collections/all/products.json?limit=250&page=N

Uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare bot challenges,
with fallback to aiohttp if curl_cffi is not installed.
"""

import asyncio
import csv
import os
import random
import sys
from datetime import datetime

try:
    from curl_cffi.requests import AsyncSession
except ImportError:
    AsyncSession = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

BASE_URL = "https://www.loccitane.com.tr"
PRODUCTS_ENDPOINT = f"{BASE_URL}/collections/all/products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PAGE_LIMIT = 250
DELAY_RANGE = (0.5, 1.2)


def get_save_path():
    this_dir = Path(__file__).resolve()
    project_root = next((p for p in this_dir.parents if (p / ".git").exists() or (p / "InflationItems").exists()), this_dir.parents[5])
    datas_dir = os.path.join(project_root, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "LOccitane")
    os.makedirs(datas_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(datas_dir, f"LOccitane_{today}.csv")


async def fetch_page(session, page, max_retries=3):
    params = {"limit": PAGE_LIMIT, "page": page}
    for attempt in range(1, max_retries + 1):
        try:
            if AsyncSession is not None and isinstance(session, AsyncSession):
                resp = await session.get(PRODUCTS_ENDPOINT, params=params, timeout=30)
                if resp.status_code != 200:
                    print(f"  Page {page} (attempt {attempt}/{max_retries}): HTTP {resp.status_code}")
                    if resp.status_code in (403, 429, 500, 502, 503, 504) and attempt < max_retries:
                        await asyncio.sleep(2 * attempt)
                        continue
                    return None
                data = resp.json()
                return data.get("products", [])
            else:
                async with session.get(
                    PRODUCTS_ENDPOINT,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        print(f"  Page {page} (attempt {attempt}/{max_retries}): HTTP {resp.status}")
                        if resp.status in (403, 429, 500, 502, 503, 504) and attempt < max_retries:
                            await asyncio.sleep(2 * attempt)
                            continue
                        return None
                    data = await resp.json(content_type=None)
                    return data.get("products", [])
        except Exception as e:
            print(f"  Page {page} (attempt {attempt}/{max_retries}) error: {type(e).__name__}: {e}")
            if attempt < max_retries:
                await asyncio.sleep(2 * attempt)
            else:
                return None
    return None


async def run():
    save_path = get_save_path()

    if os.path.exists(save_path):
        print(f"⛔ File already exists for today: {save_path}")
        return

    all_items = []
    seen = set()
    page = 1

    mode = "curl_cffi (Chrome impersonation)" if AsyncSession is not None else "aiohttp"
    print(f"🚀 L'Occitane TR scraper started using {mode}...")

    session_ctx = (
        AsyncSession(headers=HEADERS, impersonate="chrome120")
        if AsyncSession is not None
        else aiohttp.ClientSession(headers=HEADERS)
    )

    async with session_ctx as session:
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