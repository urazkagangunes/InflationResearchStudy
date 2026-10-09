import csv
import os
import re
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


URLS = [
    "https://www.nalburdayim.com/boya/",
    "https://www.nalburdayim.com/banyo-mutfak/",
    "https://www.nalburdayim.com/elektrikli-el/",
    "https://www.nalburdayim.com/hirdavat-malzemeleri/",
    "https://www.nalburdayim.com/is-guvenligi-malzemeleri/",
    "https://www.nalburdayim.com/elektrik-ve-aydinlatma/",
    "https://www.nalburdayim.com/yapi-kimyasallari/",
    "https://www.nalburdayim.com/insaat-malzemeleri/",
    "https://www.nalburdayim.com/kirtasiye-malzemeleri-533/",
    "https://www.nalburdayim.com/tesisat-malzemeleri/",
    "https://www.nalburdayim.com/ev-gerecleri/",
    "https://www.nalburdayim.com/bahce/",
    "https://www.nalburdayim.com/temizlik-malzemeleri/",
    "https://www.nalburdayim.com/mobilya/",
    "https://www.nalburdayim.com/cop-kovasi/",
]

REQUEST_DELAY_SEC = 1.2
MAX_PAGES_PER_CATEGORY = 0  # 0 = no limit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "Datas", "ConstructionSuppliesMarkets", "Nalburdayim")
)


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _parse_price_to_float(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = text.replace("TL", "").replace("₺", "").strip()
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _slug_to_category(slug: str) -> str:
    slug = slug.strip().strip("/")
    slug = re.sub(r"-\d+$", "", slug)
    words = [w for w in slug.split("-") if w]
    if not words:
        return slug
    return " ".join(word.capitalize() for word in words)


def _category_from_url(url: str) -> str:
    path = urlparse(url).path
    slug = path.strip("/").split("/")[-1]
    return _slug_to_category(slug)


def _find_category_title(soup: BeautifulSoup, fallback: str) -> str:
    selectors = [
        "h1",
        ".page-title h1",
        ".page-title",
        ".breadcrumb-container .active",
        ".breadcrumb-container li:last-child",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            return _normalize_whitespace(node.get_text())
    return fallback


def _page_number_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"\b(\d{1,4})\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _page_number_from_url(url: str) -> Optional[int]:
    if not url:
        return None
    for pattern in (r"[?&](?:page|sayfa|p|pg|i)=(\d+)", r"/page/(\d+)"):
        match = re.search(pattern, url, re.I)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _pagination_links(soup: BeautifulSoup, base_url: str) -> Dict[int, str]:
    links: Dict[int, str] = {}
    containers = soup.select("ul.pagination, nav.pagination, div.pagination")
    if not containers:
        containers = [soup]
    for container in containers:
        for link in container.find_all("a", href=True):
            href = link.get("href")
            if not href:
                continue
            page_num = None
            if link.has_attr("data-page"):
                try:
                    page_num = int(link["data-page"])
                except ValueError:
                    page_num = None
            if page_num is None:
                page_num = _page_number_from_text(link.get_text(strip=True))
            if page_num is None:
                page_num = _page_number_from_url(href)
            if page_num is None:
                continue
            links[page_num] = urljoin(base_url, href)
    return links


def _current_page_from_soup(soup: BeautifulSoup) -> Optional[int]:
    current = soup.select_one(
        "ul.pagination .active, ul.pagination .current, ul.pagination [aria-current='page']"
    )
    if current:
        if current.has_attr("data-page"):
            try:
                return int(current["data-page"])
            except ValueError:
                pass
        text = current.get_text(strip=True)
        num = _page_number_from_text(text)
        if num is not None:
            return num
    return None


def _find_next_page(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    next_link = soup.find("a", attrs={"rel": "next"})
    if not next_link:
        next_link = soup.find("a", attrs={"title": re.compile(r"sonraki", re.I)})
    if not next_link:
        next_link = soup.find("a", attrs={"aria-label": re.compile(r"sonraki|next", re.I)})
    if not next_link:
        next_link = soup.find("a", string=re.compile(r"sonraki|next", re.I))
    if not next_link:
        next_link = soup.select_one("ul.pagination a.next, ul.pagination li.next a")
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    page_links = _pagination_links(soup, current_url)
    if not page_links:
        return None
    current_page = _current_page_from_soup(soup)
    if current_page is None:
        current_page = _page_number_from_url(current_url) or 1
    candidates = sorted(p for p in page_links.keys() if p > current_page)
    if not candidates:
        return None
    return page_links[candidates[0]]


def _extract_products(soup: BeautifulSoup, category: str) -> List[Dict[str, str]]:
    products: List[Dict[str, str]] = []
    cards = soup.select("article.art, article[data-id]")
    for card in cards:
        name_node = card.select_one("span.art-name span, span.art-name a, span.art-name")
        brand_node = card.select_one("div.art-brand span, div.art-brand")
        price_node = card.select_one("span.art-price-value, span.art-finalprice")

        name = _normalize_whitespace(name_node.get_text()) if name_node else ""
        brand = _normalize_whitespace(brand_node.get_text()) if brand_node else ""
        price_value = _parse_price_to_float(price_node.get_text()) if price_node else None

        if not name or price_value is None:
            continue

        products.append(
            {
                "Category": category,
                "Brand": brand,
                "ProductName": name,
                "Price": price_value,
            }
        )
    return products


def _dedupe_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Set[str] = set()
    unique: List[Dict[str, str]] = []
    for row in rows:
        key = f"{row.get('Category')}|{row.get('Brand')}|{row.get('ProductName')}|{row.get('Price')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def scrape_category(session: requests.Session, url: str) -> List[Dict[str, str]]:
    all_rows: List[Dict[str, str]] = []
    visited: Set[str] = set()
    page_url = url
    page_count = 0
    while page_url:
        if page_url in visited:
            break
        visited.add(page_url)
        soup = _fetch_soup(session, page_url)
        category_fallback = _category_from_url(url)
        category = _find_category_title(soup, category_fallback)
        rows = _extract_products(soup, category)
        if not rows:
            break
        all_rows.extend(rows)
        page_count += 1
        if MAX_PAGES_PER_CATEGORY and page_count >= MAX_PAGES_PER_CATEGORY:
            break
        next_url = _find_next_page(soup, page_url)
        if not next_url or next_url == page_url:
            break
        page_url = next_url
        time.sleep(REQUEST_DELAY_SEC)
    return all_rows


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = requests.Session()
    unique_urls = list(dict.fromkeys(URLS))
    all_rows: List[Dict[str, str]] = []

    for url in unique_urls:
        print(f"Scraping {url}...")
        try:
            rows = scrape_category(session, url)
        except Exception as exc:
            print(f"Failed to scrape {url}: {exc}")
            continue
        all_rows.extend(rows)
        time.sleep(REQUEST_DELAY_SEC)

    all_rows = _dedupe_rows(all_rows)
    if not all_rows:
        print("No products scraped.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"nalburdayim_{date_str}.csv")
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Category", "Brand", "ProductName", "Price"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
