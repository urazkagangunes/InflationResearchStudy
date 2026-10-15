"""Alcohol prices from PiyasaDetay's price list pages.

The site has one page per category (whisky, raki, vodka, beer, wine, tequila,
gin, liqueur, rum), each with a Marka / Urun / Hacim / Guncel fiyat table.

Output: piyasadetay_YYYY-MM-DD.csv with product_name, price, volume,
category. Inside the repo it goes to the data folder that mirrors this code
folder (InflationItems/Datas/02_Alcohol_Tobacco/PiyasaDetay); run anywhere
else, it goes to the current folder.
"""

import csv
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://piyasadetay.com/alkol-fiyatlari/"
CATEGORIES = {
    "viski-fiyatlari": "Viski",
    "raki-fiyatlari": "Rakı",
    "votka-fiyatlari": "Votka",
    "bira-fiyatlari": "Bira",
    "sarap-fiyatlari": "Şarap",
    "tekila-fiyatlari": "Tekila",
    "cin-fiyatlari": "Cin",
    "likor-fiyatlari": "Likör",
    "rom-fiyatlari": "Rom",
}
FIELDS = ["product_name", "price", "volume", "category"]


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.split(os.sep)
    if "InflationItems" not in parts:
        return os.getcwd()
    root = parts.index("InflationItems")
    return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])


def parse_price(text):
    # "1.150 TL", "132,50 TL" -> float
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", text)
    values = [float(n.replace(".", "").replace(",", ".")) for n in numbers]
    return round(sum(values) / len(values), 2) if values else None


def find_col(header, *keys):
    for i, h in enumerate(header):
        if any(k in h.lower() for k in keys):
            return i
    return None


def scrape_category(slug, category):
    url = BASE + slug + "/"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
        brand_i = find_col(header, "marka")
        product_i = find_col(header, "ürün")
        volume_i = find_col(header, "hacim")
        price_i = find_col(header, "güncel")
        # Skip other tables on the page (e.g. the 5-year history table)
        if None in (brand_i, volume_i, price_i):
            continue

        for tr in trs[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= max(brand_i, volume_i, price_i):
                continue
            product = cells[product_i] if product_i is not None else ""
            rows.append((cells[brand_i], product, cells[volume_i],
                         cells[price_i], category))
    return rows


def main():
    raw = []
    for slug, category in CATEGORIES.items():
        try:
            found = scrape_category(slug, category)
        except requests.RequestException as e:
            print(f"Skipped category {category}: {e}")
            continue
        print(f"{category}: {len(found)} rows")
        raw.extend(found)
        time.sleep(1)  # be polite to the site

    rows, skipped = [], []
    for brand, product, volume, price_text, category in raw:
        price = parse_price(price_text)
        if price is None:
            skipped.append(f"{brand} {product} {volume}: {price_text}")
            continue
        # The same product comes in several volumes, so the volume is part of the name
        product_name = " ".join(f"{brand} {product} {volume}".split())
        rows.append((product_name, price, volume, category))

    if not rows:
        print("No prices found; CSV not written.")
        sys.exit(1)

    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    folder = out_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"piyasadetay_{date}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    for line in skipped:
        print(f"Skipped, price not readable: {line}")
    print(f"Written: {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()