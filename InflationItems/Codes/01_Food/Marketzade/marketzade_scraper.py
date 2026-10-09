"""
=============================================================
  Marketzade Web Scraper — AI201 Intro to Data Science
  Sınıf Adı  : MarketzadeScraper
  CSV Çıktısı: YYYY-MM-DD.csv  (o günün tarihi)

  WooCommerce Store API kullanır — tarayıcı gerekmez.

  KURULUM (PyCharm Terminali):
      pip install requests
=============================================================
"""

import csv
import os
import re
import logging
import sys
import time
from datetime import date
from pathlib import Path
from html import unescape

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


class MarketzadeScraper:

    CSV_HEADERS = ["product_name", "price"]

    API_BASE = "https://marketzade.com/wp-json/wc/store/v1/products"

    CATEGORIES = {
        "temel-gida":    10315,
        "kahvaltilik":   10410,
        "atistirmalik":  10338,
        "icecek":        10319,
        "anne-bebek":    10455,
        "kisisel-bakim": 10348,
        "temizlik":      10312,
        "petshop":       10513,
        "ev-yasam":      10387,
    }

    PER_PAGE = 100
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.today = str(date.today())
        _SCRIPT_DIR = Path(__file__).resolve().parent
        _REPO_ROOT  = _SCRIPT_DIR.parents[3]
        _DATA_DIR   = _REPO_ROOT / "InflationItems" / "Datas" / "Markets" / "Marketzade"
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.csv_file      = str(_DATA_DIR / f"{self.today}.csv")
        self.total_scraped = 0
        self._ensure_file()
        self.session = self._init_session()

    # ── HTTP SESSION ──────────────────────────────────────────
    def _init_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        })
        log.info("HTTP session başlatıldı (API modu)")
        return s

    # ── DOSYA YÖNETİMİ ───────────────────────────────────────
    def _ensure_file(self):
        if os.path.exists(self.csv_file):
            log.error(
                f"⛔ DURDURULDU: {self.today} için '{self.csv_file}' zaten mevcut!\n"
                f"   Bugün ikinci kez çalıştırıyorsunuz. Tekrar veri eklenmedi."
            )
            sys.exit(0)

        with open(self.csv_file, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writeheader()
        log.info(f"Dosya oluşturuldu: {self.csv_file}")

    def _save_products(self, products: list):
        if not products:
            return
        with open(self.csv_file, "a", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writerows(products)
        self.total_scraped += len(products)

    # ── API İSTEKLERİ ────────────────────────────────────────
    def _fetch_page(self, category_id: int, page: int) -> list | None:
        params = {
            "per_page": self.PER_PAGE,
            "page":     page,
            "category": category_id,
        }
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(self.API_BASE, params=params, timeout=30)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    return []
                else:
                    log.warning(f"  HTTP {resp.status_code} (deneme {attempt}/{self.MAX_RETRIES})")
            except requests.RequestException as e:
                log.warning(f"  İstek hatası: {e} (deneme {attempt}/{self.MAX_RETRIES})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY)
        return None

    def _fetch_all_products(self, category: str, category_id: int) -> list:
        products = []
        seen_ids = set()
        page = 1

        while True:
            data = self._fetch_page(category_id, page)
            if data is None:
                log.error(f"  {category} sayfa {page} alınamadı, durduruluyor.")
                break
            if not data:
                break

            for item in data:
                pid = item.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                name  = self._clean_name(item.get("name", ""))
                price = self._extract_price(item)

                if not name:
                    continue

                products.append({
                    "product_name": name,
                    "price":        price,
                })

            log.info(f"  Sayfa {page}: {len(data)} ürün alındı (toplam {len(products)})")

            if len(data) < self.PER_PAGE:
                break
            page += 1

        return products

    # ── VERİ TEMİZLEME ───────────────────────────────────────
    @staticmethod
    def _clean_name(raw: str) -> str:
        text = unescape(raw)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def _extract_price(item: dict) -> str:
        try:
            prices = item.get("prices", {})
            raw = prices.get("sale_price") or prices.get("price", "")
            if not raw:
                return ""
            cents = int(raw)
            return f"{cents / 100:.2f}"
        except (ValueError, TypeError):
            return ""

    # ── KATEGORİ SCRAPE ──────────────────────────────────────
    def _scrape_category(self, category: str, category_id: int):
        log.info(f"▶ Kategori: {category} (ID: {category_id})")
        products = self._fetch_all_products(category, category_id)
        self._save_products(products)
        log.info(f"  ✓ {category}: {len(products)} ürün kaydedildi.\n")

    # ── ANA ÇALIŞTIRICI ──────────────────────────────────────
    def run(self):
        log.info("=" * 55)
        log.info(f"  Marketzade Scraper (API) — {self.today}")
        log.info("=" * 55)
        start = time.time()
        try:
            for category, cat_id in self.CATEGORIES.items():
                try:
                    self._scrape_category(category, cat_id)
                except Exception as e:
                    log.error(f"Kategori '{category}' hatası: {e}")
        finally:
            self.session.close()
            elapsed = time.time() - start
            log.info("=" * 55)
            log.info(f"  TAMAMLANDI — {self.total_scraped} ürün → '{self.csv_file}'")
            log.info(f"  Süre: {elapsed:.1f}s")
            log.info("=" * 55)


if __name__ == "__main__":
    scraper = MarketzadeScraper()
    scraper.run()
