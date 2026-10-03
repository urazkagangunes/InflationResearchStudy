"""
gratis_scraper.py — Gratis Günlük Ürün Fiyat Scraper'ı

gratis.com/sitemap/Product-tr-TRY.xml üzerinden ürün linklerini alır,
her ürün sayfasındaki Schema.org LD+JSON etiketinden ad ve fiyatı çeker.
Asenkron çalışır, son derece hızlı ve stabildir.
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
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "Cosmetics" / "Gratis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITEMAP_URL = "https://www.gratis.com/sitemap/Product-tr-TRY.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

CONCURRENT_REQUESTS = 12

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def get_product_urls(session: aiohttp.ClientSession) -> list[str]:
    logger.info("Gratis ürün sitemap indiriliyor...")
    try:
        async with session.get(SITEMAP_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
            urls = re.findall(r"<loc>(https://[^<]+)</loc>", text)
            logger.info(f"Sitemap'ten {len(urls)} ürün linki bulundu.")
            return urls
    except Exception as e:
        logger.error(f"Sitemap indirme hatası: {e}")
        return []


async def scrape_product(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        for attempt in range(2):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    html = await resp.text()

                    # JSON-LD Product verisini hızlı regex ile veya BeautifulSoup ile çek
                    # Önce hızlı regex ile ara
                    matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
                    for m in matches:
                        try:
                            data = json.loads(m.strip())
                            if data.get("@type") == "Product":
                                name = data.get("name", "").strip()
                                offers = data.get("offers", {})
                                price_val = offers.get("price")
                                if name and price_val is not None:
                                    price = float(price_val)
                                    if price > 0:
                                        return {"product_name": name, "price": price}
                        except:
                            pass

                    # Fallback BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    h1 = soup.select_one("h1")
                    name = h1.get_text(strip=True) if h1 else ""
                    p_el = soup.select_one(".price, [class*='price'], [class*='Price']")
                    if p_el and name:
                        m_p = re.search(r"[\d.,]+", p_el.get_text(strip=True))
                        if m_p:
                            price = float(m_p.group(0).replace(".", "").replace(",", "."))
                            if price > 0:
                                return {"product_name": name, "price": price}

                    return None
            except Exception:
                await asyncio.sleep(0.5)
        return None


async def run():
    today = str(date.today())
    csv_path = OUT_DIR / f"gratis_{today}.csv"

    if csv_path.exists():
        logger.info(f"⛔ Bugünün dosyası zaten mevcut: {csv_path}")
        return

    logger.info(f"🚀 Gratis scraper başladı ({today})")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        urls = await get_product_urls(session)
        if not urls:
            logger.error("Ürün linkleri alınamadı.")
            return

        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        tasks = [scrape_product(session, url, semaphore) for url in urls]

        logger.info(f"Ürünler çekiliyor ({CONCURRENT_REQUESTS} eşzamanlı istek, toplam {len(urls)} ürün)...")
        results = await asyncio.gather(*tasks)

    valid_items = [r for r in results if r]
    logger.info(f"Toplam {len(valid_items)} ürün fiyatı başarıyla çekildi.")

    if not valid_items:
        logger.error("Hiç ürün fiyatı çekilemedi.")
        return

    # Tekilleştirme
    seen = set()
    dedup = []
    for it in valid_items:
        key = it["product_name"].lower()
        if key not in seen:
            seen.add(key)
            dedup.append(it)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price"])
        writer.writeheader()
        writer.writerows(dedup)

    logger.info(f"✅ {len(dedup)} ürün kaydedildi → {csv_path}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
