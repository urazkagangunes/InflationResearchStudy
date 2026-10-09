import csv
import html
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://www.onur360.com/supermarket"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "..", "..", "Datas", "Markets", "Onur")
)
WARN_MIN_PRODUCTS = 500
#scrape products from onur360.com and save to csv. use price_fixer.py to fix prices.

def fetch_text(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def fetch_json(url: str, timeout: int = 30) -> Optional[Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            charset = resp.headers.get_content_charset() or "utf-8"
            text = resp.read().decode(charset, errors="replace")
        if "application/json" in content_type:
            return json.loads(text)
        text = text.strip()
        if text.startswith("{") or text.startswith("["):
            return json.loads(text)
    except (HTTPError, URLError, json.JSONDecodeError, ValueError):
        return None
    return None


def extract_json_script(html: str, script_id: str) -> Optional[Any]:
    pattern = rf'<script[^>]*id="{re.escape(script_id)}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.S | re.I)
    if not match:
        return None
    payload = match.group(1).strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def extract_window_json(html: str, var_name: str) -> Optional[Any]:
    pattern = rf"{re.escape(var_name)}\s*=\s*(\{{.*?\}});"
    match = re.search(pattern, html, re.S)
    if not match:
        return None
    payload = match.group(1).strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def normalize_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str):
        return parse_price_to_float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("formatted", "display", "priceText", "text"):
            if key in value:
                return normalize_price(value.get(key))
        for key in ("value", "amount", "price", "current", "sale", "final"):
            if key in value:
                return normalize_price(value.get(key))
    return None


def clean_product_name(name: str) -> str:
    cleaned = " ".join(name.split())
    cleaned = re.sub(r"\s*[-–]\s*\d{8,14}\s*$", "", cleaned)
    return cleaned.strip()


def choose_first(obj: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return None


def product_from_dict(obj: Dict[str, Any]) -> Optional[Tuple[str, str, float]]:
    name = choose_first(obj, ("productName", "name", "title", "displayName", "urunAdi"))
    if not name or not isinstance(name, str):
        return None
    name = clean_product_name(name)
    brand = choose_first(obj, ("brand", "brandName", "manufacturer", "marka"))
    if isinstance(brand, dict):
        brand = choose_first(brand, ("name", "title"))
    if not isinstance(brand, str):
        brand = ""
    price = choose_first(obj, ("price", "currentPrice", "salePrice", "finalPrice", "urunFiyat"))
    price_value = normalize_price(price)
    if price_value is None:
        return None
    return (brand.strip(), name.strip(), price_value)


def extract_products_from_data(data: Any) -> List[Tuple[str, str, float]]:
    found: List[Tuple[str, str, float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            product = product_from_dict(node)
            if product:
                found.append(product)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def extract_candidate_urls(html: str) -> List[str]:
    urls = set(re.findall(r'https?://[^\s"\'<>]+', html))
    candidates: List[str] = []
    for url in urls:
        lower = url.lower()
        if any(key in lower for key in ("api", "product", "urun", "catalog", "search", "listing")):
            candidates.append(url)
    return candidates


def parse_price_to_float(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = html.unescape(text).strip()
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").strip()
    match = re.search(r"[\d\.,]+", cleaned)
    if not match:
        return None
    value = match.group(0)
    # Turkish formatting: thousands '.' and decimal ','.
    value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def extract_brand_from_block(block: str, name: str) -> str:
    patterns = [
        r'data-brand="([^"]+)"',
        r'class="productBrand"[^>]*>\s*([^<]+)',
        r'class="brand"[^>]*>\s*([^<]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, block, re.I)
        if match:
            brand = html.unescape(match.group(1)).strip()
            if brand:
                return brand
    # Fallback: use the first token from the product name.
    return name.split(" ")[0].strip()


def extract_price_from_block(block: str) -> Optional[float]:
    patterns = [
        r'class="discountPriceSpan"[^>]*>\s*([^<]+)',
        r'class="discountPrice"[^>]*>\s*([^<]+)',
        r'class="newPriceSpan"[^>]*>\s*([^<]+)',
        r'class="newPrice"[^>]*>\s*([^<]+)',
        r'class="productPrice"[^>]*>\s*([^<]+)',
        r'itemprop="price"[^>]*content="([^"]+)"',
        r'data-price="([^"]+)"',
        r'data-product-price="([^"]+)"',
        r'data-lastprice="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, block, re.I | re.S)
        if match:
            price = parse_price_to_float(match.group(1))
            if price:
                return price
    # Last fallback: pick the first currency-like token in the block.
    match = re.search(r"₺\s*[\d\.,]+", block)
    if match:
        return parse_price_to_float(match.group(0))
    return None


def extract_products_from_html(page_html: str) -> List[Tuple[str, str, float]]:
    products: List[Tuple[str, str, float]] = []
    starts = [m.start() for m in re.finditer(r'<div class="productItem\b', page_html, re.I)]
    if not starts:
        return products
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(page_html)
        block = page_html[start:end]
        name = None
        name_patterns = [
            r'<div class="productName[^"]*">\s*<a[^>]*title="([^"]+)"',
            r'<a[^>]*title="([^"]+)"',
            r'<div class="productName[^"]*">\s*<a[^>]*>\s*([^<]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, block, re.I | re.S)
            if match:
                name = clean_product_name(html.unescape(match.group(1)).strip())
                if name:
                    break
        if not name:
            continue
        if not name:
            continue
        price = extract_price_from_block(block)
        if not price:
            continue
        brand = extract_brand_from_block(block, name)
        products.append((brand, name, price))
    return products


def extract_total_pages(page_html: str) -> Optional[int]:
    candidates: List[int] = []
    patterns = [
        r"totalPages\s*[:=]\s*(\d+)",
        r"data-totalpages\s*=\s*\"(\d+)\"",
        r"pageCount\s*[:=]\s*(\d+)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, page_html, re.I):
            try:
                candidates.append(int(match))
            except ValueError:
                continue
    for match in re.findall(r"[?&](?:sayfa|page)=(\d+)", page_html, re.I):
        try:
            candidates.append(int(match))
        except ValueError:
            continue
    if not candidates:
        return None
    return max(candidates)


def build_page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    separator = "&" if "?" in BASE_URL else "?"
    return f"{BASE_URL}{separator}sayfa={page}"


def paginate_html_products(first_html: str, max_pages: int = 200) -> List[Tuple[str, str, float]]:
    total_pages = extract_total_pages(first_html)
    if total_pages is None:
        total_pages = max_pages
    else:
        total_pages = min(total_pages, max_pages)

    products: List[Tuple[str, str, float]] = []
    empty_pages = 0
    for page in range(1, total_pages + 1):
        html_page = first_html if page == 1 else fetch_text(build_page_url(page))
        page_products = extract_products_from_html(html_page)
        if not page_products:
            empty_pages += 1
        else:
            empty_pages = 0
            products.extend(page_products)
        if empty_pages >= 2:
            break
    return products


def dedupe_products(items: List[Tuple[str, str, float]]) -> List[Tuple[str, str, float]]:
    seen: Set[Tuple[str, str, float]] = set()
    out: List[Tuple[str, str, float]] = []
    for item in items:
        key = (item[0], item[1], item[2])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def scrape_products() -> List[Tuple[str, str, float]]:
    html = fetch_text(BASE_URL)

    data_sources: List[Any] = []
    for script_id in ("__NEXT_DATA__", "initial-state"):
        data = extract_json_script(html, script_id)
        if data is not None:
            data_sources.append(data)

    for var_name in ("window.__INITIAL_STATE__", "window.__NUXT__"):
        data = extract_window_json(html, var_name)
        if data is not None:
            data_sources.append(data)

    products: List[Tuple[str, str, float]] = []
    for data in data_sources:
        products.extend(extract_products_from_data(data))

    if len(products) < 50:
        products = extract_products_from_html(html)

    if len(products) < WARN_MIN_PRODUCTS:
        paginated = paginate_html_products(html)
        if len(paginated) > len(products):
            products = paginated

    if len(products) < 50:
        # Fallback: try JSON endpoints discovered in the HTML.
        for url in extract_candidate_urls(html):
            data = fetch_json(url)
            if data is None:
                continue
            candidates = extract_products_from_data(data)
            if len(candidates) > len(products):
                products = candidates
            if len(products) >= 900:
                break

    products = dedupe_products(products)
    if not products:
        raise RuntimeError("Could not extract any products from the page.")
    if len(products) < WARN_MIN_PRODUCTS:
        print(f"Warning: only {len(products)} products extracted from the page.")
    return products


def output_path(scrape_date: Optional[str]) -> str:
    if scrape_date:
        date_str = scrape_date
    else:
        date_str = datetime.now().strftime("%d.%m.%Y")
    return f"{OUTPUT_DIR}\\onur_{date_str}.csv"


def write_csv(rows: List[Tuple[str, str, float]], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Brand", "productName", "Price"])
        writer.writerows(rows)


def main() -> None:
    scrape_date = None
    if len(sys.argv) > 1:
        scrape_date = sys.argv[1].strip()
    products = scrape_products()
    path = output_path(scrape_date)
    write_csv(products, path)
    print(f"Saved {len(products)} products to {path}")


if __name__ == "__main__":
    main()
