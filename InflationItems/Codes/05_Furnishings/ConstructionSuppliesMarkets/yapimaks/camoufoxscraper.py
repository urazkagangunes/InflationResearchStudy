#!/usr/bin/env python3
"""
Yapimaks.com Product Scraper
- Sitemap'i indirir, öncekiyle karşılaştırır (değişiklik varsa günceller)
- O günkü CSV'de zaten olan URL'leri atlar (kaldığı yerden devam)
- Her ürün anında CSV'ye yazılır (tarihli dosya adı)
"""

import csv
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox

# ─── AYARLAR ─────────────────────────────────────────────────────────────────
SITEMAP_URL        = "https://yapimaks.com/sitemap/products1.xml"
LOCAL_SITEMAP_PATH = "products1.xml"
OUTPUT_DIR         = "InflationItems/Datas/ConstructionSuppliesMarkets/yapimaks"
DELAY              = 0.0
FIELDNAMES         = ["product_id", "name", "sku", "marka", "stok_durumu",
                      "birim", "price", "currency", "url", "scraped_at"]
HEADERS            = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
# ─────────────────────────────────────────────────────────────────────────────


# ── CSV ───────────────────────────────────────────────────────────────────────

def get_csv_path() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, f"{today}.csv")


def load_scraped_urls(csv_path: str) -> set:
    """O günkü CSV'de zaten scrapelanmış URL'leri döndür."""
    if not os.path.isfile(csv_path):
        return set()
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {row["url"] for row in reader if row.get("url")}


