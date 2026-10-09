"""
flormar_scraper.py — Flormar Daily Product Price Scraper

Fetches product URLs via flormar.com.tr sitemap-products-1.xml.gz,
extracts title and price from Schema.org LD+JSON / HTML on each product page.
Runs asynchronously and efficiently.
"""

import asyncio
import aiohttp
import csv
import json
import logging
import os
import re
import sys
import time
from bs4 import BeautifulSoup
from datetime import date
from pathlib import Path

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / ".git").exists()), Path(__file__).resolve().parents[5])
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Cosmetics" / "Flormar"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITEMAP_URL = "https://www.flormar.com.tr/sitemaps/sitemap-products-1.xml.gz"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CONCURRENT_REQUESTS = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def get_product_urls(session: aiohttp.ClientSession) -> list[str]:
    logger.info("Fetching sitemap...")
    try:
        async with session.get(SITEMAP_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            text = await resp.text()
            urls = re.findall(r"<loc>(https://[^<]+)</loc>", text)
            logger.info(f"Discovered {len(urls)} product URLs from sitemap.")
            return urls
    except Exception as e:
        logger.error(f"Sitemap fetch error: {e}")
        return []


async def scrape_single_product(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        for attempt in range(2):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")

                    name = ""
                    price = 0.0

                    # 1. LD+JSON
                    for s in soup.find_all("script", type="application/ld+json"):
                        try:
                            data = json.loads(s.string)
                            if data.get("@type") == "Product" or "offers" in data:
                                name = data.get("name", "")
                                p_val = data.get("offers", {}).get("price")
                                if p_val:
                                    price = float(p_val)
                                    break
                        except:
                            pass

                    # 2. Fallback H1 / price
                    if not name:
                        h1 = soup.select_one("h1")
                        name = h1.get_text(strip=True) if h1 else ""

                    if price <= 0:
                        p_el = soup.select_one(".price, [class*='price'], [class*='Price']")
                        if p_el:
                            m = re.search(r"[\d.,]+", p_el.get_text(strip=True))
                            if m:
                                price = float(m.group(0).replace(".", "").replace(",", "."))

                    if name and price > 0:
                        return {"product_name": name, "price": price, "url": url}
                    return None
            except Exception:
                await asyncio.sleep(1)
        return None


async def main_async():
    today = str(date.today())
    csv_path = OUT_DIR / f"flormar_{today}.csv"

    if csv_path.exists():
        logger.info(f"⛔ File already exists for today: {csv_path}")
        return

    logger.info(f"🚀 Flormar scraper started ({today})")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        urls = await get_product_urls(session)
        if not urls:
            return

        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        tasks = [scrape_single_product(session, url, semaphore) for url in urls]

        logger.info(f"Scraping products ({CONCURRENT_REQUESTS} concurrent workers)...")
        results = await asyncio.gather(*tasks)

    valid_items = [r for r in results if r]
    logger.info(f"Total {len(valid_items)} valid product prices collected.")

    if not valid_items:
        return

    seen = set()
    dedup = []
    for it in valid_items:
        if it["product_name"] not in seen:
            seen.add(it["product_name"])
            dedup.append(it)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price", "url"])
        writer.writeheader()
        writer.writerows(dedup)

    logger.info(f"✅ {len(dedup)} products saved → {csv_path}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
