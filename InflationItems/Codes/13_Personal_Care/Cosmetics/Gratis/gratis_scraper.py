"""
gratis_scraper.py — Gratis Daily Product Price Scraper

Fetches product URLs via gratis.com/sitemap/Product-tr-TRY.xml,
extracts title and price from Schema.org LD+JSON tags on each product page.
Uses gentle rate limiting (50-80 requests/min), periodic CSV flushing,
and an automatic circuit breaker (aborts safely if rate-limited continuously).
"""

import asyncio
import aiohttp
import csv
import json
import logging
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / ".git").exists()), Path(__file__).resolve().parents[5])
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Cosmetics" / "Gratis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITEMAP_URL = "https://www.gratis.com/sitemap/Product-tr-TRY.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}

# --- RATE LIMITING: Target 50 - 80 requests per minute ---
CONCURRENT_REQUESTS = 2
REQUEST_DELAY_RANGE = (0.8, 1.5)

# --- CIRCUIT BREAKER: Stop if rate limit persists ---
MAX_CONSECUTIVE_BLOCKS = 10  # If 10 consecutive requests return 403/429, abort safely
consecutive_blocks = 0
abort_signal = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def get_product_urls(session: aiohttp.ClientSession) -> list[str]:
    logger.info("Fetching Gratis product sitemap...")
    for attempt in range(3):
        try:
            async with session.get(SITEMAP_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    urls = re.findall(r"<loc>(https://[^<]+)</loc>", text)
                    logger.info(f"Discovered {len(urls)} product URLs from sitemap.")
                    return urls
                elif resp.status in (403, 429):
                    logger.warning(f"Sitemap access blocked (HTTP {resp.status}). Waiting 20s...")
                    await asyncio.sleep(20)
                else:
                    await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Sitemap fetch error: {e}. Waiting 10s...")
            await asyncio.sleep(10)
    return []


async def scrape_product(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> dict | None:
    global consecutive_blocks, abort_signal

    if abort_signal:
        return None

    async with semaphore:
        for attempt in range(2):
            if abort_signal:
                return None

            try:
                await asyncio.sleep(random.uniform(*REQUEST_DELAY_RANGE))

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status in (403, 429):
                        consecutive_blocks += 1
                        logger.warning(
                            f"Rate limit hit ({resp.status}) on {url[-30:]} "
                            f"[Consecutive blocks: {consecutive_blocks}/{MAX_CONSECUTIVE_BLOCKS}]"
                        )
                        if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                            logger.error(
                                f"🚨 CIRCUIT BREAKER TRIGGERED: Site blocked {consecutive_blocks} consecutive requests. "
                                f"Stopping scraper to protect IP."
                            )
                            abort_signal = True
                            return None

                        wait_time = 15 * (attempt + 1)
                        await asyncio.sleep(wait_time)
                        continue

                    # Reset consecutive blocks on any successful response
                    consecutive_blocks = 0

                    if resp.status != 200:
                        return None

                    html = await resp.text()

                    # 1. Primary: JSON-LD Product schema
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

                    # 2. Fallback: HTML extraction
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
                await asyncio.sleep(1)
        return None


async def run():
    global abort_signal
    today = str(date.today())
    csv_path = OUT_DIR / f"gratis_{today}.csv"

    logger.info(f"🚀 Gratis scraper started ({today}) — Safe Mode (~50-80 req/min with auto circuit breaker)")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        urls = await get_product_urls(session)
        if not urls:
            logger.error("Could not retrieve product URLs (Site is currently blocking IP). Exiting gracefully.")
            return

        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        logger.info(f"Scraping products ({CONCURRENT_REQUESTS} concurrent workers)...")

        seen = set()
        dedup = []

        # Load existing partial data so work is never lost
        if csv_path.exists():
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        k = r.get("product_name", "").lower()
                        if k and k not in seen:
                            seen.add(k)
                            dedup.append({"product_name": r["product_name"], "price": float(r["price"])})
                logger.info(f"Loaded {len(dedup)} existing products from today's partial CSV.")
            except Exception as e:
                logger.warning(f"Could not load partial CSV: {e}")

        # Batch processing with regular flush to CSV
        batch_size = 100
        for i in range(0, len(urls), batch_size):
            if abort_signal:
                logger.warning("Scraper aborted by circuit breaker. Saving current progress...")
                break

            batch = urls[i:i + batch_size]
            tasks = [scrape_product(session, url, semaphore) for url in batch]
            results = await asyncio.gather(*tasks)

            new_count = 0
            for r in results:
                if r:
                    key = r["product_name"].lower()
                    if key not in seen:
                        seen.add(key)
                        dedup.append(r)
                        new_count += 1

            # Flush to disk immediately
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["product_name", "price"])
                writer.writeheader()
                writer.writerows(dedup)

            processed = min(i + batch_size, len(urls))
            logger.info(f"Progress: {processed}/{len(urls)} URLs | +{new_count} new | Total unique: {len(dedup)}")

    if abort_signal:
        logger.warning(f"🛑 Run terminated early due to rate limit block. Preserved {len(dedup)} items in {csv_path}")
    else:
        logger.info(f"✅ Scraping completed! {len(dedup)} unique items saved → {csv_path}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
