"""Product extraction for the Karaca scraper."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger(__name__)

# Listing pages are Next.js pages; the server-rendered product search result is
# the dehydrated React Query cache streamed inside these script calls.
FLIGHT_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)', re.S)
QUERIES_MARKER = '"queries":['
SEARCH_QUERY_KEY = ["product-service", "search"]
LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


@dataclass
class CategoryFetchResult:
    products: list[dict]
    total_products: Optional[int]
    total_pages: Optional[int]
    complete: bool


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _normalise_product_url(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    absolute = urljoin(config.HOME_URL, cleaned)
    if absolute.rstrip("/") == config.BASE_URL:
        return ""
    return absolute


def _as_float(value) -> float:
    """Convert a number or a Turkish price string such as '1.299,90 TL'."""
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = re.sub(r"[^\d,.]", "", str(value)).replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def _as_int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def build_page_url(category_url: str, page: int) -> str:
    """Build a category page URL with Karaca's `page` pagination parameter."""
    if page <= 1:
        return category_url

    parsed = urlparse(category_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


def _flight_text(html: str) -> str:
    return "".join(json.loads(match.group(1)) for match in FLIGHT_CHUNK_RE.finditer(html))


def parse_search_state(html: str) -> Optional[dict]:
    """Return the product search result embedded in a Karaca listing page."""
    text = _flight_text(html)
    decoder = json.JSONDecoder()
    start = text.find(QUERIES_MARKER)
    while start != -1:
        array_start = start + len(QUERIES_MARKER) - 1
        try:
            queries, end = decoder.raw_decode(text, array_start)
        except json.JSONDecodeError:
            start = text.find(QUERIES_MARKER, array_start)
            continue
        for query in queries if isinstance(queries, list) else []:
            if not isinstance(query, dict):
                continue
            key = query.get("queryKey") or []
            data = (query.get("state") or {}).get("data")
            if key[:2] == SEARCH_QUERY_KEY and isinstance(data, dict):
                return data
        start = text.find(QUERIES_MARKER, end)
    return None


def parse_listing_names(html: str) -> list[tuple[str, str]]:
    """Return (url, full name) pairs of the page's schema.org ItemList in listing order."""
    for match in LD_JSON_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "ItemList":
            elements = [el for el in data.get("itemListElement") or [] if isinstance(el, dict)]
            elements.sort(key=lambda el: el.get("position") or 0)
            items = [element.get("item") or {} for element in elements]
            return [(item.get("url") or "", item.get("name") or "") for item in items]
    return []


def _group_root_name(state: dict, source_category: dict) -> str:
    """Site taxonomy name of the listing's root when that root is the menu group."""
    taxonomy = state.get("taxonomy") or []
    if len(taxonomy) > 1 and isinstance(taxonomy[1], dict):
        if str(taxonomy[1].get("id")) == str(source_category.get("group_id")):
            return _clean_text(taxonomy[1].get("name") or "")
    return ""


def normalize_product_record(
    item: dict,
    source_category: dict,
    site_root: str = "",
    full_name: str = "",
) -> dict:
    """Normalise one Karaca listing item into CSV-ready fields."""
    analytics = item.get("analytics") or {}
    shown_price = _as_float(analytics.get("currentPrice")) or _as_float(item.get("price"))
    regular_price = (
        _as_float(analytics.get("listPrice"))
        or _as_float(item.get("originalPrice"))
        or shown_price
    )
    discount_amount = round(max(0.0, regular_price - shown_price), 2)
    discount_rate = round((discount_amount / regular_price) * 100, 2) if regular_price else 0.0

    stock_quantity = _as_int(analytics.get("stockLevel")) or 0
    in_stock = item.get("inStock")
    if in_stock is None:
        in_stock = stock_quantity > 0

    taxonomy = [
        _clean_text(name) for name in analytics.get("categories") or [] if _clean_text(name)
    ]
    # A product can be listed under several menu groups; the row whose group is
    # the product's own taxonomy root wins when duplicates are merged.
    primary = bool(site_root) and bool(taxonomy) and taxonomy[0] == site_root
    main_category = source_category.get("main_category", "")
    if len(taxonomy) > 1:
        top_category = taxonomy[1]
    elif taxonomy and not primary:
        top_category = taxonomy[0]
    else:
        top_category = source_category.get("name", "")

    # The product cards drop the brand prefix of the catalog name; the page's
    # ItemList keeps it, as earlier snapshots did. Approximate it otherwise.
    name = _clean_text(full_name)
    if not name:
        name = _clean_text(item.get("name") or "")
        brand = _clean_text(item.get("brand") or "")
        if brand and name and name.split()[0].casefold() != brand.split()[0].casefold():
            name = f"{brand} {name}"

    return {
        "product_name": name,
        "price": shown_price,
        "Product Original Cost": regular_price,
        "Discount Amount": discount_amount,
        "Discount Rate": discount_rate,
        "Currency": "TRY",
        "Product ID": str(item.get("productId") or ""),
        "Stock Quantity": stock_quantity,
        "In Stock": "Yes" if in_stock else "No",
        "Main Category": main_category,
        "Top Category": top_category,
        "Category ID": str(analytics.get("categoryId") or ""),
        "Category Path": " > ".join(part for part in (main_category, top_category) if part),
        "Source Category": source_category.get("name", ""),
        "Source Category URL": source_category.get("url", ""),
        "Product URL": _normalise_product_url(item.get("url") or ""),
        "Image URL": _clean_text((item.get("image") or {}).get("url") or ""),
        "Color": _clean_text(analytics.get("variant") or ""),
        "Size": "",
        "_primary": primary,
    }


def _is_valid_product_record(record: dict) -> bool:
    product_id = _clean_text(record.get("Product ID") or "")
    product_name = _clean_text(record.get("product_name") or "")
    product_url = _clean_text(record.get("Product URL") or "")
    if not product_id or not product_name or not product_url:
        return False
    if product_url.rstrip("/") == config.BASE_URL:
        return False
    if record.get("price", 0) <= 0:
        return False
    return True


def parse_product_records(
    state: dict,
    source_category: dict,
    listing_names: Optional[list[tuple[str, str]]] = None,
) -> list[dict]:
    """Normalise the items of one embedded search result."""
    site_root = _group_root_name(state, source_category)
    items = state.get("items") or []
    names = listing_names if listing_names and len(listing_names) == len(items) else []
    records: list[dict] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        full_name = ""
        if names and names[index][0] == item.get("url"):
            full_name = names[index][1]
        record = normalize_product_record(item, source_category, site_root, full_name)
        if not _is_valid_product_record(record):
            logger.warning(
                "Dropping malformed Karaca product row in '%s': id=%s name=%r url=%r price=%r",
                source_category.get("name", ""),
                record.get("Product ID", ""),
                record.get("product_name", ""),
                record.get("Product URL", ""),
                record.get("price"),
            )
            continue
        records.append(record)
    return records


def _fetch_page_html(session: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BACKOFF * attempt)
    raise RuntimeError(f"Karaca category page could not be fetched: {url} ({last_error})")


def _fetch_listing(session: requests.Session, url: str) -> tuple[Optional[dict], str]:
    # The page is occasionally rendered without its product listing; a later
    # request for the same URL returns it again.
    html = ""
    for attempt in range(1, config.MAX_RETRIES + 1):
        html = _fetch_page_html(session, url)
        state = parse_search_state(html)
        if state is not None:
            return state, html
        if attempt < config.MAX_RETRIES:
            logger.info("No product listing in %s (attempt %d); retrying.", url, attempt)
            time.sleep(config.RETRY_BACKOFF * attempt)
    return None, html


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> CategoryFetchResult:
    """Fetch every page for one Karaca category."""
    if session is None:
        session = _make_session()

    all_products: list[dict] = []
    seen_ids: set[str] = set()
    seen_page_signatures: set[tuple[str, ...]] = set()
    total_products: Optional[int] = None
    total_pages: Optional[int] = None
    page = 1
    complete = True

    while True:
        if page_limit and page > page_limit:
            if total_products is None or len(seen_ids) < total_products:
                complete = False
            break
        if total_pages is not None and page > total_pages:
            break
        if page > 1 and delay:
            time.sleep(random.uniform(delay, delay * 3))

        state, html = _fetch_listing(session, build_page_url(category["url"], page))
        if state is None:
            if page == 1:
                logger.warning("Category '%s' has no Karaca product listing.", category["name"])
                break
            logger.warning(
                "Category '%s' page %d has no product listing after %d attempts; skipping it.",
                category["name"],
                page,
                config.MAX_RETRIES,
            )
            complete = False
            if total_pages is None:
                break
            page += 1
            continue

        pagination = state.get("pagination") or {}
        if total_products is None:
            total_products = _as_int(pagination.get("totalResults"))
        if total_pages is None:
            total_pages = _as_int(pagination.get("totalPages"))

        page_products = parse_product_records(state, category, parse_listing_names(html))
        if not page_products:
            if page == 1:
                logger.warning(
                    "Category '%s' returned no Karaca products on its first page.",
                    category["name"],
                )
            break

        signature = tuple(item["Product ID"] for item in page_products)
        if signature in seen_page_signatures:
            logger.warning(
                "Category '%s' page %d repeated a previous page payload. Stopping pagination.",
                category["name"],
                page,
            )
            complete = False
            break
        seen_page_signatures.add(signature)

        all_products.extend(page_products)
        seen_ids.update(signature)
        logger.info(
            "  %s page %d/%s -> %d products (unique so far: %d/%s)",
            category["name"],
            page,
            total_pages if total_pages is not None else "?",
            len(page_products),
            len(seen_ids),
            total_products if total_products is not None else "?",
        )
        page += 1

    if (complete and not page_limit and total_pages and total_products is not None
            and len(seen_ids) < total_products):
        # The default order shifts while paging (2026-09-29: page 3 of a
        # 123-product category repeated 10 products and skipped 10 others);
        # one more pass picks up what the first one missed.
        logger.info(
            "Category '%s' is %d short of the site's count; paging it once more.",
            category["name"],
            total_products - len(seen_ids),
        )
        for page in range(1, total_pages + 1):
            if delay:
                time.sleep(random.uniform(delay, delay * 3))
            state, html = _fetch_listing(session, build_page_url(category["url"], page))
            if state is None:
                continue
            for item in parse_product_records(state, category, parse_listing_names(html)):
                if item["Product ID"] not in seen_ids:
                    seen_ids.add(item["Product ID"])
                    all_products.append(item)

    if complete and total_products is not None and len(seen_ids) < total_products:
        logger.warning(
            "Category '%s' collected %d unique products but the site reported %d.",
            category["name"],
            len(seen_ids),
            total_products,
        )

    return CategoryFetchResult(
        products=all_products,
        total_products=total_products,
        total_pages=total_pages,
        complete=complete,
    )
