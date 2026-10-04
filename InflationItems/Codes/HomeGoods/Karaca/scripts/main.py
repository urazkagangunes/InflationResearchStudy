"""CLI entry point and orchestrator for the Karaca scraper."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:
    from . import config
    from .category_fetcher import fetch_categories
    from .product_fetcher import fetch_products_for_category
except ImportError:
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


def _scrape_category_worker(
    category: dict,
    delay: float,
    page_limit: int,
) -> tuple[dict, object]:
    session = _make_session()
    logger.info(
        "Scraping category: %s [%s]",
        category["name"],
        category["main_category"],
    )
    result = fetch_products_for_category(
        category,
        session=session,
        delay=delay,
        page_limit=page_limit,
    )
    logger.info("Finished %s with %d rows before dedup.", category["name"], len(result.products))
    return category, result


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
    if not config.PARTIAL_FILE.exists():
        return {}

    rows: dict[str, dict] = {}
    with config.PARTIAL_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
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


def _category_rank(row: dict) -> tuple[int, int]:
    # Categories finish in parallel, so a fixed preference keeps the category
    # columns of cross-listed products stable from day to day.
    return (
        0 if row.get("_primary") else 1,
        config.MAIN_CATEGORY_PRIORITY.get(row.get("Main Category", ""), 999),
    )


def _merge_products(existing_rows: dict[str, dict], new_rows: list[dict]) -> None:
    for row in new_rows:
        row = _normalize_row(row)
        product_id = row.get("Product ID", "").strip()
        if not product_id:
            continue
        if product_id not in existing_rows:
            existing_rows[product_id] = row
            continue
        existing = existing_rows[product_id]
        if _category_rank(row) < _category_rank(existing):
            existing_rows[product_id] = _coalesce(row, existing)
        else:
            existing_rows[product_id] = _coalesce(existing, row)


def _write_snapshot(rows: dict[str, dict], path, fieldnames=config.CSV_FIELDNAMES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(
        rows.values(),
        key=lambda row: (
            config.MAIN_CATEGORY_PRIORITY.get(row.get("Main Category", ""), 999),
            row.get("Main Category", ""),
            row.get("Top Category", ""),
            row.get("product_name", ""),
        ),
    )

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in ordered_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _persist_category_result(
    category: dict,
    result,
    product_rows: dict[str, dict],
    checkpoint: dict,
) -> bool:
    _merge_products(product_rows, result.products)
    _write_snapshot(product_rows, config.PARTIAL_FILE)

    done = checkpoint.setdefault("done", [])
    if result.complete:
        if category["id"] not in done:
            done.append(category["id"])
        _save_checkpoint(checkpoint)
    else:
        logger.warning(
            "Category '%s' was not checkpointed as complete because the scrape stopped early.",
            category["name"],
        )

    logger.info(
        "Snapshot updated: %d unique Karaca products saved.",
        len(product_rows),
    )
    return result.complete


def _parse_category_filter(raw_values: list[str]) -> set[str]:
    values: set[str] = set()
    for raw in raw_values:
        for part in raw.split(","):
            cleaned = part.strip().casefold()
            if cleaned:
                values.add(cleaned)
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Karaca category scraper")
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List discovered navigation categories and exit.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Restrict scraping to categories by slug, name or menu group name.",
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
        help="Minimum delay in seconds between paginated requests (randomised up to 3x).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config.CATEGORY_WORKERS,
        help="Number of Karaca categories to scrape in parallel.",
    )
    parser.add_argument(
        "--include-promotions",
        action="store_true",
        help="Include gift, campaign, and promotional landing categories.",
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
            print(
                f"{category['name']} ({category['id']}){promo_flag} "
                f"[{category['main_category']}] -> {category['url']}"
            )
        print(f"\nToplam: {len(categories)} kategori")
        return

    selected_filters = _parse_category_filter(args.category)
    if selected_filters:
        categories = [
            item
            for item in categories
            if item["id"].casefold() in selected_filters
            or item["name"].casefold() in selected_filters
            or item["main_category"].casefold() in selected_filters
        ]
        if not categories:
            raise SystemExit("No Karaca categories matched the provided filter.")

    checkpoint = _load_checkpoint() if args.resume else {"done": []}
    completed = set(checkpoint.get("done", []))
    product_rows = _load_existing_rows() if args.resume else {}

    if not args.resume:
        _save_checkpoint(checkpoint)

    pending_categories = []
    for category in categories:
        if args.resume and category["id"] in completed:
            logger.info("Skipping already completed category: %s", category["name"])
            continue
        pending_categories.append(category)

    logger.info(
        "Karaca scrape starting with %d categories (%d pending) using %d worker(s).",
        len(categories),
        len(pending_categories),
        max(1, args.workers),
    )
    logger.info("CSV output: %s", config.CSV_OUTPUT_FILE)

    failed: list[dict] = []
    worker_count = max(1, args.workers)

    if not pending_categories:
        logger.info("No pending Karaca categories remain for today.")
    elif worker_count == 1 or len(pending_categories) == 1:
        for category in pending_categories:
            try:
                category_result, result = _scrape_category_worker(
                    category,
                    args.delay,
                    args.limit,
                )
            except Exception as exc:
                logger.error("Category '%s' failed: %s", category["name"], exc)
                failed.append(category)
                continue
            if not _persist_category_result(category_result, result, product_rows, checkpoint) and not args.limit:
                failed.append(category)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _scrape_category_worker,
                    category,
                    args.delay,
                    args.limit,
                ): category
                for category in pending_categories
            }

            for future in as_completed(futures):
                category = futures[future]
                try:
                    category_result, result = future.result()
                except Exception as exc:
                    logger.error("Category '%s' failed: %s", category["name"], exc)
                    failed.append(category)
                    continue
                if not _persist_category_result(category_result, result, product_rows, checkpoint) and not args.limit:
                    failed.append(category)

    # A --limit run stops categories early on purpose, so only exceptions are retried there.
    failures: list[str] = []
    for category in failed:
        logger.info("Retrying category '%s' once.", category["name"])
        try:
            category_result, result = _scrape_category_worker(category, args.delay, args.limit)
        except Exception as exc:
            logger.error("Category '%s' failed again: %s", category["name"], exc)
            failures.append(category["name"])
            continue
        complete = _persist_category_result(category_result, result, product_rows, checkpoint)
        if not complete and not args.limit:
            failures.append(category["name"])

    logger.info("Karaca scrape finished. Unique product count: %d", len(product_rows))
    # The daily runner counts any CSV as success, so a partial catalogue must not produce one.
    if failures:
        raise SystemExit(
            "Karaca categories incomplete: " + ", ".join(sorted(failures))
            + f". No CSV written; rows kept in {config.PARTIAL_FILE} for --resume."
        )
    if not product_rows:
        raise SystemExit("Karaca scrape produced no products. No CSV written.")

    in_scope = {
        key: row for key, row in product_rows.items()
        if row.get("Top Category", "") not in config.EXCLUDED_TOP_CATEGORIES
    }
    logger.info(
        "Out of scope (food): %d; written: %d.",
        len(product_rows) - len(in_scope),
        len(in_scope),
    )
    _write_snapshot(in_scope, config.CSV_OUTPUT_FILE, config.OUTPUT_FIELDNAMES)
    config.PARTIAL_FILE.unlink(missing_ok=True)
    logger.info("CSV written: %s", config.CSV_OUTPUT_FILE)


if __name__ == "__main__":
    main()
