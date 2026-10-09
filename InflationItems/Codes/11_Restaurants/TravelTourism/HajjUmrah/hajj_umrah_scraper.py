"""
=============================================================
  Hajj & Umrah Fee Scraper — AI201 Intro to Data Science
  Category   : Hajj and Umrah fees  (Batu Onlukus task)
  Source     : semersahturizm.com (Umrah price tables)
  CSV Output : YYYY-MM-DD.csv   (product_name,price)

  WHY THIS DESIGN
  ---------------
  Umrah operators publish a price matrix: package duration (10/14/20
  days...) x room occupancy (4/3/2-person room). Each (duration, room)
  combination is a well-defined, repeatable item, so we flatten the
  matrix into one product_name,price row per combination and track it
  over time.

  CURRENCY NOTE
  -------------
  Umrah packages are quoted in US dollars (USD) by the operators, so the
  `price` value is in USD and the product_name carries a "(USD)" marker.
  This is intentional: inflation here is a within-item percentage change,
  which is currency-agnostic, and keeping the native USD quote avoids
  adding FX-conversion noise. (All other project stores are in TL.)

  HOW IT WORKS
  ------------
  The price tables are rendered server-side, so a plain HTTP GET + HTML
  table parse is enough (no browser).

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
    """Parse a price string ('1.250$', '450 USD', '1.310 $') to float."""
    if not text:
        return None
    s = re.sub(r"[^0-9.,]", "", text)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        if re.search(r"\.\d{3}$", s):        # thousands separator
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def clean_label(text: str) -> str:
    """Tidy a duration/label cell: drop status notes like '(Tukendi)'."""
    text = re.sub(r"\([^)]*\)", "", text)    # remove parenthetical notes
    return re.sub(r"\s+", " ", text).strip()


def looks_like_price(raw: str) -> bool:
    """True only if the cell is a real price (digits + optional currency).

    Rejects section-header cells like "4'lu Oda" and discount cells like
    "%16 Indirimli" (these contain letters / percent signs).
    """
    if not raw or not re.search(r"\d", raw):
        return False
    if "%" in raw:
        return False
    leftover = re.sub(r"(usd|tl|₺|\$|\s|[0-9.,])", "", raw, flags=re.I)
    return leftover == ""


class HajjUmrahScraper:

    CSV_HEADERS = ["product_name", "price"]
    PROVIDER = "Semersah"
    URL = "https://www.semersahturizm.com/umre-fiyatlari/"

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.today = str(date.today())
        _SCRIPT_DIR = Path(__file__).resolve().parent
        _REPO_ROOT = next((p for p in _SCRIPT_DIR.parents if (p / ".git").exists()), _SCRIPT_DIR.parents[4])          # .../InflationResearchStudy
        _DATA_DIR = _REPO_ROOT / "InflationItems" / "Datas" / "TravelTourism" / "HajjUmrah"
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

    def _fetch(self):
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                r = self.session.get(self.URL, timeout=40)
                if r.status_code == 200:
                    return r.text
                log.warning(f"  HTTP {r.status_code} (deneme {attempt}/{self.MAX_RETRIES})")
            except requests.RequestException as e:
                log.warning(f"  istek hatasi {e} (deneme {attempt}/{self.MAX_RETRIES})")
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY)
        return None

    def _parse_table(self, table) -> list:
        """Flatten one price table into product_name,price rows."""
        rows_out = []
        trs = table.find_all("tr")
        if len(trs) < 2:
            return rows_out
        header = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]

        # ---- Matrix mode: duration x room-type (header contains "Oda") ----
        # The table interleaves section sub-headers (e.g. "Somestir Umresi",
        # "Ramazan Umresi") between the data rows; we track the current section
        # and prefix it onto each item so identities stay unique.
        if any("oda" in h.lower() for h in header):
            room_types = [clean_label(h) for h in header[1:]]
            section = "Standart"
            for tr in trs[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                price_cells = cells[1:]
                # A row with no real price cells is a section header / promo row.
                if not any(looks_like_price(c) for c in price_cells):
                    lbl = clean_label(cells[0])
                    if lbl:
                        section = lbl
                    continue
                duration = clean_label(cells[0])
                if not duration:
                    continue
                for idx, raw_price in enumerate(price_cells):
                    if not looks_like_price(raw_price):
                        continue
                    price = parse_money(raw_price)
                    room = room_types[idx] if idx < len(room_types) else f"Oda{idx + 1}"
                    if price:
                        name = f"{self.PROVIDER} Umre {section} {duration} - {room} (USD)"
                        rows_out.append({"product_name": name, "price": f"{price:.2f}"})
            return rows_out

        # ---- Last-column-price mode (header contains "Fiyat") ----
        if any("fiyat" in h.lower() for h in header):
            for tr in trs[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                price = parse_money(cells[-1])
                label = clean_label(" ".join(cells[:-1]))
                if price and label:
                    name = f"{self.PROVIDER} Umre {label} (USD)"
                    rows_out.append({"product_name": name, "price": f"{price:.2f}"})
        return rows_out

    def run(self):
        html = self._fetch()
        if not html:
            log.error("Sayfa alinamadi, cikiliyor.")
            sys.exit(1)
        soup = BeautifulSoup(html, "html.parser")
        seen = set()
        rows = []
        for table in soup.find_all("table"):
            for row in self._parse_table(table):
                if row["product_name"] in seen:
                    continue
                seen.add(row["product_name"])
                rows.append(row)
        self._save(rows)
        log.info(f"TAMAMLANDI — toplam {self.total_scraped} umre paketi -> {self.csv_file}")


if __name__ == "__main__":
    HajjUmrahScraper().run()
