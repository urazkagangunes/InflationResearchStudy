"""
=============================================================
  Holiday / Vacation Package Scraper — AI201 Intro to Data Science
  Category   : Holiday / vacation fees  (Batu Onlukus task)
  Source     : tatilsepeti.com (tour packages)
  CSV Output : YYYY-MM-DD.csv   (product_name,price)

  WHY THIS DESIGN
  ---------------
  A "holiday fee" here = the advertised starting price of a named tour
  package (e.g. "Bursa Cikisli Karadeniz Ruyasi ve Batum Turu"). Each
  named package is treated as one trackable item; re-running the scraper
  on different days captures how that package's price moves over time,
  which is exactly the signal an inflation study needs.

  HOW IT WORKS
  ------------
  For each tour-category listing page the price is rendered server-side,
  so a plain HTTP GET + HTML parse is enough (no browser):
    - each package is a `[data-tourname]` element (stable id: data-tourid)
    - its price sits in a nearby `.discount-price` element
  We write product_name,price rows, de-duplicated by tour id.

  SETUP (PyCharm terminal):
      pip install requests beautifulsoup4
=============================================================
"""

import csv
import logging
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_money(text: str):
    """Parse a Turkish-formatted price string to float.

    Handles '4.999,00 TL', '4.999, 00 TL', '1.250$', '450 USD'.
    Turkish convention: '.' = thousands separator, ',' = decimal.
    Returns float or None.
    """
    if not text:
        return None
    s = re.sub(r"[^0-9.,]", "", text)        # keep only digits . ,
    if not s:
        return None
    if "," in s and "." in s:                # 4.999,00 -> 4999.00
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                           # 4999,00 -> 4999.00
        s = s.replace(",", ".")
    elif "." in s:
        # '.' is thousands sep if the last group has 3 digits, else decimal
        if re.search(r"\.\d{3}$", s):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


class HolidayScraper:

    CSV_HEADERS = ["product_name", "price"]
    BASE = "https://www.tatilsepeti.com"

    # Tour-category listing pages that make up the holiday basket.
    CATEGORIES = [
        "kultur-turlari",
        "yurtdisi-turlar",
        "gap-turlari",
        "karadeniz-turlari",
        "dogu-ekspresi-turlari",
        "gunubirlik-turlar",
    ]

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.today = str(date.today())
        _SCRIPT_DIR = Path(__file__).resolve().parent
        _REPO_ROOT = next((p for p in _SCRIPT_DIR.parents if (p / ".git").exists()), _SCRIPT_DIR.parents[4])          # .../InflationResearchStudy
        _DATA_DIR = _REPO_ROOT / "InflationItems" / "Datas" / "TravelTourism" / "HolidayPackages"
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.csv_file = str(_DATA_DIR / f"{self.today}.csv")
        self.total_scraped = 0
        self._ensure_file()
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",     # no brotli (requests can't decode)
        })
        log.info("HTTP session baslatildi")
        return s

    def _ensure_file(self):
        if os.path.exists(self.csv_file):
            log.error(
                f"DURDURULDU: {self.today} icin '{self.csv_file}' zaten mevcut. "
                f"Bugun ikinci kez calistiriliyor; veri eklenmedi."
            )
            sys.exit(0)
        with open(self.csv_file, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writeheader()
        log.info(f"Dosya olusturuldu: {self.csv_file}")

    def _save(self, rows: list):
        if not rows:
            return
        with open(self.csv_file, "a", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writerows(rows)
        self.total_scraped += len(rows)

    def _fetch(self, slug: str):
        url = f"{self.BASE}/{slug}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                r = self.session.get(url, timeout=40)
                if r.status_code == 200:
                    return r.text
                if r.status_code in (404, 410):
                    log.info(f"  {slug}: sayfa yok (HTTP {r.status_code}), atlaniyor")
                    return None
                log.warning(f"  {slug}: HTTP {r.status_code} (deneme {attempt}/{self.MAX_RETRIES})")
            except requests.RequestException as e:
                log.warning(f"  {slug}: istek hatasi {e} (deneme {attempt}/{self.MAX_RETRIES})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY)
        return None

    @staticmethod
    def _parse_tours(html: str):
        """Yield (tour_id, tour_name, price_float) from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-tourname]"):
            name = (el.get("data-tourname") or "").strip()
            tid = (el.get("data-tourid") or "").strip()
            if not name:
                continue
            # climb to the nearest ancestor that contains a price element
            price = None
            node = el
            for _ in range(6):
                node = node.parent
                if node is None:
                    break
                disc = node.select_one(".discount-price")
                if disc:
                    price = parse_money(disc.get_text(" ", strip=True))
                    break
            if price:
                yield tid, name, price

    def run(self):
        seen = set()
        for slug in self.CATEGORIES:
            html = self._fetch(slug)
            if not html:
                continue
            rows = []
            for tid, name, price in self._parse_tours(html):
                # De-duplicate by product_name (the inflation key). The same tour
                # can be listed under several categories; identical display names
                # must appear only once so the daily time series stays consistent.
                if name in seen:
                    continue
                seen.add(name)
                rows.append({"product_name": name, "price": f"{price:.2f}"})
            self._save(rows)
            log.info(f"  {slug}: {len(rows)} tur kaydedildi")
            time.sleep(0.5)

        log.info(f"TAMAMLANDI — toplam {self.total_scraped} tur -> {self.csv_file}")


if __name__ == "__main__":
    HolidayScraper().run()
