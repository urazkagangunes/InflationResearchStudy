"""
Samsung Product Data Extraction Module
======================================

Fetches every SKU in a Samsung Türkiye category via the public Product
Finder v2 (``pfv2``) JSON endpoint and returns a list of normalised
flat dictionaries ready for CSV export / downstream inflation
calculations.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=0.5, page_limit=0) -> list[dict]
    Iterates through all pages for ``category["type"]`` and returns the
    combined, SKU-level product list.

Data Flow
---------
1. GET ``searchapi.samsung.com/v6/front/b2c/product/finder/newhybris``
   with the category ``type`` code and ``start/num`` pagination params.
2. Parse ``response.resultData.productList`` — a list of *families*
   (e.g. "Galaxy S25").  Each family carries a ``modelList`` of real
   SKUs (one per colour / capacity).
3. Convert each model to a flat record (see :func:`_parse_model`),
   inheriting the family's sub-category name.
4. Advance ``start`` by ``num`` until the cumulative count reaches
   ``totalRecord`` or the API returns an empty / null page.

Output Schema
-------------
Each normalised product dict matches the schema used by the other
API-based scrapers (Rossmann, Migros) in this repository::

    {
      "id":            "SM-S931BLGGTUR",        # modelCode (primary key)
      "sku":           "SM-S931BLGGTUR",        # usually == id
      "name":          "Galaxy S25 256GB",      # displayName
      "brand":         "Samsung",               # always Samsung here
      "category":      "Smartphones",           # top-level (per scraper)
      "sub_category":  "Galaxy S",              # family.categorySubTypeName
      "family":        "Galaxy S25",            # family.fmyMarketingName
      "regular_price": 65499.0,                 # listPrice when set, else price
      "shown_price":   65499.0,                 # price (post-promotion)
      "discount_rate": 0,                       # % off (0 when none)
      "unit":          "PIECE",
      "status":        "IN_STOCK" / "OUT_OF_STOCK" / "COMING_SOON" / …
      "image_url":     "https://images.samsung.com/…",
      "product_url":   "https://www.samsung.com/tr/…/",
    }
"""

import logging
import random
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


# ── Session helpers ─────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Return a fresh ``requests.Session`` pre-loaded with default headers."""
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Price / status normalisation ────────────────────────────────────────────

def _as_float(value) -> float:
    """Return ``value`` as a ``float`` (``0.0`` on any parse failure).

    Samsung's pfv2 payload uses numeric JSON for prices but occasionally
    returns strings with a Turkish thousands separator (e.g. on the
    ``*_Display`` variants).  This helper tolerates both.
    """
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        cleaned = (
            str(value)
            .replace("TL", "")
            .replace("\xa0", "")
            .strip()
            .replace(".", "")
            .replace(",", ".")
        )
        try:
            return float(cleaned)
        except ValueError:
            return 0.0


def _status_from_cta(model: dict) -> str:
    """Derive a compact stock-status label from ``ctaType`` / ``stockStatusText``.

    Samsung uses a handful of CTA-type strings to communicate stock on
    the storefront.  We normalise them to the same ``IN_STOCK`` /
    ``OUT_OF_STOCK`` / ``COMING_SOON`` vocabulary used by the Rossmann
    scraper so downstream analytics can be store-agnostic.
    """
    cta = (model.get("ctaType") or "").strip().lower()
    if cta in {"instock", "in_stock", "buynow", "addtocart", "lowstock"}:
        return "IN_STOCK"
    if cta in {"outofstock", "out_of_stock", "soldout"}:
        return "OUT_OF_STOCK"
    if cta in {"comingsoon", "coming_soon", "notifyme", "notify_me"}:
        return "COMING_SOON"
    if cta in {"preorder", "pre_order"}:
        return "PRE_ORDER"
    if cta in {"learnmore", "learn_more", "viewdetails", "view_details"}:
        return "LEARN_MORE"
    # Fallback: pass through stockStatusText verbatim if ctaType is empty.
    raw = (model.get("stockStatusText") or "").strip().lower()
    if raw in {"instock", "in_stock", "lowstock", "low_stock"}:
        return "IN_STOCK"
    if raw in {"outofstock", "out_of_stock"}:
        return "OUT_OF_STOCK"
    return raw.upper() or "UNKNOWN"


def _absolute_image(url: str) -> str:
    """Ensure a ``thumbUrl`` coming back as ``//images…`` has a scheme."""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def _absolute_url(path: str) -> str:
    """Convert a relative ``pdpUrl`` to an absolute Samsung Türkiye URL."""
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return config.BASE_URL + path
    return path


# ── Family / model → record normalisation ───────────────────────────────────

