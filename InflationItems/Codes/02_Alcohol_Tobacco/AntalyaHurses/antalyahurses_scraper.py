"""Cigarette prices from an Antalya Hürses "güncel zamlı sigara fiyatları" article.

The article has one table per company group (JTI, BAT, Imperial, Philip
Morris, Captain Black) with Ürün Adı / Güncel Fiyat columns. The page repeats
the same prices in other lists and a loose-tobacco table, and an older TT group
list, so only the company tables are read.

Output: antalyahurses_sigara_YYYY-MM-DD.csv with product_name, price,
category_number, sub_category_number (COICOP). Cigarettes get 0230101; the
loose rolling tobacco lines have no code and get 0. Inside the repo it goes to
the data folder that mirrors this code folder
(InflationItems/Datas/02_Alcohol_Tobacco/AntalyaHurses); run anywhere else, it
goes to the current folder.
"""

import csv
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://www.antalyahurses.com/guncel-zamli-sigara-fiyatlari/530457"
FIELDS = ["product_name", "price", "category_number", "sub_category_number"]

CATEGORY_NUMBER = "02"  # Alkollü içecekler ve tütün
CIGARETTE_CODE = "0230101"
NO_CODE = "0"


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.split(os.sep)
    if "InflationItems" not in parts:
        return os.getcwd()
    root = parts.index("InflationItems")
    return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])


def parse_price(text):
    # "120 ₺", "130 TL", "1.050" -> float
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", text)
    values = [float(n.replace(".", "").replace(",", ".")) for n in numbers]
    return round(sum(values) / len(values), 2) if values else None


def find_col(header, key):
    for i, h in enumerate(header):
        if key in h.lower():
            return i
    return None


def sub_category(name):
    # Loose rolling tobacco is not a cigarette pack, so it gets no cigarette code
    lower = name.lower()
    if "tütün" in lower or "sarmal" in lower:
        return NO_CODE
    return CIGARETTE_CODE


def scrape(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
        name_i = find_col(header, "ürün")
        price_i = find_col(header, "fiyat")
        # Only the company tables; the loose tobacco table is headed Marka / Gramaj
        if name_i is None or price_i is None:
            continue

        for tr in trs[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= max(name_i, price_i):
                continue
            name = " ".join(cells[name_i].replace("\xa0", " ").split())
            rows.append((name, cells[price_i]))
    return rows


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    raw = scrape(url)

    rows, skipped = [], []
    for name, price_text in raw:
        price = parse_price(price_text)
        if price is None:
            skipped.append(f"{name}: {price_text}")
            continue
        rows.append((name, price, CATEGORY_NUMBER, sub_category(name)))

    if not rows:
        print("No prices found; CSV not written. Is the link a cigarette price article?")
        sys.exit(1)

    for r in rows:
        if r[3] == NO_CODE:
            print(f"No COICOP code for '{r[0]}', written with 0")

    date = datetime.now().strftime("%Y-%m-%d")
    folder = out_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"antalyahurses_sigara_{date}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    for line in skipped:
        print(f"Skipped, price not readable: {line}")
    print(f"Written: {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()