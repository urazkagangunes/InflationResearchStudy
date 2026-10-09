"""
scraper.py - Core scraping logic for the Erzurum / Erzincan / Bayburt rent scraper.

Rewritten to use SeleniumBase in UC (undetected-chromedriver) mode.
SeleniumBase automatically downloads the correct ARM64 chromedriver on Apple Silicon.

Key design: SMART ADAPTIVE BRACKETS (EARLY PEEK)
------------------------------------------------
For any price range, the scraper loads page 1 and looks for the text telling
us the total number of listings (e.g. "aramanizda 3.193 ilan bulundu").
- If count <= 1000: It continues and scrapes all pages.
- If count > 1000: It stops immediately, cuts the price range in half, and
  recursively tries again.
"""

import csv
import logging
import os
import random
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver

import config

logger = logging.getLogger(__name__)

_TURKISH_CHAR_MAP = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }
)
_VALID_LOCATION_PREFIXES = {
    "erzincan": {
        "cayirli",
        "ilic",
        "kemah",
        "kemaliye",
        "merkez",
        "otlukbeli",
        "refahiye",
        "tercan",
        "uzumlu",
    }
}


def _normalise_location_token(value: str) -> str:
    return value.strip().translate(_TURKISH_CHAR_MAP).casefold()


def _is_valid_location(city_url_slug: str, district: str) -> bool:
    allowed_prefixes = _VALID_LOCATION_PREFIXES.get(city_url_slug)
    if not allowed_prefixes:
        return True

    top_level = district.split(" / ")[0].strip()
    return _normalise_location_token(top_level) in allowed_prefixes


# -- HTML helpers ----------------------------------------------------------

def _clean_price(price_str: str) -> float:
    """Convert sahibinden price string like '5.000 TL' to float 5000.0"""
    if not price_str:
        return 0.0
    cleaned = price_str.upper().replace("TL", "").strip()
    cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _get_soup(driver: WebDriver) -> BeautifulSoup:
    return BeautifulSoup(driver.page_source, "html.parser")