def open_csv_writer(csv_path: str):
    file_exists = os.path.isfile(csv_path)
    f = open(csv_path, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if not file_exists:
        writer.writeheader()
        f.flush()
    return f, writer


def write_row(f, writer, data: dict):
    writer.writerow(data)
    f.flush()


# ── SİTEMAP ───────────────────────────────────────────────────────────────────

def fetch_sitemap(url: str) -> str:
    print(f"[*] Sitemap indiriliyor: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_urls(xml_text: str) -> list:
    xml_text = re.sub(r' xmlns="[^"]+"', "", xml_text)
    root = ET.fromstring(xml_text)
    return [el.findtext("loc", "").strip() for el in root.findall(".//url")]


def is_product_url(url: str) -> bool:
    return bool(re.search(r"-p\d+$", url.rstrip("/")))


def extract_product_id(url: str) -> str:
    m = re.search(r"-p(\d+)$", url.rstrip("/"))
    return m.group(1) if m else ""


def load_local_urls() -> set:
    if not os.path.exists(LOCAL_SITEMAP_PATH):
        return set()
    with open(LOCAL_SITEMAP_PATH, "r", encoding="utf-8") as f:
        return set(parse_urls(f.read()))


def save_local_sitemap(xml_text: str):
    with open(LOCAL_SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(xml_text)
    print(f"[*] Sitemap güncellendi -> {LOCAL_SITEMAP_PATH}")


# ── BROWSER ───────────────────────────────────────────────────────────────────

_camoufox_ctx = None
_browser      = None
_page         = None


def init_browser():
    global _camoufox_ctx, _browser, _page
    _camoufox_ctx = Camoufox(headless=True)
    _browser = _camoufox_ctx.__enter__()
    _page = _browser.new_page()


def close_browser():
    if _camoufox_ctx:
        _camoufox_ctx.__exit__(None, None, None)


# ── SCRAPE ────────────────────────────────────────────────────────────────────

def scrape_product(url: str) -> dict:
    product_id = extract_product_id(url)
    result = {
        "product_id": product_id,
        "url":         url,
        "name":        "",
        "sku":         "",
        "marka":       "",
        "stok_durumu": "",
        "birim":       "",
        "price":       "",
        "currency":    "TRY",
        "scraped_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        _page.goto(url, wait_until="networkidle", timeout=30000)
        try:
            _page.wait_for_selector("h5.text-primary.font-weight-bold", timeout=8000)
        except Exception:
            pass
        soup = BeautifulSoup(_page.content(), "html.parser")

        # ISIM
        name_el = soup.select_one("h5.mb-0")
        if name_el:
            result["name"] = name_el.get_text(strip=True)
        else:
            og = soup.find("meta", property="og:title")
            if og:
                result["name"] = og.get("content", "").split("|")[0].strip()

        # FIYAT
        price_el = soup.select_one("h5.text-primary.font-weight-bold")
        if price_el:
            price_text = price_el.get_text(separator=" ", strip=True)
            m = re.search(r"(\d[\d.]*,\d+)", price_text)
            result["price"] = m.group(1) if m else ""

        if not result["price"]:
            full = soup.get_text(separator="\n")
            m = re.search(r"Satis Fiyati\s*[:\-]?\s*(\d[\d.]*,\d+)", full, re.IGNORECASE)
            if m:
                result["price"] = m.group(1)

        # SKU
        sku_el = soup.select_one("small.text-muted")
        if sku_el:
            sku_text = sku_el.get_text(strip=True)
            m = re.search(r"SKU[:\s]+(.+)", sku_text, re.IGNORECASE)
            result["sku"] = m.group(1).strip() if m else sku_text

        # MARKA / STOK / BIRIM
        full = soup.get_text(separator="\n")
        for field, patterns in {
            "marka":       [r"Marka[:\s]+(.+)"],
            "stok_durumu": [r"Stok Durumu[:\s]+(.+)"],
            "birim":       [r"Birim[:\s]+(.+)"],
        }.items():
            for pat in patterns:
                m = re.search(pat, full, re.IGNORECASE)
                if m:
                    result[field] = m.group(1).strip()
                    break

        print(f"  + [{product_id}] {result['name'][:40]!r} | {result['price']} TL | SKU: {result['sku']}")

    except Exception as e:
        print(f"  x [{url}] Hata: {e}")

    return result


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Yapimaks Scraper")
    print("=" * 55)

    # 1. Sitemap'i indir
    new_xml      = fetch_sitemap(SITEMAP_URL)
    new_urls     = set(parse_urls(new_xml))
    product_urls = sorted(u for u in new_urls if is_product_url(u))
    print(f"[*] Toplam URL: {len(new_urls)} | Urun URL'i: {len(product_urls)}")

    # 2. Eski sitemap ile karsilastir, degistiyse guncelle
    old_urls = load_local_urls()
    if old_urls:
        added   = {u for u in product_urls if u not in old_urls}
        removed = {u for u in old_urls if is_product_url(u) and u not in new_urls}
        if added:
            print(f"[*] Yeni eklenen urun: {len(added)}")
        if removed:
            print(f"[!] Kaldirilmis urun: {len(removed)}")
            with open("removed_urls.txt", "w") as f:
                f.write("\n".join(sorted(removed)))
            print(f"    -> removed_urls.txt dosyasina yazildi")
        if not added and not removed:
            print("[*] Sitemap'te degisiklik yok.")
        if new_urls != old_urls:
            save_local_sitemap(new_xml)
    else:
        print("[*] Lokal sitemap bulunamadi — kaydediliyor.")
        save_local_sitemap(new_xml)

    # 3. O günkü CSV'de zaten olan URL'leri atla (kaldığı yerden devam)
    csv_path     = get_csv_path()
    scraped_urls = load_scraped_urls(csv_path)
    remaining    = [u for u in product_urls if u not in scraped_urls]

    if scraped_urls:
        print(f"[*] Daha once scraplanmis: {len(scraped_urls)} | Kalan: {len(remaining)}")
    if not remaining:
        print("[+] Bugun tum urunler zaten scraplanmis, cikiliyor.")
        return

    # 4. Tarayiciyi baslat
    print("[*] Tarayici baslatiliyor...")
    init_browser()

    # 5. Kalan URL'leri scrapelar, her satiri aninda yaz
    csv_file, writer = open_csv_writer(csv_path)
    print(f"[*] {len(remaining)} urun scrapelanacak -> {csv_path}")

    count = 0
    for i, url in enumerate(remaining, 1):
        print(f"[{i}/{len(remaining)}] {url}")
        data = scrape_product(url)
        write_row(csv_file, writer, data)
        count += 1
        time.sleep(DELAY)

    csv_file.close()
    close_browser()

    print(f"\n[+] Tamamlandi! {count} urun -> {csv_path}")


if __name__ == "__main__":
    main()