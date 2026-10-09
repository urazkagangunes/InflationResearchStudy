"""Product extraction for the Golden Rose scraper."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

import config

logger = logging.getLogger(__name__)

PRODUCT_DATA_RE = re.compile(
    r"PRODUCT_DATA\.push\(JSON\.parse\('(?P<payload>(?:\\'|[^'])*)'\)\);"
)
TOTAL_COUNT_EN_RE = re.compile(
    r"There is a total of\s*<span[^>]*>\s*(?P<count>\d+)\s*</span>\s*products",
    re.IGNORECASE,
)
TOTAL_COUNT_TR_RE = re.compile(
    r"Toplam\s*<span[^>]*>\s*(?P<count>\d+)\s*</span>\s*ürün",
    re.IGNORECASE,
)
SLUG_TOKEN_RE = re.compile(r"[a-z0-9]+")
SLUG_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
    }
)
SLUG_STOPWORDS = {
    "and",
    "care",
    "color",
    "colors",
    "eyeliner",
    "for",
    "golden",
    "kalem",
    "kalemi",
    "kiss",
    "likit",
    "liquid",
    "liner",
    "lipstick",
    "mat",
    "matte",
    "new",
    "oje",
    "ojesi",
    "pencil",
    "rose",
    "ruj",
    "the",
    "urun",
    "urunler",
    "ve",
    "yeni",
}
GENERIC_LEAF_CATEGORY_SLUGS = {"urunler"}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _slug_tokens(value: str) -> list[str]:
    normalized = _clean_text(value).casefold().translate(SLUG_TRANSLATION)
    return SLUG_TOKEN_RE.findall(normalized)


def _significant_slug_tokens(value: str) -> set[str]:
    return {
        token
        for token in _slug_tokens(value)
        if len(token) > 1 and token not in SLUG_STOPWORDS
    }


def _humanize_slug_tokens(tokens: list[str]) -> str:
    words: list[str] = []
    for token in tokens:
        if token.isdigit():
            words.append(token)
        else:
            words.append(token.capitalize())
    return " ".join(words)


def _as_float(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def _decode_js_single_quoted_string(payload: str) -> str:
    """Decode JS single-quoted string contents into plain text.

    Golden Rose embeds JSON inside `JSON.parse('...')`, so the captured
    payload follows JavaScript string-literal escape rules rather than raw
    JSON string rules. Notably, apostrophes are emitted as `\'`, which is
    valid JavaScript but invalid JSON.
    """
    chars: list[str] = []
    i = 0
    while i < len(payload):
        ch = payload[i]
        if ch != "\\":
            chars.append(ch)
            i += 1
            continue

        if i + 1 >= len(payload):
            chars.append("\\")
            break

        nxt = payload[i + 1]
        if nxt in {"'", '"', "\\", "/"}:
            chars.append(nxt)
            i += 2
            continue
        if nxt == "b":
            chars.append("\b")
            i += 2
            continue
        if nxt == "f":
            chars.append("\f")
            i += 2
            continue
        if nxt == "n":
            chars.append("\n")
            i += 2
            continue
        if nxt == "r":
            chars.append("\r")
            i += 2
            continue
        if nxt == "t":
            chars.append("\t")
            i += 2
            continue
        if nxt == "u" and i + 5 < len(payload):
            hex_part = payload[i + 2 : i + 6]
            if all(c in "0123456789abcdefABCDEF" for c in hex_part):
                chars.append(chr(int(hex_part, 16)))
                i += 6
                continue
        if nxt == "x" and i + 3 < len(payload):
            hex_part = payload[i + 2 : i + 4]
            if all(c in "0123456789abcdefABCDEF" for c in hex_part):
                chars.append(chr(int(hex_part, 16)))
                i += 4
                continue

        # Preserve unexpected escapes conservatively.
        chars.append(nxt)
        i += 2

    return "".join(chars)


def _decode_embedded_json(payload: str) -> dict:
    decoded = _decode_js_single_quoted_string(payload)
    return json.loads(decoded)


def _build_product_url(raw: dict) -> str:
    return urljoin(config.HOME_URL, raw.get("url") or "")


def _looks_like_wrong_product_name(record: dict) -> bool:
    slug = urlparse(record.get("Product URL", "")).path.strip("/").split("/")[-1]
    slug_tokens = _significant_slug_tokens(slug)
    name_tokens = _significant_slug_tokens(record.get("product_name", ""))
    model_tokens = _significant_slug_tokens(record.get("Model", ""))
    return bool(slug_tokens) and bool(slug_tokens & model_tokens) and not (slug_tokens & name_tokens)


def _repair_product_name(record: dict) -> dict:
    if not _looks_like_wrong_product_name(record):
        return record

    slug = urlparse(record.get("Product URL", "")).path.strip("/").split("/")[-1]
    slug_tokens = _slug_tokens(slug)
    if slug_tokens[:2] == ["golden", "rose"]:
        slug_tokens = slug_tokens[2:]

    model_tokens = _slug_tokens(record.get("Model", ""))
    if not model_tokens or slug_tokens[: len(model_tokens)] != model_tokens:
        return record

    remainder_tokens = slug_tokens[len(model_tokens) :]
    if not remainder_tokens:
        return record

    leaf_category = _clean_text(record.get("Leaf Category", ""))
    leaf_tokens = _slug_tokens(leaf_category)
    leaf_slug = "-".join(leaf_tokens)

    repaired_name: str | None = None
    if (
        leaf_tokens
        and leaf_slug not in GENERIC_LEAF_CATEGORY_SLUGS
        and len(remainder_tokens) > len(leaf_tokens)
        and remainder_tokens[-len(leaf_tokens) :] == leaf_tokens
    ):
        variant_tokens = remainder_tokens[: -len(leaf_tokens)]
        if variant_tokens:
            repaired_name = " - ".join(
                [
                    record["Model"],
                    _humanize_slug_tokens(variant_tokens),
                    leaf_category,
                ]
            )

    if repaired_name is None:
        suffix = _humanize_slug_tokens(remainder_tokens)
        if not suffix:
            return record
        separator = " - " if remainder_tokens[0].isdigit() else " "
        repaired_name = f"{record['Model']}{separator}{suffix}"

    if repaired_name == record.get("product_name", ""):
        return record

    logger.warning(
        "Corrected suspicious Golden Rose product name for ID %s: %r -> %r",
        record.get("Product ID", ""),
        record.get("product_name", ""),
        repaired_name,
    )
    updated = dict(record)
    updated["product_name"] = repaired_name
    return updated


def build_page_url(category_url: str, page: int) -> str:
    """Build a category page URL with the site's `pg` pagination parameter."""
    if page <= 1:
        return category_url

    parsed = urlparse(category_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["pg"] = str(page)
    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


def extract_total_products(html: str) -> Optional[int]:
    """Extract the total product count from a category page if present."""
    for pattern in (TOTAL_COUNT_EN_RE, TOTAL_COUNT_TR_RE):
        match = pattern.search(html)
        if match:
            return int(match.group("count"))
    return None


def normalize_product_record(raw: dict, source_category: dict) -> dict:
    """Normalise one inline Golden Rose product payload into CSV-ready fields."""
    regular_price = _as_float(
        raw.get("total_base_price") or raw.get("total_sale_price") or raw.get("price")
    )
    shown_price = _as_float(raw.get("total_sale_price") or raw.get("total_base_price"))
    if shown_price == 0:
        shown_price = regular_price
    if regular_price == 0:
        regular_price = shown_price

    discount_amount = round(max(0.0, regular_price - shown_price), 2)
    discount_rate = round((discount_amount / regular_price) * 100, 2) if regular_price else 0.0

    quantity = int(float(raw.get("quantity") or 0))
    available = raw.get("available")
    in_stock = bool(available) if available is not None else quantity > 0

    category_path = _clean_text(raw.get("category_path") or "")
    leaf_category = _clean_text(raw.get("category") or "")
    path_parts = [part.strip() for part in category_path.split(">") if part.strip()]
    top_category = path_parts[0] if path_parts else source_category.get("name", "")
    full_category_parts = list(path_parts)
    if leaf_category and (not full_category_parts or full_category_parts[-1] != leaf_category):
        full_category_parts.append(leaf_category)

    record = {
        "product_name": _clean_text(raw.get("name") or ""),
        "price": shown_price,
        "Product Original Cost": regular_price,
        "Discount Amount": discount_amount,
        "Discount Rate": discount_rate,
        "Currency": _clean_text(raw.get("currency_target") or raw.get("currency") or "TL"),
        "Product ID": str(raw.get("id") or ""),
        "SKU": str(raw.get("supplier_code") or raw.get("code") or ""),
        "Brand": _clean_text(raw.get("brand") or ""),
        "Stock Quantity": quantity,
        "In Stock": "Yes" if in_stock else "No",
        "Top Category": top_category,
        "Category Path": category_path,
        "Leaf Category": leaf_category,
        "Full Category": " > ".join(full_category_parts),
        "Model": _clean_text(raw.get("model") or ""),
        "Variant 1": _clean_text(raw.get("variant1") or ""),
        "Variant 2": _clean_text(raw.get("variant2") or ""),
        "Subproduct ID": str(raw.get("subproduct_id") or ""),
        "Subproduct Code": str(raw.get("subproduct_code") or ""),
        "Category ID": str(raw.get("category_id") or ""),
        "Source Category": source_category.get("name", ""),
        "Source Category URL": source_category.get("url", ""),
        "Product URL": _build_product_url(raw),
        "Image URL": _clean_text(raw.get("image") or ""),
    }
    return _repair_product_name(record)


def parse_product_records_from_html(html: str, source_category: dict) -> list[dict]:
    """Parse embedded Golden Rose `PRODUCT_DATA` records from a category page."""
    records: list[dict] = []
    for match in PRODUCT_DATA_RE.finditer(html):
        raw = _decode_embedded_json(match.group("payload"))
        records.append(normalize_product_record(raw, source_category))
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
    raise RuntimeError(f"Golden Rose category page could not be fetched: {url} ({last_error})")


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Fetch every page for one Golden Rose category."""
    if session is None:
        session = _make_session()

    all_products: list[dict] = []
    seen_page_signatures: set[tuple[str, ...]] = set()
    total_products: Optional[int] = None
    page = 1

    while True:
        if page_limit and page > page_limit:
            break

        page_url = build_page_url(category["url"], page)
        html = _fetch_page_html(session, page_url)

        if total_products is None:
            total_products = extract_total_products(html)

        page_products = parse_product_records_from_html(html, category)
        if not page_products:
            break

        signature = tuple(item["Product ID"] for item in page_products)
        if signature in seen_page_signatures:
            logger.warning(
                "Category '%s' page %d repeated a previous page payload. Stopping pagination.",
                category["name"],
                page,
            )
            break
        seen_page_signatures.add(signature)

        all_products.extend(page_products)
        total_suffix = f"/{total_products}" if total_products is not None else ""
        logger.info(
            "  %s page %d -> %d products (running total: %d%s)",
            category["name"],
            page,
            len(page_products),
            len(all_products),
            total_suffix,
        )

        if total_products is not None and len(all_products) >= total_products:
            break

        page += 1
        time.sleep(delay)

    return all_products