def _extract_total_listings(soup: BeautifulSoup) -> int | None:
    res_elem = soup.select_one(".result-text")
    if res_elem:
        text = res_elem.get_text(strip=True)
        clean_text = text.replace(".", "")
        match = re.search(r"(\d+)\s*ilan", clean_text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    for tag in soup.find_all(string=lambda t: t and "ilan" in t.lower()):
        parent = tag.parent
        if parent and parent.name not in ["script", "style", "title"]:
            text = tag.strip()
            clean_text = text.replace(".", "")
            match = re.search(r"(\d+)\s*ilan\s*(?:bulundu|var)", clean_text, re.IGNORECASE)
            if match:
                return int(match.group(1))

    return None


def _resolve_rooms_index(soup: BeautifulSoup) -> int | None:
    headers = [
        th.get_text(strip=True)
        for th in soup.select(
            "#searchResultsTable thead th.searchResultsAttributeHeader"
        )
    ]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("\u0131", "i"):
            return idx
    return None


def _parse_listings(
    soup: BeautifulSoup, rooms_idx: int | None, city_url_slug: str
) -> list[dict]:
    records = []
    for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price = price_elem.text.strip() if price_elem else None

            loc_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"

            attrs = row.select(".searchResultsAttributeValue")
            if rooms_idx is not None and len(attrs) > rooms_idx:
                rooms = attrs[rooms_idx].text.strip()
            elif len(attrs) > 1:
                rooms = attrs[1].text.strip()
            else:
                rooms = "N/A"

            if price and _is_valid_location(city_url_slug, district):
                records.append({"product_name": district, "price": _clean_price(price), "Rooms": rooms})
        except Exception as exc:
            logger.debug("Row parse error: %s", exc)

    return records


def _wait_for_listings(driver: WebDriver) -> BeautifulSoup:
    """
    Wait for the listings table to load with a polling loop.
    Retries several times before assuming CAPTCHA/login wall.
    """
    # Initial wait for page to start rendering
    load_delay = max(config.PAGE_LOAD_FLOOR, random.normalvariate(config.PAGE_LOAD_DELAY, config.PAGE_LOAD_STDEV))
    time.sleep(load_delay)

    # Poll for listings up to max_retries times
    max_retries = 5
    retry_delay = 2.0  # seconds between retries

    for attempt in range(max_retries):
        soup = _get_soup(driver)
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

        if listings:
            return soup

        # Check if the page explicitly says "no results"
        page_lower = driver.page_source.lower()
        if "ilan bulunamad\u0131" in page_lower or "bulunamam\u0131\u015ft\u0131r" in page_lower:
            return soup

        if attempt < max_retries - 1:
            logger.debug(
                "Listings not found yet (attempt %d/%d). Waiting %.1fs...",
                attempt + 1, max_retries, retry_delay,
            )
            time.sleep(retry_delay)

    # All retries exhausted - likely CAPTCHA or login wall
    print("\n" + "=" * 55)
    print("\u26a0\ufe0f  ACTION REQUIRED: CAPTCHA or Login wall detected.")
    print("   1. Look at the Chrome window and solve the puzzle.")
    print("   2. Wait until you clearly see the list of houses.")
    print("=" * 55)
    input("   \u25b6 Press ENTER here ONLY AFTER you see the listings... ")

    soup = _get_soup(driver)
    return soup


# -- Core: Adaptive Scrape -------------------------------------------------

def scrape_range(
    sb,
    city_url_slug: str,
    min_price: int,
    max_price: int,
    done_ranges: set[tuple[str, int, int]],
    save_fn,
    save_checkpoint_fn,
    indent: int = 0,
) -> int:
    pad = "  " * indent
    range_key = (city_url_slug, min_price, max_price)

    if range_key in done_ranges:
        logger.info(
            "%s\u21a9  Skipping already-completed range %d-%d TL [%s]",
            pad, min_price, max_price, city_url_slug,
        )
        return 0

    width = max_price - min_price
    logger.info(
        "  Checking range %d-%d TL [%s]...",
        min_price, max_price, city_url_slug,
    )

    url = (
        f"https://www.sahibinden.com/kiralik/{city_url_slug}"
        f"?pagingSize={config.PAGE_SIZE}"
        f"&price_min={min_price}&price_max={max_price}"
    )
    sb.execute_script(f"window.location.href = '{url}';")
    load_delay = max(config.PAGE_LOAD_FLOOR, random.normalvariate(config.PAGE_LOAD_DELAY, config.PAGE_LOAD_STDEV))
    time.sleep(load_delay)

    soup = _wait_for_listings(sb.driver)
    total_listings = _extract_total_listings(soup)

    # -- SPLIT DECISION --
    if (
        total_listings is not None
        and total_listings > config.MAX_LISTINGS_PER_QUERY
        and width > config.MIN_BRACKET_WIDTH
    ):
        logger.info(
            "  Range too dense (%d items). Splitting...",
            total_listings,
        )
        mid = (min_price + max_price) // 2
        total_saved = 0

        total_saved += scrape_range(
            sb, city_url_slug, min_price, mid,
            done_ranges, save_fn, save_checkpoint_fn, indent + 1,
        )
        delay = max(config.BETWEEN_BRACKET_DELAY_FLOOR, random.normalvariate(config.BETWEEN_BRACKET_DELAY_MEAN, config.BETWEEN_BRACKET_DELAY_STDEV))
        time.sleep(delay)
        total_saved += scrape_range(
            sb, city_url_slug, mid + 1, max_price,
            done_ranges, save_fn, save_checkpoint_fn, indent + 1,
        )
        return total_saved

    elif total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY:
        logger.warning(
            "  Min width reached (%d TL) but count (%d) over cap. Scraping capped.",
            width, total_listings,
        )
    elif total_listings is not None:
        logger.info("  Safe range (%d items). Scraping all pages.", total_listings)
    else:
        logger.info("  ? Could not parse total count. Scraping anyway.")

    # -- PERFORM ACTUAL SCRAPE --
    records: list[dict] = []
    rooms_idx: int | None = _resolve_rooms_index(soup)
    page_num = 1

    while True:
        page_records = _parse_listings(soup, rooms_idx, city_url_slug)
        records.extend(page_records)

        if page_records:
            logger.info(
                "  Page %d: %d items (total so far: %d) | %d-%d TL [%s]",
                page_num, len(page_records), len(records),
                min_price, max_price, city_url_slug,
            )

        has_next = bool(soup.find("a", title="Sonraki"))

        if page_num >= 20:
            break

        if has_next:
            next_btn = soup.find("a", title="Sonraki")
            next_url = "https://www.sahibinden.com" + next_btn["href"]
            sb.execute_script(f"window.location.href = '{next_url}';")
            # Page load delay
            load_delay = max(config.PAGE_LOAD_FLOOR, random.normalvariate(config.PAGE_LOAD_DELAY, config.PAGE_LOAD_STDEV))
            time.sleep(load_delay)
            page_num += 1
            # "Human" random wait
            turn_delay = max(config.PAGE_TURN_DELAY_FLOOR, random.normalvariate(config.PAGE_TURN_DELAY_MEAN, config.PAGE_TURN_DELAY_STDEV))
            time.sleep(turn_delay)
            soup = _wait_for_listings(sb.driver)

            if rooms_idx is None:
                rooms_idx = _resolve_rooms_index(soup)
        else:
            break

    if records:
        save_fn(records)
        logger.info(
            "  Saved %d items for %d-%d TL [%s]",
            len(records), min_price, max_price, city_url_slug,
        )

    save_checkpoint_fn(city_url_slug, min_price, max_price)
    done_ranges.add(range_key)
    return len(records)


# -- CSV output ------------------------------------------------------------

def save_incremental(city_name: str, data_batch: list[dict]) -> None:
    if not data_batch:
        return

    output_dir = config.get_city_output_dir(city_name)
    csv_path   = config.get_city_csv_path(city_name)

    os.makedirs(output_dir, exist_ok=True)
    file_exists = os.path.isfile(csv_path)
    if file_exists:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames == ["Product Name", "Product Cost", "Rooms"]:
                rows = [
                    {
                        "product_name": row.get("Product Name", ""),
                        "price": row.get("Product Cost", ""),
                        "Rooms": row.get("Rooms", ""),
                    }
                    for row in reader
                ]
                with open(csv_path, mode="w", newline="", encoding="utf-8") as migrated:
                    writer = csv.DictWriter(migrated, fieldnames=["product_name", "price", "Rooms"])
                    writer.writeheader()
                    writer.writerows(rows)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price", "Rooms"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
