import csv
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

from datetime import datetime

BASE = "https://sehzadeonline.com"
SITEMAP_URL = f"{BASE}/sitemap"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProductScraper/1.0; +https://example.com/bot)",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

PRICE_RE = re.compile(r"₺\s*([\d]+(?:[.,]\d+)?)")
PAGE_RE = re.compile(r"(?:\?|&)sayfa=(\d+)")


@dataclass(frozen=True)
class Product:
    name: str
    price: str  # keep as string like "91.20"


def normalize_price(p: str) -> str:
    p = p.strip().replace(" ", "")
    p = p.replace(",", ".")
    return p


def with_page(url: str, page: int) -> str:
    """Return url with sayfa=page (preserving other params)."""
    u = urlparse(url)
    q = parse_qs(u.query)
    if page <= 1:
        q.pop("sayfa", None)
    else:
        q["sayfa"] = [str(page)]
    new_query = urlencode(q, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def extract_category_urls(soup: BeautifulSoup) -> List[str]:
    """
    Sitemap HTML'den kategori linklerini yakala.
    Kategori URL formatı: ...-c-<id> (ör: /manav-c-1)
    """
    cats: Set[str] = set()
    for a in soup.select('a[href]'):
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(BASE, href)
        # kategori sayfaları genelde "-c-" içeriyor
        if "-c-" in abs_url and abs_url.startswith(BASE):
            cats.add(abs_url.split("#")[0])
    return sorted(cats)


def find_last_page(soup: BeautifulSoup) -> int:
    """
    Sayfadaki sayfa linklerinden max sayfayı bul.
    Linkler: ?sayfa=2 gibi.
    """
    pages = []
    for a in soup.select('a[href*="sayfa="]'):
        href = a.get("href", "")
        m = re.search(r"sayfa=(\d+)", href)
        if m:
            pages.append(int(m.group(1)))
    return max(pages) if pages else 1


def climb_to_product_container(a: Tag, max_up: int = 6) -> Optional[Tag]:
    """
    Ürün kartını yakalamak için yukarı tırman:
    kart içinde 'Sepete Ekle' metni bulunuyor.
    """
    cur: Optional[Tag] = a
    for _ in range(max_up):
        if cur is None or not isinstance(cur, Tag):
            return None
        txt = cur.get_text(" ", strip=True)
        if "Sepete Ekle" in txt:
            return cur
        cur = cur.parent
    return None


def extract_products_from_listing(soup: BeautifulSoup) -> Dict[str, Product]:
    """
    Listing sayfasından ürünleri çıkar.
    Ana fikir:
      - ürün linkleri '-p-' içeriyor
      - ürün kartında 'Sepete Ekle' var
      - kart içindeki ilk "₺ içermeyen" ürün link metni = isim
      - kart içindeki son ₺ değeri = görünen fiyat (indirim varsa son fiyat)
    """
    out: Dict[str, Product] = {}

    for a in soup.select('a[href*="-p-"]'):
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(BASE, href)

        container = climb_to_product_container(a)
        if container is None:
            continue

        # isim: container içindeki ürün linklerinden ₺ içermeyen ilk metin
        name = None
        for na in container.select('a[href*="-p-"]'):
            t = na.get_text(" ", strip=True)
            if t and "₺" not in t:
                name = t
                break

        # fiyat: container metnindeki tüm ₺ değerlerinden sonuncusu
        txt = container.get_text(" ", strip=True)
        prices = PRICE_RE.findall(txt)
        if not name or not prices:
            continue

        price = normalize_price(prices[-1])
        # aynı ürün birden çok kez yakalanırsa (isim linki + fiyat linki), tekilleştir
        out[abs_url] = Product(name=name, price=price)

    return out


def scrape_all_products(output_csv: str = "sehzade_products.csv", delay_s: float = 0.35) -> None:
    session = requests.Session()

    sitemap_soup = get_soup(session, SITEMAP_URL)
    category_urls = extract_category_urls(sitemap_soup)

    all_products: Dict[str, Product] = {}

    for ci, cat_url in enumerate(category_urls, start=1):
        first_soup = get_soup(session, cat_url)
        last_page = find_last_page(first_soup)

        # page 1
        all_products.update(extract_products_from_listing(first_soup))
        time.sleep(delay_s)

        # pages 2..N
        for p in range(2, last_page + 1):
            page_url = with_page(cat_url, p)
            soup = get_soup(session, page_url)
            all_products.update(extract_products_from_listing(soup))
            time.sleep(delay_s)

        print(f"[{ci}/{len(category_urls)}] {cat_url} -> pages:{last_page} | total_products:{len(all_products)}")

    # CSV yaz
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["isim", "fiyat"])
        for prod in all_products.values():
            w.writerow([prod.name, prod.price])

    print(f"\nBitti. CSV: {output_csv} | Ürün sayısı: {len(all_products)}")


if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"sehzade_products_{today_str}.csv"
    scrape_all_products(filename)