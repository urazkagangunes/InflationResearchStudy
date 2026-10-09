"""CLI entry point and orchestrator for the Golden Rose scraper."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

import requests

import config
from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

LEGACY_HEADER_MAP = {
    "Product Name": "product_name",
    "Product Cost": "price",
}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _load_checkpoint() -> dict:
    if config.CHECKPOINT_FILE.exists():
        return json.loads(config.CHECKPOINT_FILE.read_text(encoding="utf-8"))
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    config.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    config.CHECKPOINT_FILE.write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_row(row: dict) -> dict:
    normalized = dict(row)
    for legacy_key, normalized_key in LEGACY_HEADER_MAP.items():
        if normalized.get(normalized_key) in ("", None) and normalized.get(legacy_key) not in ("", None):
            normalized[normalized_key] = normalized[legacy_key]
    return normalized


def _load_existing_rows() -> dict[str, dict]:
    if not config.CSV_OUTPUT_FILE.exists():
        return {}

    rows: dict[str, dict] = {}
    with config.CSV_OUTPUT_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row = _normalize_row(row)
            product_id = row.get("Product ID", "").strip()
            if product_id:
                rows[product_id] = row
    return rows


def _coalesce(existing: dict, new_record: dict) -> dict:
    merged = dict(existing)
    for key, value in new_record.items():
        if merged.get(key) in ("", None):
            merged[key] = value
        if key == "Stock Quantity":
            try:
                if int(float(value)) > int(float(merged.get(key, 0))):
                    merged[key] = value
            except (TypeError, ValueError):
                pass
        if key == "In Stock" and merged.get(key) == "No" and value == "Yes":
            merged[key] = value
    return merged


def _merge_products(existing_rows: dict[str, dict], new_rows: list[dict]) -> None:
    for row in new_rows:
        row = _normalize_row(row)
        product_id = row.get("Product ID", "").strip()
        if not product_id:
            continue
        if product_id not in existing_rows:
            existing_rows[product_id] = row
            continue
        existing_rows[product_id] = _coalesce(existing_rows[product_id], row)


def _write_snapshot(rows: dict[str, dict]) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(
        rows.values(),
        key=lambda row: (
            config.TOP_LEVEL_PRIORITY.get(row.get("Top Category", ""), 999),
            row.get("Top Category", ""),
            row.get("Leaf Category", ""),
            row.get("product_name", ""),
        ),
    )

    with config.CSV_OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=config.CSV_FIELDNAMES)
        writer.writeheader()
        for row in ordered_rows:
            writer.writerow({field: row.get(field, "") for field in config.CSV_FIELDNAMES})


def _parse_category_filter(raw_values: list[str]) -> set[str]:
    values: set[str] = set()
    for raw in raw_values:
        for part in raw.split(","):
            cleaned = part.strip().casefold()
            if cleaned:
                values.add(cleaned)
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Golden Rose category scraper")
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List discovered top-level categories and exit.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Restrict scraping to one or more top-level categories by slug or name.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum pages to fetch per category (0 = unlimited).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from today's checkpoint and current CSV snapshot.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        help="Delay in seconds between paginated requests.",
    )
    parser.add_argument(
        "--include-promotions",
        action="store_true",
        help="Include 'Yeni Ürünler' and 'Kampanyalar' top-level pages.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    session = _make_session()
    categories = fetch_categories(
        session=session,
        include_promotional=args.include_promotions,
    )

    if args.list_categories:
        for category in categories:
            promo_flag = " [promo]" if category["is_promotional"] else ""
            print(f"{category['name']} ({category['id']}){promo_flag} -> {category['url']}")
        print(f"\nToplam: {len(categories)} kategori")
        return

    selected_filters = _parse_category_filter(args.category)
    if selected_filters:
        categories = [
            item
            for item in categories
            if item["id"].casefold() in selected_filters
            or item["name"].casefold() in selected_filters
        ]
        if not categories:
            raise SystemExit("No Golden Rose categories matched the provided filter.")

    checkpoint = _load_checkpoint() if args.resume else {"done": []}
    completed = set(checkpoint.get("done", []))
    product_rows = _load_existing_rows() if args.resume else {}

    logger.info("Golden Rose scrape starting with %d categories.", len(categories))
    logger.info("CSV output: %s", config.CSV_OUTPUT_FILE)

    for category in categories:
        if args.resume and category["id"] in completed:
            logger.info("Skipping already completed category: %s", category["name"])
            continue

        logger.info("Scraping category: %s", category["name"])
        products = fetch_products_for_category(
            category,
            session=session,
            delay=args.delay,
            page_limit=args.limit,
        )
        logger.info("Finished %s with %d rows before dedup.", category["name"], len(products))

        _merge_products(product_rows, products)
        _write_snapshot(product_rows)

        checkpoint.setdefault("done", []).append(category["id"])
        _save_checkpoint(checkpoint)

        logger.info(
            "Snapshot updated: %d unique Golden Rose products saved.",
            len(product_rows),
        )

    logger.info("Golden Rose scrape complete. Final unique product count: %d", len(product_rows))


if __name__ == "__main__":
    main()
