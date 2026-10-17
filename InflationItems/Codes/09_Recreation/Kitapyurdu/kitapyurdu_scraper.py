import argparse
import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("KitapyurduScraper")


BASE_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = next(
    (p for p in BASE_DIR.parents if (p / ".git").exists()),
    BASE_DIR
)

DATA_DIR = (
    PROJECT_ROOT
    / "InflationItems"
    / "Datas"
    / "09_Recreation"
    / "Kitapyurdu"
)


CATEGORIES = {
    "children_books": 2,
    "textbooks": 298,
    "test_books": 737,
    "other_books": 342
}

CATEGORY_NUMBER = "09"

SUB_CATEGORY_NUMBERS = {
    "children_books": "0971901",
    "textbooks": "0971103",
    "test_books": "0971102",
    "other_books": "0971902"
}

MAX_PAGES = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def fetch_html(url, timeout=30):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout
    )

    response.raise_for_status()
    return response.text


def convert_price(price_text):
    price_text = (
        price_text
        .replace("TL", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )

    return float(price_text)


def scrape_category(category_name, category_id):
    results = []
    seen = set()

    logger.info("Starting category: %s", category_name)

    for page_number in range(1, MAX_PAGES + 1):

        url = (
            "https://www.kitapyurdu.com/index.php"
            f"?category_id={category_id}"
            f"&page={page_number}"
            "&route=product/list"
        )

        success = False

        for attempt in range(1, 4):

            logger.info(
                "%s - page %d - attempt %d/3",
                category_name,
                page_number,
                attempt
            )

            try:
                html = fetch_html(url)

                soup = BeautifulSoup(
                    html,
                    "html.parser"
                )

                products = soup.select(
                    "div.ky-product"
                )

                if not products:
                    logger.warning(
                        "No products found: %s page %d",
                        category_name,
                        page_number
                    )

                    time.sleep(3 * attempt)
                    continue

                logger.info(
                    "Found %d products",
                    len(products)
                )

                for product in products:

                    name = None

                    links = product.find_all(
                        "a",
                        href=lambda href:
                            href and "/kitap/" in href
                    )

                    for link in links:
                        text = link.get_text(
                            " ",
                            strip=True
                        )

                        if text:
                            name = text
                            break

                    price_box = product.select_one(
                        "p.ky-product-price-label "
                        "span.fw-bold"
                    )

                    if name is None or price_box is None:
                        continue

                    if category_name == "other_books":

                        excluded_words = [
                            "dergi",
                            "ajanda",
                            "takvim",
                            "albüm"
                        ]

                        lower_name = name.lower()

                        if any(
                            word in lower_name
                            for word in excluded_words
                        ):
                            continue

                    price_text = price_box.get_text(
                        " ",
                        strip=True
                    )

                    try:
                        price = convert_price(
                            price_text
                        )
                    except ValueError:
                        continue

                    if price <= 0:
                        continue

                    key = name.strip().lower()

                    if key in seen:
                        continue

                    seen.add(key)

                    results.append(
                        (name, price)
                    )

                success = True
                break

            except Exception as exc:
                logger.warning(
                    "%s page %d failed "
                    "(attempt %d): %s",
                    category_name,
                    page_number,
                    attempt,
                    exc
                )

                time.sleep(3 * attempt)

        if not success:
            logger.error(
                "Skipping %s page %d",
                category_name,
                page_number
            )

        time.sleep(2)

    logger.info(
        "%s: extracted %d unique products",
        category_name,
        len(results)
    )

    return results


def save_to_csv(data, date_str):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        DATA_DIR
        / f"kitapyurdu_{date_str}.csv"
    )

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "product_name",
            "price",
            "category_number",
            "sub_category_number"
        ])

        for name, price, category in sorted(
            data,
            key=lambda x: x[0]
        ):

            writer.writerow([
                name,
                f"{price:.2f}",
                CATEGORY_NUMBER,
                SUB_CATEGORY_NUMBERS[category]
            ])

    logger.info(
        "Saved %d products to %s",
        len(data),
        output_file
    )

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Kitapyurdu Book Scraper"
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None
    )

    args = parser.parse_args()

    date_str = (
        args.date
        or datetime.today().strftime("%Y-%m-%d")
    )

    all_items = []
    global_seen = set()

    for category_name, category_id in CATEGORIES.items():

        items = scrape_category(
            category_name,
            category_id
        )

        for name, price in items:

            key = name.strip().lower()

            if key in global_seen:
                continue

            global_seen.add(key)

            all_items.append(
                (
                    name,
                    price,
                    category_name
                )
            )

    if not all_items:
        logger.error("No products scraped.")
        sys.exit(1)

    output_file = save_to_csv(
        all_items,
        date_str
    )

    print()
    print("----------------------------")
    print("Scraping completed.")
    print("Total unique products:", len(all_items))
    print("File:", output_file)
    print("----------------------------")


if __name__ == "__main__":
    main()
