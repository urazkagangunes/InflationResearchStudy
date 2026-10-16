"""Cigarette prices from a Rize Takip daily "güncel sigara fiyatları" article.

The article is plain text, one product per line ("MARLBORO EDGE: 123 TL"),
grouped under company headings. It is a new article with a new link every day,
so pass the link as an argument or change DEFAULT_URL.

Output: rizetakip_sigara_YYYY-MM-DD.csv with product_name, price,
category_number, sub_category_number (COICOP). Cigarettes get 0230101; the
loose rolling tobacco lines have no code and get 0. Inside the repo it goes to
the data folder that mirrors this code folder
(InflationItems/Datas/02_Alcohol_Tobacco/RizeTakip); run anywhere else, it
goes to the current folder.
"""

import csv
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = ("https://rizetakip.com/Haber/guncel-zamli-sigara-fiyatlari-"
               "14-ekim-2026-carsamba-parliament-marlboro-camel-winston-54323")
FIELDS = ["product_name", "price", "category_number", "sub_category_number"]

CATEGORY_NUMBER = "02"  # Alkollü içecekler ve tütün
CIGARETTE_CODE = "0230101"
NO_CODE = "0"
# "PARLIAMENT MIDNIGHT: 140 TL" -> name, price
LINE = re.compile(r"^(.+?):\s*(\d[\d.,]*)\s*TL\b", re.IGNORECASE)


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.split(os.sep)
    if "InflationItems" not in parts:
        return os.getcwd()
    root = parts.index("InflationItems")
    return os.sep.join(parts[:root + 1] + ["Datas"] + parts[root + 2:])


def parse_price(text):
    # "140", "1.050", "132,50" -> float
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", text)
    values = [float(n.replace(".", "").replace(",", ".")) for n in numbers]
    return round(sum(values) / len(values), 2) if values else None


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
    for line in soup.get_text("\n").splitlines():
        line = " ".join(line.replace("\xa0", " ").split())
        m = LINE.match(line)
        if m:
            rows.append((m.group(1).strip(), m.group(2)))
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

    no_code = [r[0] for r in rows if r[3] == NO_CODE]
    for name in no_code:
        print(f"No COICOP code for '{name}', written with 0")

    date = datetime.now().strftime("%Y-%m-%d")
    folder = out_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"rizetakip_sigara_{date}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    for line in skipped:
        print(f"Skipped, price not readable: {line}")
    print(f"Written: {len(rows)} products -> {path}")


if __name__ == "__main__":
    main()