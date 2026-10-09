"""
Product fetcher — Sarıyer Market
Ürünler AJAX ile yükleniyor. Slug URL'den cid alıp POST ile çekiyoruz.
"""

import re
import time
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _price(text: str) -> float:
    if not text:
        return 0.0
    clean = re.sub(r"[^\d,\.]", "", text)
    if "," in clean and "." in clean:
        if clean.rfind(",") > clean.rfind("."):
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(",", "")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        return round(float(clean), 2)
    except:
        return 0.0


def _get_cid(session: requests.Session, category_url: str) -> Optional[str]:
    """
    Kategori slug URL'ini ziyaret edip cid parametresini döndürür.
    Redirect sonrası URL'de ?cid= varsa oradan alır.
    Yoksa sayfa HTML'inden çıkarmaya çalışır.
    """
    try:
        resp = session.get(category_url, timeout=20, allow_redirects=True)
        # Redirect sonrası URL'de cid var mı?
        final_url = resp.url
        parsed = urlparse(final_url)
        qs = parse_qs(parsed.query)
        if "cid" in qs:
            return qs["cid"][0]

        # HTML içinde cid ara
        match = re.search(r'["\']?cid["\']?\s*[:=]\s*["\']?(\d+)', resp.text)
        if match:
            return match.group(1)

        # data-categoryid veya benzeri attribute
        soup = BeautifulSoup(resp.text, "lxml")
        tag = soup.select_one("[data-categoryid], [data-category-id], [data-cid]")
        if tag:
            return (
                tag.get("data-categoryid")
                or tag.get("data-category-id")
                or tag.get("data-cid")
            )

    except Exception as exc:
        logger.warning("cid alınamadı (%s): %s", category_url, exc)

    return None


def _parse_product(raw: dict, category: dict) -> dict:
    def p(val) -> float:
        if not val:
            return 0.0
        return _price(str(val))

    shown    = p(raw.get("Price") or raw.get("price"))
    regular  = p(raw.get("OldPrice") or raw.get("oldPrice") or shown)
    if regular == 0:
        regular = shown

    discount = 0
    if regular and shown and regular > shown:
        discount = int(round((regular - shown) / regular * 100))

    image = raw.get("PictureThumbnailUrl") or raw.get("DefaultPictureModel", {}).get("ImageUrl", "")
    if image and not image.startswith("http"):
        image = config.BASE_URL + image

    slug = raw.get("SeName") or raw.get("seName") or ""
    product_url = f"{config.BASE_URL}/{slug}" if slug else ""

    return {
        "id":            str(raw.get("Id") or raw.get("id") or ""),
        "sku":           str(raw.get("Sku") or raw.get("sku") or ""),
        "name":          raw.get("Name") or raw.get("name") or "",
        "brand":         "",
        "category":      category.get("name", ""),
        "category_id":   category.get("id", ""),
        "regular_price": regular,
        "shown_price":   shown,
        "discount_rate": discount,
        "unit":          "",
        "status":        "IN_STOCK" if raw.get("InStock") else "OUT_OF_STOCK",
        "image_url":     image,
        "product_url":   product_url,
    }


def _parse_product_html(card, category: dict) -> Optional[dict]:
    """Fallback: HTML karttan ürün parse et."""
    item = card.select_one(".product-item") or card

    product_id = item.get("data-productid", "")
    name_tag = item.select_one("h2.product-title a")
    name = name_tag.get_text(strip=True) if name_tag else ""
    if not name:
        return None

    sku_tag = item.select_one(".sku")
    sku = sku_tag.get_text(strip=True) if sku_tag else product_id

    price_tag = item.select_one("span.actual-price, span.price")
    shown_price = _price(price_tag.get_text(strip=True) if price_tag else "")
    old_tag = item.select_one("span.old-price")
    regular_price = _price(old_tag.get_text(strip=True) if old_tag else "")
    if regular_price == 0:
        regular_price = shown_price

    discount = 0
    if regular_price and shown_price and regular_price > shown_price:
        discount = int(round((regular_price - shown_price) / regular_price * 100))

    img_tag = item.select_one("img.picture-img, img")
    image_url = ""
    if img_tag:
        image_url = img_tag.get("src") or img_tag.get("data-lazyloadsrc") or ""
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(config.BASE_URL, image_url)

    link_tag = item.select_one(".picture a, h2.product-title a")
    product_url = ""
    if link_tag:
        href = link_tag.get("href", "")
        product_url = urljoin(config.BASE_URL, href) if href else ""

    unit_tag = item.select_one(".bootstrap-touchspin-postfix .input-group-text")
    unit = unit_tag.get_text(strip=True) if unit_tag else ""

    return {
        "id":            str(product_id),
        "sku":           str(sku),
        "name":          name,
        "brand":         "",
        "category":      category.get("name", ""),
        "category_id":   category.get("id", ""),
        "regular_price": regular_price,
        "shown_price":   shown_price,
        "discount_rate": discount,
        "unit":          unit,
        "status":        "OUT_OF_STOCK" if item.select_one(".out-of-stock") else "IN_STOCK",
        "image_url":     image_url,
        "product_url":   product_url,
    }


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:

    if session is None:
        session = _make_session()

    # cid'yi bul
    cid = _get_cid(session, category["url"])

    if cid:
        return _fetch_via_post(session, category, cid, delay, page_limit)
    else:
        logger.warning("cid bulunamadı '%s' — HTML moduna geçiliyor.", category["name"])
        return _fetch_via_html(session, category, delay, page_limit)