def _parse_model(
    family: dict,
    model: dict,
    category_name: str,
) -> Optional[dict]:
    """Convert one ``modelList`` entry into a flat CSV record.

    Pricing
    -------
    Samsung exposes several price fields per SKU:

    - ``price`` / ``priceDisplay``                 – the shown price
      (post-promotion, what the customer actually pays).
    - ``listPrice`` / ``listPriceDisplay``         – the regular / list
      price.  Often ``None`` when no promotion is active.
    - ``lowestWasPrice`` / ``lowestWasPriceDisplay`` – the lowest
      "was" price recorded recently; also ``None`` when irrelevant.
    - ``promotionPrice``                             – usually equal to
      ``price`` when a promo applies.

    We treat ``price`` as ``shown_price`` and ``listPrice`` (or
    ``lowestWasPrice`` as fallback, or ``price`` when neither is set)
    as ``regular_price``.  ``discount_rate`` is derived from the ratio,
    clamped at zero.
    """
    model_code = (model.get("modelCode") or model.get("shopSKU") or "").strip()
    if not model_code:
        return None

    shown_price   = _as_float(model.get("price"))
    list_price    = _as_float(model.get("listPrice"))
    lowest_was    = _as_float(model.get("lowestWasPrice"))
    promo_price   = _as_float(model.get("promotionPrice"))

    # Some legal / placeholder entries have no price at all — they still
    # ship with a valid modelCode (e.g. "Coming soon" units).  Keep them
    # out of the dataset because they'd skew any price index.
    if not shown_price:
        shown_price = promo_price  # often identical to ``price``
    if not shown_price:
        return None

    # Choose a sensible regular_price.
    regular_price = list_price or lowest_was or shown_price

    # Derive discount percentage (0 when no discount or when the ratio
    # would be negative due to data noise).
    if regular_price and regular_price > shown_price:
        discount_rate = round((regular_price - shown_price) / regular_price * 100, 2)
    else:
        discount_rate = 0

    display_name = (
        (model.get("displayName") or "").strip()
        or (family.get("fmyMarketingName") or "").strip()
    )

    return {
        "product_name": display_name,
        "price":        round(shown_price, 2),
    }


# ── Page fetch with retries ─────────────────────────────────────────────────

def _fetch_page(
    session: requests.Session,
    type_code: str,
    start: int,
    num: int,
) -> Optional[dict]:
    """GET one pfv2 page with retries and return ``response.resultData``.

    Returns
    -------
    dict or None
        The ``resultData`` dict on success or ``None`` when every
        retry fails / the API returns ``resultData: null`` (e.g. when
        ``num`` is out of range).
    """
    params = {
        "type":             str(type_code),
        "siteCode":         config.SITE_CODE,
        "start":            int(start),
        "num":              int(num),
        "sort":             config.DEFAULT_SORT,
        "onlyFilterInfoYN": "N",
    }

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(
                config.PRODUCT_FINDER_URL, params=params, timeout=30
            )
            if resp.status_code == 403:
                logger.warning(
                    "403 Forbidden for type=%s start=%d — backing off.",
                    type_code, start,
                )
                time.sleep(config.RETRY_BACKOFF * attempt)
                continue

            resp.raise_for_status()
            data = resp.json() or {}
            rd = (data.get("response") or {}).get("resultData")
            # ``resultData`` is explicitly ``null`` when ``num`` is out
            # of range or when no products match.  Treat as empty page.
            return rd if rd is not None else {}
        except (requests.RequestException, ValueError) as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for type=%s start=%d: %s",
                    config.MAX_RETRIES, type_code, start, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds...",
                attempt, exc, wait,
            )
            time.sleep(wait)

    return None


# ── Public entry point ──────────────────────────────────────────────────────

def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Return every SKU in ``category`` by iterating pfv2 pages.

    Args
    ----
    category : dict
        Category dict as produced by ``category_fetcher.fetch_categories``.
        Must contain ``type`` and ``name``.
    session : requests.Session, optional
        Shared session with the required headers.  Created lazily when
        ``None``.
    delay : float
        Base inter-page sleep in seconds (multiplied by a uniform jitter
        in ``[config.JITTER_MIN, config.JITTER_MAX]``).
    page_limit : int
        Maximum pages to fetch per category.  ``0`` (default) →
        unlimited (still bounded by ``totalRecord`` reported by the API).

    Returns
    -------
    list[dict]
        Normalised SKU-level records (see :func:`_parse_model`).  An
        empty list is returned when the very first page fails.
    """
    if session is None:
        session = _make_session()

    type_code = category["type"]
    cat_name  = category["name"]

    all_products: list[dict] = []
    seen_skus: set[str] = set()

    start     = 1
    page_num  = 0
    total_record: Optional[int] = None

    logger.info("[%s] Starting scrape (type=%s)", cat_name, type_code)

    while True:
        page_num += 1
        if page_limit and page_num > page_limit:
            logger.info(
                "[%s] Reached page_limit=%d; stopping.", cat_name, page_limit
            )
            break

        rd = _fetch_page(session, type_code, start, config.PAGE_SIZE)
        if rd is None:
            logger.warning("[%s] Page %d fetch failed — aborting.",
                           cat_name, page_num)
            break

        if total_record is None:
            common = rd.get("common") or {}
            try:
                total_record = int(common.get("totalRecord") or 0)
            except (TypeError, ValueError):
                total_record = 0
            logger.debug(
                "[%s] totalRecord=%s", cat_name, total_record,
            )

        families = rd.get("productList") or []
        if not families:
            logger.info(
                "[%s] No families on page %d (start=%d) — end of catalogue.",
                cat_name, page_num, start,
            )
            break

        new_this_page = 0
        for family in families:
            for model in family.get("modelList") or []:
                record = _parse_model(family, model, cat_name)
                if record is None:
                    continue
                sku = record["sku"]
                if sku in seen_skus:
                    continue
                seen_skus.add(sku)
                all_products.append(record)
                new_this_page += 1

        logger.info(
            "[%s] page %d: +%d SKUs (family-batch=%d, running total: %d)",
            cat_name, page_num, new_this_page, len(families), len(all_products),
        )

        # Stop when the API has served us every family reported by
        # totalRecord (families, not SKUs) or when a page contributes
        # nothing new (defensive guard against infinite loops).
        start += len(families)
        if total_record and start > total_record:
            break
        if new_this_page == 0:
            logger.info(
                "[%s] Page %d produced 0 new SKUs — stopping.",
                cat_name, page_num,
            )
            break

        time.sleep(delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX))

    logger.info(
        "[%s] Completed: %d SKUs from %s families across %d page(s).",
        cat_name, len(all_products),
        "?" if total_record is None else total_record,
        page_num,
    )
    return all_products
