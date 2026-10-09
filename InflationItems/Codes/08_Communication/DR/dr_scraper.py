"""
D&R technology scraper.

Scrapes D&R's technology-related catalog sections into the repo's standard
daily CSV format:

    InflationItems/Datas/TechnologicalProducts/DR/dr_YYYY-MM-DD.csv

The scraper works directly from server-rendered category pages. It discovers
approved top-level technology categories from
https://www.dr.com.tr/kategori/elektronik, adds the office-technology catalog
explicitly, paginates with ?Page=N, and deduplicates products by D&R product
id.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.dr.com.tr"
ELECTRONICS_INDEX_URL = f"{BASE_URL}/kategori/elektronik"
OFFICE_TECH_URL = f"{BASE_URL}/kategori/ofis-teknolojileri"

# The course announcement asks us to stay inside technology-related product
# categories only. We therefore keep an explicit allowlist instead of scraping
# every navigation link that may appear on the electronics landing page in the
# future.
TECH_CATEGORY_ROOTS = {
    "Ev Elektroniği": "Elektronik",
    "Tablet & PC Aksesuarları": "Elektronik",
    "Oyun & Konsol": "Elektronik",
    "Telefon Aksesuarları": "Elektronik",
    "Foto & Kamera": "Elektronik",
    "Küçük Ev Aletleri": "Elektronik",
    "Telefon": "Elektronik",
    "Giyilebilir Teknoloji": "Elektronik",
    "Isıtma ve Soğutma": "Elektronik",
    "Kişisel Bakım & Sağlık": "Elektronik",
    "Kobo E-kitap Okuyucular": "Elektronik",
    "Elektronik Diğer": "Elektronik",
    "Outdoor": "Elektronik",
}
TECH_CATEGORY_ORDER = list(TECH_CATEGORY_ROOTS)
EXCLUDED_SUBCATEGORIES = {
    "Bavul & Valiz",
    "Cricut Sarf Malzemeleri",
    "Giyotinler",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{BASE_URL}/",
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
RETRY_BACKOFF = 2.0
PAGE_DELAY = 0.25
DEFAULT_WORKERS = 4

CSV_COLUMNS = [
    "product_name",
    "price",
    "Product Original Cost",
    "Currency",
    "Product ID",
    "Variation ID",
    "Brand",
    "In Stock",
    "Campaign Label",
    "Top Category",
    "Category",
    "Subcategory",
    "Category Path",
    "Source Category",
    "Source Category URL",
    "Product URL",
    "Image URL",
]


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    url: str
    root_section: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _output_dir() -> Path:
    return _project_root() / "InflationItems" / "Datas" / "TechnologicalProducts" / "DR"


def _scrape_date_str() -> str:
    override = os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
    if override:
        return datetime.fromisoformat(override).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def _default_output_path() -> Path:
    return _output_dir() / f"dr_{_scrape_date_str()}.csv"


def _normalise_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _slugify(value: str) -> str:
    text = _normalise_text(value).lower()
    replacements = {
        "&": "and",
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    safe = []
    for char in text:
        if char.isalnum():
            safe.append(char)
        else:
            safe.append("-")
    slug = "".join(safe)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _parse_price(text: str | None) -> float | None:
    raw = _normalise_text(text)
    if not raw:
        return None
    raw = raw.replace("TL", "").replace("₺", "").replace(" ", "")
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def _fetch_html(session: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait_seconds = RETRY_BACKOFF * attempt
            logging.warning(
                "Request failed for %s on attempt %d/%d: %s. Retrying in %.1fs...",
                url,
                attempt,
                MAX_RETRIES,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def _build_page_url(category_url: str, page_number: int) -> str:
    if page_number <= 1:
        return category_url

    split = urlsplit(category_url)
    params = dict(parse_qsl(split.query, keep_blank_values=True))
    params["Page"] = str(page_number)
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(params), split.fragment)
    )


def _extract_categories_from_index(session: requests.Session) -> list[Category]:
    html = _fetch_html(session, ELECTRONICS_INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")

    discovered: dict[str, Category] = {}

    for link in soup.select("a.dr-flex-between[href]"):
        name = _normalise_text(link.get_text(" ", strip=True))
        href = link.get("href", "").strip()
        if (
            not name
            or name not in TECH_CATEGORY_ROOTS
            or not href.startswith("/kategori/")
        ):
            continue

        full_url = urljoin(BASE_URL, href)
        discovered[name] = Category(
            id=_slugify(name),
            name=name,
            url=full_url,
            root_section=TECH_CATEGORY_ROOTS[name],
        )

    categories: list[Category] = []
    for name in TECH_CATEGORY_ORDER:
        category = discovered.get(name)
        if category is None:
            logging.warning("Expected D&R technology category is missing from the index: %s", name)
            continue
        categories.append(category)

    office_category = Category(
        id="ofis-teknolojileri",
        name="Ofis Teknolojileri",
        url=OFFICE_TECH_URL,
        root_section="Kırtasiye",
    )
    categories.append(office_category)

    return categories


def _total_pages(soup: BeautifulSoup) -> int:
    pages = []
    for link in soup.select(".pagination a[data-number]"):
        number = link.get("data-number", "").strip()
        if number.isdigit():
            pages.append(int(number))

    if pages:
        return max(pages)

    return 1 if soup.select(".prd.js-prd-item") else 0


def _parse_gtm_payload(card: Any) -> dict[str, Any]:
    payload = card.get("data-gtm")
    if not payload:
        return {}

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logging.debug("Could not decode data-gtm payload for card %s", card.get("data-id"))
        return {}


def _extract_price_info(card: Any) -> tuple[float | None, float | None, str]:
    campaign = card.select_one(".campaign-price-badge")
    if campaign:
        label = _normalise_text(campaign.select_one(".campaign-label").get_text(" ", strip=True))
        old_price = _parse_price(
            campaign.select_one(".campaign-price-old").get_text(" ", strip=True)
            if campaign.select_one(".campaign-price-old")
            else ""
        )
        current_price = None
        for span in reversed(campaign.select(".campaign-price span")):
            if "campaign-price-old" in (span.get("class") or []):
                continue
            current_price = _parse_price(span.get_text(" ", strip=True))
            if current_price is not None:
                break
        if current_price is None:
            current_price = old_price
        return current_price, old_price or current_price, label

    price_el = card.select_one(".prd-price[data-price]")
    if price_el is not None:
        data_price = price_el.get("data-price", "").strip()
        try:
            value = float(data_price)
        except ValueError:
            value = _parse_price(price_el.get_text(" ", strip=True))
        return value, value, ""

    return None, None, ""


def _extract_image_url(card: Any) -> str:
    image = card.select_one("img[data-src], img[src]")
    if image is None:
        return ""
    return image.get("data-src") or image.get("src") or ""


def _extract_product_url(card: Any) -> str:
    link = card.select_one("a[href*='urunno=']")
    if link is None:
        return ""
    return urljoin(BASE_URL, link.get("href", ""))


def _extract_product_name(card: Any, gtm: dict[str, Any]) -> str:
    if _normalise_text(gtm.get("item_name")):
        return _normalise_text(str(gtm["item_name"]))

    image = card.select_one("img[alt]")
    if image is not None and _normalise_text(image.get("alt")):
        return _normalise_text(image.get("alt"))

    return _normalise_text(card.get_text(" ", strip=True))


def _category_path(root: str, category: str, subcategory: str) -> str:
    parts = [part for part in [root, category, subcategory] if _normalise_text(part)]
    return " > ".join(parts)


def _parse_card(card: Any, category: Category) -> dict[str, Any] | None:
    gtm = _parse_gtm_payload(card)
    current_price, original_price, campaign_label = _extract_price_info(card)
    product_url = _extract_product_url(card)
    product_name = _extract_product_name(card, gtm)

    product_id = (
        card.get("data-id")
        or gtm.get("item_id")
        or ""
    )
    product_id = str(product_id).strip()
    if not product_id or current_price is None or not product_name:
        return None

    stock_value = _normalise_text(str(gtm.get("item_stock", ""))).lower()
    in_stock = True
    if stock_value:
        in_stock = stock_value in {"yes", "true", "1", "var"}
    elif "stokta yok" in _normalise_text(card.get_text(" ", strip=True)).lower():
        in_stock = False

    top_category = _normalise_text(str(gtm.get("item_category", category.root_section)))
    mid_category = _normalise_text(str(gtm.get("item_category2", category.name)))
    subcategory = _normalise_text(str(gtm.get("item_category3", "")))
    if subcategory in EXCLUDED_SUBCATEGORIES:
        return None

    return {
        "product_name": product_name,
        "price": current_price,
        "Product Original Cost": original_price if original_price is not None else current_price,
        "Currency": _normalise_text(str(gtm.get("currency", "TRY"))) or "TRY",
        "Product ID": product_id,
        "Variation ID": _normalise_text(str(card.get("variationid", ""))),
        "Brand": _normalise_text(str(gtm.get("item_brand", ""))),
        "In Stock": in_stock,
        "Campaign Label": campaign_label,
        "Top Category": top_category,
        "Category": mid_category,
        "Subcategory": subcategory,
        "Category Path": _category_path(top_category, mid_category, subcategory),
        "Source Category": category.name,
        "Source Category URL": category.url,
        "Product URL": product_url,
        "Image URL": _extract_image_url(card),
    }


def _scrape_category(category: Category, page_limit: int | None = None) -> list[dict[str, Any]]:
    session = _make_session()
    products: list[dict[str, Any]] = []

    first_page_url = _build_page_url(category.url, 1)
    first_page_html = _fetch_html(session, first_page_url)
    first_page_soup = BeautifulSoup(first_page_html, "html.parser")
    total_pages = _total_pages(first_page_soup)
    if page_limit is not None:
        total_pages = min(total_pages, page_limit)

    if total_pages == 0:
        logging.warning("No product cards found for %s (%s)", category.name, category.url)
        return products

    soups = [(1, first_page_soup)]
    for page_number in range(2, total_pages + 1):
        page_url = _build_page_url(category.url, page_number)
        html = _fetch_html(session, page_url)
        soups.append((page_number, BeautifulSoup(html, "html.parser")))
        time.sleep(PAGE_DELAY)

    for page_number, soup in soups:
        cards = soup.select(".prd.js-prd-item")
        page_products = 0
        for card in cards:
            parsed = _parse_card(card, category)
            if parsed is None:
                continue
            products.append(parsed)
            page_products += 1

        logging.info(
            "%s page %d/%d -> %d products",
            category.name,
            page_number,
            total_pages,
            page_products,
        )

    logging.info(
        "Finished %s with %d rows before dedup.",
        category.name,
        len(products),
    )
    return products


def _merge_pipe_values(left: str, right: str) -> str:
    seen: list[str] = []
    for value in [left, right]:
        for part in value.split(" | "):
            clean = _normalise_text(part)
            if clean and clean not in seen:
                seen.append(clean)
    return " | ".join(seen)


def _deduplicate(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for product in products:
        key = str(product.get("Product ID") or product.get("Product URL") or product.get("product_name"))
        if key not in merged:
            merged[key] = product
            continue

        existing = merged[key]
        existing["Source Category"] = _merge_pipe_values(
            str(existing.get("Source Category", "")),
            str(product.get("Source Category", "")),
        )
        existing["Source Category URL"] = _merge_pipe_values(
            str(existing.get("Source Category URL", "")),
            str(product.get("Source Category URL", "")),
        )
        if not existing.get("Subcategory") and product.get("Subcategory"):
            existing["Subcategory"] = product["Subcategory"]
            existing["Category Path"] = product["Category Path"]
        if not existing.get("Image URL") and product.get("Image URL"):
            existing["Image URL"] = product["Image URL"]

    return sorted(merged.values(), key=lambda row: (str(row["Source Category"]), str(row["product_name"])))


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _filter_categories(categories: list[Category], only: str | None) -> list[Category]:
    if not only:
        return categories

    wanted = {_slugify(part) for part in only.split(",") if _normalise_text(part)}
    filtered = [cat for cat in categories if cat.id in wanted or _slugify(cat.name) in wanted]
    missing = sorted(wanted - {_slugify(cat.id) for cat in filtered} - {_slugify(cat.name) for cat in filtered})
    if missing:
        logging.warning("Unknown categories ignored: %s", ", ".join(missing))
    return filtered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape D&R technology products into the daily repo CSV.")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel category workers (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Optional per-category page limit for smoke tests.",
    )
    parser.add_argument(
        "--category-limit",
        type=int,
        default=None,
        help="Optional limit on how many categories to scrape, from the discovered list order.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated category ids or names to scrape, e.g. 'telefon,oyun-konsol'.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional CSV output path override. Defaults to the dated repo path.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()

    bootstrap_session = _make_session()
    categories = _extract_categories_from_index(bootstrap_session)
    categories = _filter_categories(categories, args.only)
    if args.category_limit is not None:
        categories = categories[: args.category_limit]

    if not categories:
        raise SystemExit("No categories selected.")

    logging.info("Discovered %d D&R categories to scrape.", len(categories))
    for category in categories:
        logging.info("  - %s -> %s", category.name, category.url)

    all_products: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(_scrape_category, category, args.page_limit): category
            for category in categories
        }
        for future in as_completed(futures):
            category = futures[future]
            try:
                category_products = future.result()
            except Exception as exc:
                logging.error("Category %s failed: %s", category.name, exc)
                raise
            all_products.extend(category_products)

    deduped_products = _deduplicate(all_products)
    duplicates_removed = len(all_products) - len(deduped_products)

    output_path = Path(args.output).expanduser() if args.output else _default_output_path()
    _write_csv(deduped_products, output_path)

    logging.info("Raw rows collected: %d", len(all_products))
    logging.info("Duplicates removed: %d", duplicates_removed)
    logging.info("Final unique products: %d", len(deduped_products))
    logging.info("Saved CSV to %s", output_path)


if __name__ == "__main__":
    main()
