import csv
import os
import re
import time
from datetime import datetime
from typing import List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://www.loft.com.tr"
LISTING_URL = f"{BASE_URL}/c/tumurunler-1"

PRICE_RE = re.compile(r"((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})\s*TL", re.IGNORECASE)
TOTAL_COUNT_RE = re.compile(r"(\d+)\s+ürün\s+bulundu", re.IGNORECASE)
VISIBLE_COUNT_RE = re.compile(
    r"(\d+)\s+üründen\s+(\d+)\s+tanesini\s+görüntüledin",
    re.IGNORECASE
)


def repo_root() -> str:
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )


def clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def normalize_price(price_str: str) -> str:
    return price_str.replace(".", "").strip()


def infer_category(product_name: str) -> str:
    lowered = product_name.lower()
    if "kadın" in lowered:
        return "Women"
    if "erkek" in lowered:
        return "Men"
    return "Other"


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def build_page_url(page_number: int) -> str:
    if page_number <= 1:
        return LISTING_URL
    return f"{LISTING_URL}?pagenumber={page_number}"


def extract_total_pages(soup: BeautifulSoup) -> int:
    text = clean_text(soup.get_text(" ", strip=True))

    total_products = None
    shown_per_page = None

    total_match = TOTAL_COUNT_RE.search(text)
    if total_match:
        try:
            total_products = int(total_match.group(1))
        except ValueError:
            total_products = None

    visible_match = VISIBLE_COUNT_RE.search(text)
    if visible_match:
        try:
            shown_per_page = int(visible_match.group(2))
        except ValueError:
            shown_per_page = None

    if total_products and shown_per_page and shown_per_page > 0:
        return (total_products + shown_per_page - 1) // shown_per_page

    return 1


def make_absolute_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return BASE_URL + href


def get_text_container_from_product_anchor(anchor: Tag) -> Optional[Tag]:
    parent = anchor.parent
    if isinstance(parent, Tag):
        classes = parent.get("class", [])
        if "productWrapper" in classes and "product-text-container" in classes:
            return parent
    return None


def extract_name_from_container(container: Tag) -> Optional[str]:
    full_text = clean_text(container.get_text(" ", strip=True))
    if not full_text:
        return None

    price_match = PRICE_RE.search(full_text)
    if price_match:
        name = clean_text(full_text[:price_match.start()])
        if name:
            return name

    for child in container.find_all(["div", "span", "p", "a", "h2", "h3", "h4"]):
        child_text = clean_text(child.get_text(" ", strip=True))
        if not child_text:
            continue
        if PRICE_RE.search(child_text):
            continue
        lowered = child_text.lower()
        if "sepette" in lowered or "kazancınız" in lowered:
            continue
        if len(child_text) >= 4:
            return child_text

    return None


def extract_original_price_from_container(container: Tag) -> Optional[str]:
    text = clean_text(container.get_text(" ", strip=True))
    # Remove "Kazancınız X TL" (savings amount, not a real price)
    idx = text.lower().find("kazancınız")
    if idx != -1:
        text = text[:idx]
    prices = PRICE_RE.findall(text)
    if not prices:
        return None
    # Last price = cheapest available (sepette price if exists, else discounted, else normal)
    return normalize_price(prices[-1])


def parse_products_from_page(soup: BeautifulSoup) -> List[Tuple[str, str, str, str]]:
    rows: List[Tuple[str, str, str, str]] = []
    seen_urls_on_page: Set[str] = set()

    anchors = soup.select('a[href*="/p/"]')

    for anchor in anchors:
        href = anchor.get("href", "").strip()
        if not href:
            continue

        product_url = make_absolute_url(href)

        if product_url in seen_urls_on_page:
            continue

        container = get_text_container_from_product_anchor(anchor)
        if container is None:
            continue

        name = extract_name_from_container(container)
        price = extract_original_price_from_container(container)

        if not name or not price:
            continue

        category = infer_category(name)
        rows.append((category, name, price, product_url))
        seen_urls_on_page.add(product_url)

    return rows


def scrape_all_products(session: requests.Session, delay_sec: float = 0.35) -> List[Tuple[str, str, str, str]]:
    first_soup = fetch_soup(session, LISTING_URL)
    total_pages = extract_total_pages(first_soup)

    print(f"Detected total pages: {total_pages}")

    all_rows: List[Tuple[str, str, str, str]] = []
    seen_global_urls: Set[str] = set()

    for page in range(1, total_pages + 1):
        page_url = build_page_url(page)
        print(f"Scraping page {page}/{total_pages} -> {page_url}")

        try:
            soup = fetch_soup(session, page_url)
            rows = parse_products_from_page(soup)
            print(f"Page {page}: {len(rows)} rows")

            if page > 1 and not rows:
                print(f"Page {page} returned 0 rows, stopping early")
                break

            for category, name, price, product_url in rows:
                if product_url in seen_global_urls:
                    continue
                seen_global_urls.add(product_url)
                all_rows.append((category, name, price, product_url))

            time.sleep(delay_sec)

        except Exception as exc:
            print(f"Failed on page {page}: {exc}")

    return all_rows


def main() -> None:
    session = requests.Session()
    final_rows = scrape_all_products(session)

    out_dir = os.path.join(repo_root(), "Datas", "ClothingStores", "Loft")
    os.makedirs(out_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"loft_{today}.csv")

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Product Name", "Price", "Product URL"])
        writer.writerows(final_rows)

    print(f"Done. Unique rows written: {len(final_rows)}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()