"""Alcohol prices from Karekod Blog's Metro price list page.

One table per category (beer, whisky, vodka, gin, raki, tequila). The quick
summary table at the top repeats products from the category tables, so it
is skipped.

Output: karekod_metro_YYYY-MM-DD.csv with product_name, price,
category_number, sub_category_number (COICOP). Categories without a COICOP
code get 0. Inside the repo it goes to the data folder that mirrors this code
folder (InflationItems/Datas/02_Alcohol_Tobacco/KarekodMetro); run anywhere
else, it goes to the current folder.
"""

import csv
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://www.karekod.org/blog/metro-alkol-fiyatlari/"
FIELDS = ["product_name", "price", "category_number", "sub_category_number"]

CATEGORY_NUMBER = "02"  # Alkollü içecekler ve tütün
# (words in the category name, COICOP code)
SUB_CATEGORIES = [
    (("rakı", "raki"), "0211001"),
    (("votka",), "0211002"),
    (("viski", "whisky"), "0211006"),
    (("şarap", "sarap"), "0212101"),
    (("bira",), "0213001"),
]


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.split(os.sep)
    if "InflationItems" not in parts:
        return os.getcwd()
    root = parts.index("InflationItems")
    return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])


def parse_price(text):
    # "1.375 TL", "132,50 TL" and "123 TL + 2 TL depozito" (the deposit is
    # refunded, so it is not counted)
    text = text.split("+")[0]
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", text)
    values = [float(n.replace(".", "").replace(",", ".")) for n in numbers]
    return round(sum(values) / len(values), 2) if values else None


def find_col(header, key):
    for i, h in enumerate(header):
        if key in h.lower():
            return i
    return None


def to_coicop(rows):
    out, unmapped = [], {}
    for product_name, price, volume, category in rows:
        code = next((c for keys, c in SUB_CATEGORIES
                     if any(k in category.lower() for k in keys)), None)
        if code is None:
            code = "0"  # no COICOP code for this category yet
            unmapped[category] = unmapped.get(category, 0) + 1
        out.append((product_name, price, CATEGORY_NUMBER, code))
    return out, unmapped


def scrape():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
        price_i = find_col(header, "fiyat")
        volume_i = find_col(header, "hacim")  # the beer table has no volume column
        # The summary table starts with "Ürün"; category tables start with the category
        if price_i is None or header[0].lower() == "ürün":
            continue
        category = header[0]

        for tr in trs[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= price_i:
                continue
            volume = cells[volume_i] if volume_i is not None else ""
            rows.append((cells[0], volume, cells[price_i], category))
    return rows


def main():
    raw = scrape()
    rows, skipped = [], []
    for name, volume, price_text, category in raw:
        price = parse_price(price_text)
        if price is None:
            skipped.append(f"{name} {volume}: {price_text}")
            continue
        # The same product comes in several volumes, so the volume is part of the name
        product_name = " ".join(f"{name} {volume}".split())
        rows.append((product_name, price, volume, category))

    rows, unmapped = to_coicop(rows)
    for category, count in unmapped.items():
        print(f"No COICOP code for '{category}', {count} rows written with 0")

    if not rows:
        print("No prices found; CSV not written.")
        sys.exit(1)

    date = datetime.now().strftime("%Y-%m-%d")
    folder = out_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"karekod_metro_{date}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    for line in skipped:
        print(f"Skipped, price not readable: {line}")
    print(f"Written: {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()