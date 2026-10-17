"""
Loya Makina daily price scraper.
Site: https://www.loyamakina.com (T-Soft)

The site moved to a new theme, so the old Selenium selectors found nothing
(4 Oct came out empty). The category pages are plain HTML: each product card is
div[data-toggle="product"], the selling price is span[data-toggle="price-sell-vat"],
and ?pg=N pages the list. Past the last page no new product appears.

Output: InflationItems/Datas/05_Furnishings/ConstructionSuppliesMarkets/
        LoyaMakina/loya_urunler_YYYY-MM-DD.csv
        (product_name, price, category_number, sub_category_number)

Usage:
    python loya-scraper.py
"""

import csv
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "coicop").is_dir())))
import coicop  # noqa: E402

BASE_URL = "https://www.loyamakina.com"
# Top-level categories; together they hold every product. The menu's other
# links are subcategories of these, except oto-aksesuar (checked 11 Oct 2026).
ANA_KATEGORILER = [
    "utu-grubu",
    "ev-ve-yasam",
    "hirdavat-el-aletleri",
    "bahce-camping",
    "isitma-sogutma",
    "raflar-ve-dolaplar",
    "oto-aksesuar",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}
DELAY_RANGE = (0.5, 1.5)
MAX_PAGES = 300
ATTEMPTS = 3

# The data folder mirrors this code folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_parcalar = os.path.dirname(os.path.abspath(__file__)).split(os.sep)
_kok = _parcalar.index("InflationItems")
VERI_KLASORU = os.sep.join(_parcalar[:_kok + 1] + ["Datas"] + _parcalar[_kok + 2:])


def sayfa_getir(session, url, params):
    """Page text, "" for 404 (the site's answer past the last page), None on failure."""
    for deneme in range(ATTEMPTS):
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
            print(f"  status {r.status_code}: {url} {params}")
        except requests.RequestException as e:
            print(f"  hata: {url} {params}: {e}")
        time.sleep(5 * (deneme + 1))
    return None


def fiyat_oku(metin):
    try:
        return float(metin.strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def urunleri_ayikla(html):
    soup = BeautifulSoup(html, "lxml")
    urunler = []
    for kart in soup.select('div[data-toggle="product"]'):
        link = kart.select_one('a[data-toggle="product-url"]')
        fiyat = kart.select_one('span[data-toggle="price-sell-vat"]')
        if not link or not fiyat:
            continue
        isim = (link.get("title") or "").strip()
        deger = fiyat_oku(fiyat.get_text())
        if isim and deger:
            urunler.append({
                "id": kart.get("data-id"),
                "product_name": isim,
                "price": deger,
                "link": BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
            })
    return urunler


def kategori_tara(session, kategori):
    bulunan = {}
    for pg in range(1, MAX_PAGES + 1):
        html = sayfa_getir(session, f"{BASE_URL}/{kategori}", {"pg": pg})
        if html is None or (html == "" and pg == 1):
            return None
        if html == "":
            break
        yeni =[u for u in urunleri_ayikla(html) if u["id"] not in bulunan]
        if not yeni:
            break
        for u in yeni:
            u["kategori"] = kategori
            bulunan[u["id"]] = u
        print(f"[{kategori}] sayfa {pg}: +{len(yeni)} (toplam {len(bulunan)})")
        time.sleep(random.uniform(*DELAY_RANGE))
    else:
        print(f"[{kategori}] {MAX_PAGES} sayfada bitmedi")
        return None
    return bulunan


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    tum_urunler, basarisiz = {}, []
    for kategori in ANA_KATEGORILER:
        bulunan = kategori_tara(session, kategori)
        if not bulunan:
            basarisiz.append(kategori)
            continue
        for urun_id, urun in bulunan.items():
            tum_urunler.setdefault(urun_id, urun)

    # A partial day must not look like a complete one.
    if basarisiz:
        print(f"Eksik kategori, CSV yazılmadı: {', '.join(basarisiz)}")
        sys.exit(1)

    os.makedirs(VERI_KLASORU, exist_ok=True)
    dosya = os.path.join(VERI_KLASORU, f"loya_urunler_{datetime.now():%Y-%m-%d}.csv")
    with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(coicop.FIELDS)
        writer.writerows(coicop.row(u["product_name"], u["price"], u["kategori"], "LoyaMakina")
                         for u in tum_urunler.values())
    print(f"Kaydedildi: {len(tum_urunler)} ürün -> {dosya}")


if __name__ == "__main__":
    main()
