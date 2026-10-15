"""Alcohol prices from Aydın Havadisleri's price list page.

The page lists retail prices in tables: beer, raki, wine, vodka, gin, rum and
whisky, one table per heading.

Output: aydinhavadisleri_YYYY-MM-DD.csv with product_name, price, volume,
category. Inside the repo it goes to the data folder that mirrors this code
folder (InflationItems/Datas/02_Alcohol_Tobacco/AydinHavadisleri); run
anywhere else, it goes to the current folder.
"""

import csv
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://aydinhavadisleri.com/alkol-fiyatlari/"
FIELDS = ["product_name", "price", "volume", "category"]


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.split(os.sep)
    if "InflationItems" not in parts:
        return os.getcwd()
    root = parts.index("InflationItems")
    return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])


def parse_price(text):
    # "125 TL", "132,50 TL", "1.039-1.050 TL" (a range: its midpoint) and
    # "123 TL + 2 TL depozito" (the deposit is refunded, so it is not counted)
    text = text.split("+")[0]
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", text)
    values = [float(n.replace(".", "").replace(",", ".")) for n in numbers]
    return round(sum(values) / len(values), 2) if values else None


def scrape():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.find_all("table"):
        heading = table.find_previous(["h2", "h3"])
        category = heading.get_text(strip=True) if heading else ""
        if "lik Alkol" in category:
            continue

        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]

        for tr in trs[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            name = cells[0]
            # Three table shapes: product | volume | price, product | price with
            # the volume in the header, and product | one column per volume
            if len(cells) == 3 and header[1].lower().startswith("hacim"):
                pairs = [(cells[1], cells[2])]
            elif len(cells) == 2:
                m = re.search(r"\d+[,.]?\d*\s*cl", header[1])
                pairs = [(m.group(0) if m else "", cells[1])]
            else:
                pairs = [(vol, price) for vol, price in zip(header[1:], cells[1:])
                         if price not in ("–", "-", "")]
            for volume, price_text in pairs:
                rows.append((name, volume, price_text, category))
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

    if not rows:
        print("No prices found; CSV not written.")
        sys.exit(1)

    date = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    folder = out_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"aydinhavadisleri_{date}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    for line in skipped:
        print(f"Skipped, price not readable: {line}")
    print(f"Written: {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()
