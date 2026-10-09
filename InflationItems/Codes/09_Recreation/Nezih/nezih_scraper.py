"""
Nezih books and stationery scraper.

Scrapes Nezih's top-level `Kitap` and `Kirtasiye` category listings into the
repo's daily CSV format:

    InflationItems/Datas/BooksStationery/Nezih/nezih_YYYY-MM-DD.csv

The scraper reads the embedded `PRODUCT_DATA` JSON payloads on each listing
page, paginates with `?pg=N`, and writes a combined daily CSV for both
assigned course categories.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.nezih.com.tr"

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
DEFAULT_WORKERS = 4

PRODUCT_DATA_PATTERN = re.compile(
    r"PRODUCT_DATA\.push\(JSON\.parse\('((?:\\.|[^'])*)'\)\)\s*;",
    re.DOTALL,
)

CSV_COLUMNS = [
    "Product Name",
    "Product Cost",
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
class CategoryScope:
    slug: str
    name: str
    url: str


CATEGORY_SCOPES = {
    "kitap": CategoryScope(slug="kitap", name="Kitap", url=f"{BASE_URL}/kitap"),
    "kirtasiye": CategoryScope(
        slug="kirtasiye",
        name="Kırtasiye",
        url=f"{BASE_URL}/kirtasiye",
    ),
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _output_dir() -> Path:
    return (
        _project_root()
        / "InflationItems"
        / "Datas"
        / "BooksStationery"
        / "Nezih"
    )


def _scrape_date_str() -> str:
    override = os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
    if override:
        return datetime.fromisoformat(override).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def _default_output_path() -> Path:
    return _output_dir() / f"nezih_{_scrape_date_str()}.csv"


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_currency(value: str | None) -> str:
    currency = _normalise_text(value).upper()
    if currency == "TL":
        return "TRY"
    return currency or "TRY"


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
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
    params["pg"] = str(page_number)
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(params), split.fragment)
    )


def _parse_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    page_numbers: list[int] = []
    for link in soup.select("div.pagination a[href*='pg=']"):
        href = link.get("href", "")
        query = dict(parse_qsl(urlsplit(href).query, keep_blank_values=True))
        raw_page = query.get("pg", "").strip()
        if raw_page.isdigit():
            page_numbers.append(int(raw_page))
    return max(page_numbers, default=1)


def _decode_product_payload(escaped_json: str) -> dict[str, Any]:
    # Nezih embeds PRODUCT_DATA inside a JavaScript single-quoted string, so
    # payloads can contain JS-only escapes like \' that are invalid in JSON.
    decoded_json = escaped_json.encode("utf-8").decode("unicode_escape")
    decoded_json = decoded_json.replace("\\/", "/")
    return json.loads(decoded_json)


def _split_category_fields(
    category_path: str | None,
    leaf_category: str | None,
    source_category_name: str,
) -> tuple[str, str, str, str]:
    path_segments = [
        _normalise_text(segment)
        for segment in (category_path or "").split(">")
        if _normalise_text(segment)
    ]
    leaf = _normalise_text(leaf_category)
    full_segments = list(path_segments)
    if leaf and (not full_segments or full_segments[-1] != leaf):
        full_segments.append(leaf)

    if not full_segments:
        full_segments = [source_category_name]

    top_category = full_segments[0]

    if len(full_segments) == 1:
        category = full_segments[0]
        subcategory = ""
    elif len(full_segments) == 2:
        category = full_segments[1]
        subcategory = ""
    else:
        category = full_segments[1]
        subcategory = " > ".join(full_segments[2:])

    return top_category, category, subcategory, " > ".join(full_segments)


def _campaign_label(original_price: float | None, current_price: float | None) -> str:
    if not original_price or not current_price or original_price <= current_price:
        return ""

    discount_rate = ((original_price - current_price) / original_price) * 100.0
    return f"-%{round(discount_rate)}"


def _product_row(
    payload: dict[str, Any],
    source_category_name: str,
    source_category_url: str,
) -> dict[str, Any] | None:
    product_name = _normalise_text(payload.get("name"))
    current_price = _coerce_float(payload.get("total_sale_price"))
    original_price = _coerce_float(payload.get("total_base_price")) or current_price

    if not product_name or current_price is None:
        return None

    top_category, category, subcategory, category_path = _split_category_fields(
        category_path=str(payload.get("category_path") or ""),
        leaf_category=str(payload.get("category") or ""),
        source_category_name=source_category_name,
    )

    product_id = _normalise_text(payload.get("id"))
    variation_id = _normalise_text(payload.get("subproduct_id"))
    if variation_id == "0":
        variation_id = ""

    product_url = urljoin(f"{BASE_URL}/", _normalise_text(payload.get("url")))
    image_url = urljoin(f"{BASE_URL}/", _normalise_text(payload.get("image")))

    quantity = payload.get("quantity")
    try:
        in_stock = int(quantity) > 0
    except (TypeError, ValueError):
        in_stock = bool(quantity)

    return {
        "Product Name": product_name,
        "Product Cost": round(current_price, 2),
        "Product Original Cost": round(original_price, 2) if original_price is not None else "",
        "Currency": _clean_currency(
            _normalise_text(payload.get("currency_target"))
            or _normalise_text(payload.get("currency"))
        ),
        "Product ID": product_id,
        "Variation ID": variation_id,
        "Brand": _normalise_text(payload.get("brand")),
        "In Stock": in_stock,
        "Campaign Label": _campaign_label(original_price, current_price),
        "Top Category": top_category,
        "Category": category,
        "Subcategory": subcategory,
        "Category Path": category_path,
        "Source Category": source_category_name,
        "Source Category URL": source_category_url,
        "Product URL": product_url,
        "Image URL": image_url,
    }


def _extract_products_from_html(
    html: str,
    source_category_name: str,
    source_category_url: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in PRODUCT_DATA_PATTERN.finditer(html):
        payload = _decode_product_payload(match.group(1))
        row = _product_row(payload, source_category_name, source_category_url)
        if row is not None:
            rows.append(row)
    return rows


def _fetch_category_page(page_url: str) -> str:
    session = _make_session()
    try:
        return _fetch_html(session, page_url)
    finally:
        session.close()


def _scrape_category(
    category: CategoryScope,
    page_limit: int | None = None,
    workers: int = DEFAULT_WORKERS,
) -> list[dict[str, Any]]:
    session = _make_session()
    try:
        first_page_html = _fetch_html(session, category.url)
    finally:
        session.close()

    total_pages = _parse_total_pages(first_page_html)
    if page_limit is not None:
        total_pages = min(total_pages, page_limit)

    logging.info("%s: fetching %d page(s)", category.name, total_pages)

    pages: dict[int, str] = {1: first_page_html}
    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_to_page = {
                executor.submit(_fetch_category_page, _build_page_url(category.url, page_number)): page_number
                for page_number in range(2, total_pages + 1)
            }
            for future in as_completed(future_to_page):
                page_number = future_to_page[future]
                pages[page_number] = future.result()

    rows: list[dict[str, Any]] = []
    for page_number in range(1, total_pages + 1):
        page_rows = _extract_products_from_html(
            pages[page_number],
            source_category_name=category.name,
            source_category_url=category.url,
        )
        logging.info("%s page %d: %d product rows", category.name, page_number, len(page_rows))
        rows.extend(page_rows)
    return rows


def _dedupe_products(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("Product ID") or row.get("Product URL") or row.get("Product Name"))
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
            continue

        # Prefer the row with the more specific category path if duplicates appear.
        if len(str(row.get("Category Path", ""))) > len(str(existing.get("Category Path", ""))):
            merged[key] = row

    return sorted(
        merged.values(),
        key=lambda row: (
            str(row["Top Category"]),
            str(row["Category Path"]),
            str(row["Product Name"]),
        ),
    )


def _write_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _parse_only_categories(raw_value: str | None) -> list[CategoryScope]:
    if not raw_value:
        return [CATEGORY_SCOPES["kitap"], CATEGORY_SCOPES["kirtasiye"]]

    slugs = [item.strip().lower() for item in raw_value.split(",") if item.strip()]
    invalid = [slug for slug in slugs if slug not in CATEGORY_SCOPES]
    if invalid:
        valid_options = ", ".join(sorted(CATEGORY_SCOPES))
        raise SystemExit(f"Unknown category slug(s): {', '.join(invalid)}. Valid options: {valid_options}")

    return [CATEGORY_SCOPES[slug] for slug in slugs]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Nezih books and stationery products into the daily repo CSV."
    )
    parser.add_argument(
        "--only",
        help="Comma-separated category slugs to scrape. Options: kitap,kirtasiye",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        help="Limit the number of pages per category for smoke tests.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of worker threads for paginated fetches (default: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional CSV output path. Defaults to the repo's dated Nezih CSV path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    categories = _parse_only_categories(args.only)
    rows: list[dict[str, Any]] = []

    for category in categories:
        rows.extend(
            _scrape_category(
                category,
                page_limit=args.page_limit,
                workers=args.workers,
            )
        )

    unique_rows = _dedupe_products(rows)
    output_path = args.output or _default_output_path()
    _write_rows(unique_rows, output_path)
    logging.info("Saved %d unique products to %s", len(unique_rows), output_path)


if __name__ == "__main__":
    main()
