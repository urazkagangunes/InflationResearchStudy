import os
import re
import csv
from datetime import datetime
from typing import Optional, List, Tuple

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://basdasonline.com"
LIST_URL = f"{BASE_URL}/tab-lists.asp"

TODAY = datetime.now().strftime("%Y-%m-%d")
CSV_PATH = f"basdas_{TODAY}.csv"

HEADERS = ["tarih", "grup_id", "urun_adi", "fiyat"]

_price_clean_re = re.compile(r"[^\d,\.]")


def parse_price(text: str) -> Optional[float]:
    if not text:
        return None

    t = _price_clean_re.sub("", text.strip())

    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")

    try:
        return float(t)
    except ValueError:
        return None


def parse_products(html: str) -> List[Tuple[str, float]]:
    soup = BeautifulSoup(html, "html.parser")
    products: List[Tuple[str, float]] = []

    cards = soup.select(".urun-kutusu")

    for card in cards:
        name_el = card.select_one("h2 a.kutu-link")
        price_el = card.select_one("div.urun-fiyat span")

        if not name_el or not price_el:
            continue

        name = name_el.get_text(strip=True)
        price = parse_price(price_el.get_text(strip=True))

        if name and price is not None:
            products.append((name, price))

    return products


def load_existing_keys() -> set:
    existing = set()

    if not os.path.exists(CSV_PATH):
        return existing

    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header'ı geç

        for row in reader:
            if len(row) < 3:
                continue
            existing.add((row[0], row[1], row[2]))

    return existing


def append_rows(rows: List[Tuple[str, int, str, float]]) -> None:
    if not rows:
        return

    existing = load_existing_keys()
    file_exists = os.path.exists(CSV_PATH)

    new_count = 0

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(HEADERS)

        for r in rows:
            key = (str(r[0]), str(r[1]), str(r[2]))

            if key not in existing:
                writer.writerow(r)
                existing.add(key)
                new_count += 1

    print(f"Yeni eklenen satır: {new_count}")


def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL + "/",
        "Origin": BASE_URL,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })

    # Siteye ilk giriş
    s.get(BASE_URL + "/", timeout=20)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows: List[Tuple[str, int, str, float]] = []

    for gid in range(0, 101):
        try:
            r = s.post(LIST_URL, data={"grupID": str(gid)}, timeout=25)
            r.encoding = "utf-8"

            products = parse_products(r.text)

            if products:
                print(f"[OK] grupID={gid} → {len(products)} ürün")
                for name, price in products:
                    all_rows.append((now, gid, name, price))

        except Exception as e:
            print(f"[ERR] grupID={gid} → {e}")

    append_rows(all_rows)

    print(f"\nCSV'ye yazıldı: {CSV_PATH}")
    print(f"Toplam bulunan satır: {len(all_rows)}")


if __name__ == "__main__":
    main()
