"""
=============================================================
  Hotel Price Scraper — AI201 Intro to Data Science
  Category   : Hotel prices  (Batu Onlukus task)
  Source     : tatilsepeti.com
  CSV Output : YYYY-MM-DD.csv   (product_name,price)

  WHY THIS DESIGN
  ---------------
  Hotel prices are *date dependent*: the same room costs different
  amounts depending on the check-in date and how far away it is.
  To make day-to-day prices comparable for an inflation study we must
  re-price the SAME basket every run. We therefore query a fixed
  rolling window:  check-in = today + 30 days, 1 night, 2 adults.
  That fixed basket is encoded into product_name so each run measures
  the same thing:  "<Hotel> | <City> | +30g 1gece 2yetiskin".

  HOW IT WORKS
  ------------
  1. GET the city listing page  -> read data-hotelid / data-hotelname
     (the listing also hands us the session cookies we need).
  2. POST /hotel/GetHotelListPrice/ with the fixed basket + hotel ids
     -> a clean JSON response with Price / DiscountPrice per hotel.
  3. Write product_name,price rows (cheapest bookable price per hotel).

  Browser is NOT required — the site exposes a JSON price endpoint.

  SETUP (PyCharm terminal):
      pip install requests beautifulsoup4
=============================================================
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


class HotelScraper:

    CSV_HEADERS = ["product_name", "price"]

    BASE = "https://www.tatilsepeti.com"
    PRICE_API = "https://www.tatilsepeti.com/hotel/GetHotelListPrice/"

    # Fixed basket — re-priced identically every run (inflation comparability)
    CHECKIN_OFFSET_DAYS = 30
    NIGHTS = 1
    ADULTS = 2

    # City listing pages that form our hotel basket (label -> URL slug)
    CITIES = {
        "Antalya":   "antalya-otelleri",
        "Istanbul":  "istanbul-otelleri",
        "Izmir":     "izmir-otelleri",
        "Mugla":     "mugla-otelleri",
        "Nevsehir":  "nevsehir-otelleri",
        "Bursa":     "bursa-otelleri",
    }

    BATCH = 40           # hotel ids per price-API call
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.today = str(date.today())
        _SCRIPT_DIR = Path(__file__).resolve().parent
        _REPO_ROOT = next((p for p in _SCRIPT_DIR.parents if (p / ".git").exists()), _SCRIPT_DIR.parents[4])          # .../InflationResearchStudy
        _DATA_DIR = _REPO_ROOT / "InflationItems" / "Datas" / "TravelTourism" / "Hotels"
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.csv_file = str(_DATA_DIR / f"{self.today}.csv")
        self.total_scraped = 0
        self._ensure_file()
        self.session = self._init_session()

        ci = date.today() + timedelta(days=self.CHECKIN_OFFSET_DAYS)
        co = ci + timedelta(days=self.NIGHTS)
        self.checkin = ci.strftime("%d.%m.%Y")
        self.checkout = co.strftime("%d.%m.%Y")
        self.basket_tag = f"+{self.CHECKIN_OFFSET_DAYS}g {self.NIGHTS}gece {self.ADULTS}yetiskin"

    # ── HTTP SESSION ──────────────────────────────────────────
    def _init_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            # NOTE: do not request brotli ("br") — requests can't decode it
            "Accept-Encoding": "gzip, deflate",
        })
        log.info("HTTP session baslatildi")
        return s

    # ── FILE HANDLING ─────────────────────────────────────────
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

    # ── LISTING: hotel id -> name ─────────────────────────────
    def _fetch_hotels(self, city_label: str, slug: str) -> dict:
        """Return {hotel_id: hotel_name} for a city listing page."""
        url = f"{self.BASE}/{slug}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                r = self.session.get(url, timeout=40)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    hotels = {}
                    for el in soup.select("[data-hotelid][data-hotelname]"):
                        hid = (el.get("data-hotelid") or "").strip()
                        name = (el.get("data-hotelname") or "").strip()
                        if hid and name:
                            hotels[hid] = name
                    log.info(f"  {city_label}: {len(hotels)} otel listelendi")
                    return hotels
                log.warning(f"  {city_label}: HTTP {r.status_code} (deneme {attempt}/{self.MAX_RETRIES})")
            except requests.RequestException as e:
                log.warning(f"  {city_label}: istek hatasi {e} (deneme {attempt}/{self.MAX_RETRIES})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY)
        return {}

    # ── PRICE API ─────────────────────────────────────────────
    def _fetch_prices(self, slug: str, hotel_ids: list) -> dict:
        """Return {hotel_id: price_float} for the fixed basket."""
        out = {}
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": self.BASE,
            "Referer": f"{self.BASE}/{slug}",
        }
        for i in range(0, len(hotel_ids), self.BATCH):
            chunk = hotel_ids[i:i + self.BATCH]
            payload = {
                "AdultCount": self.ADULTS,
                "ChildCount": 0,
                "ChildAges": [],
                "CampaignType": 0,
                "CampaignId": None,
                "checkinDate": self.checkin,
                "checkoutDate": self.checkout,
                "HotelIds": ",".join(chunk),
            }
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    r = self.session.post(
                        self.PRICE_API, data=json.dumps(payload),
                        headers=headers, timeout=40,
                    )
                    if r.status_code == 200:
                        for h in (r.json() or []):
                            if not h.get("HasPrice"):
                                continue
                            hid = str(h.get("HotelId"))
                            # DiscountPrice = price actually paid; fall back to list Price
                            price = h.get("DiscountPrice") or h.get("Price") or 0
                            if price and price > 0:
                                out[hid] = float(price)
                        break
                    log.warning(f"  fiyat API HTTP {r.status_code} (deneme {attempt}/{self.MAX_RETRIES})")
                except (requests.RequestException, ValueError) as e:
                    log.warning(f"  fiyat API hatasi {e} (deneme {attempt}/{self.MAX_RETRIES})")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
            time.sleep(0.5)  # be polite between batches
        return out

    # ── MAIN ──────────────────────────────────────────────────
    def run(self):
        log.info(
            f"Otel sepeti: check-in {self.checkin} -> check-out {self.checkout} "
            f"({self.ADULTS} yetiskin, {self.NIGHTS} gece)"
        )
        seen = set()
        for city_label, slug in self.CITIES.items():
            hotels = self._fetch_hotels(city_label, slug)
            if not hotels:
                continue
            prices = self._fetch_prices(slug, list(hotels.keys()))
            rows = []
            for hid, name in hotels.items():
                if hid in seen:
                    continue
                price = prices.get(hid)
                if price is None:
                    continue
                seen.add(hid)
                product_name = f"{name} | {city_label} | {self.basket_tag}"
                rows.append({"product_name": product_name, "price": f"{price:.2f}"})
            self._save(rows)
            log.info(f"  {city_label}: {len(rows)} otel fiyati kaydedildi")

        log.info(f"TAMAMLANDI — toplam {self.total_scraped} otel -> {self.csv_file}")


if __name__ == "__main__":
    HotelScraper().run()