def _fetch_via_post(
    session: requests.Session,
    category: dict,
    cid: str,
    delay: float,
    page_limit: int,
) -> list[dict]:
    """POST /Catalog/OBAjaxFilterProducts ile ürünleri çek."""
    all_products: list[dict] = []
    page = 0  # 0-indexed

    while True:
        if page_limit and page >= page_limit:
            break

        form_data = {
            "q":    "",
            "cid":  cid,
            "isc":  "true",
            "mid":  "0",
            "vid":  "0",
            "sid":  "true",
            "adv":  "true",
            "asv":  "false",
            "PagingFilteringContext[PageNumber]": str(page),
            "PagingFilteringContext[PageSize]":   str(config.PAGE_SIZE),
        }

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = session.post(
                    config.PRODUCT_LIST_URL,
                    data=form_data,
                    headers={**config.DEFAULT_HEADERS,
                             "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                             "X-Requested-With": "XMLHttpRequest",
                             "Referer": category["url"]},
                    timeout=30,
                )
                if resp.status_code == 403:
                    return all_products
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == config.MAX_RETRIES:
                    return all_products
                time.sleep(config.RETRY_BACKOFF * attempt)

        # Yanıt HTML mi JSON mi?
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            try:
                data = resp.json()
                products_raw = (
                    data.get("products") or data.get("Products")
                    or data.get("CatalogProductsModel", {}).get("Products")
                    or []
                )
            except Exception:
                products_raw = []
        else:
            # HTML yanıtı — BeautifulSoup ile parse et
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(".item-box")
            products_raw = []
            for card in cards:
                rec = _parse_product_html(card, category)
                if rec:
                    all_products.append(rec)

            total_pages_tag = soup.select_one(".total-pages")
            if not cards:
                break

            logger.debug(
                "Kategori '%s' (POST/HTML) — sayfa %d → %d ürün",
                category["name"], page, len(cards),
            )

            next_page = soup.select_one(".next-page a, a[rel='next']")
            if not next_page:
                break
            page += 1
            time.sleep(delay)
            continue

        if not products_raw:
            break

        for raw in products_raw:
            all_products.append(_parse_product(raw, category))

        logger.debug(
            "Kategori '%s' — sayfa %d → %d ürün (toplam: %d)",
            category["name"], page, len(products_raw), len(all_products),
        )

        total_pages = data.get("totalPages") or data.get("TotalPages")
        if total_pages and page + 1 >= int(total_pages):
            break
        if len(products_raw) < config.PAGE_SIZE:
            break

        page += 1
        time.sleep(delay)

    return all_products


def _fetch_via_html(
    session: requests.Session,
    category: dict,
    delay: float,
    page_limit: int,
) -> list[dict]:
    """Fallback: sayfa sayfa HTML scraping."""
    all_products: list[dict] = []
    page = 1
    base_url = category["url"]

    while True:
        if page_limit and page > page_limit:
            break

        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}pagenumber={page}"

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == config.MAX_RETRIES:
                    return all_products
                time.sleep(config.RETRY_BACKOFF * attempt)

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select(".item-box")

        if not cards:
            break

        for card in cards:
            rec = _parse_product_html(card, category)
            if rec:
                all_products.append(rec)

        next_page = soup.select_one(".next-page a, a[rel='next']")
        if not next_page:
            break

        page += 1
        time.sleep(delay)

    return all_products
