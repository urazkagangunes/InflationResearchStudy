"""
Koton Türkiye Product Scraper - Main Entry Point and Orchestration Layer
=========================================================================

This module serves as the primary interface for the Koton product scraping system,
providing comprehensive CLI functionality and coordinating all scraping operations
through a modular, multi-threaded architecture.

Core Responsibilities
----------------------
- Command-line argument parsing and validation
- XML sitemap-based category discovery coordination
- Parallel product extraction using ThreadPoolExecutor
- Incremental data persistence and checkpoint management
- Cross-category product deduplication
- CSV data export with standardized formatting

Execution Pipeline
-----------------
1. Category Discovery: Downloads and parses compressed XML sitemap to extract complete taxonomy
2. Checkpoint Management: Loads previous session state when resume mode is enabled
3. Parallel Processing: Dispatches categories to worker threads with independent sessions
4. Incremental Persistence: Saves data and checkpoints after each category completion
5. Data Deduplication: Removes duplicate products across category boundaries
6. Export Generation: Creates CSV output file with UTF-8 BOM formatting

Threading Model
---------------
- ThreadPoolExecutor manages concurrent category processing
- Each worker maintains an independent requests.Session with unique User-Agent
- No session sharing across threads prevents race conditions
- Configurable worker count allows performance tuning

Anti-Detection Features
----------------------
- User-Agent rotation across 7 realistic browser signatures
- Per-thread User-Agent assignment for consistency
- Configurable rate limiting with random jitter
- Exponential backoff for failed requests

Output Management
-----------------
All file paths are resolved relative to the config.py location, ensuring
consistent operation regardless of execution directory:

- CSV Export: UTF-8 with BOM formatting for Excel compatibility
- Checkpoint Files: Daily session state for resume capability

CLI Interface
-------------
The module provides comprehensive command-line options including:
- Category listing and selective scraping
- Performance tuning (workers, delays, limits)
- Session management (resume functionality)
- Debug mode with verbose logging

Usage Examples
--------------
```bash
# List all available categories
python main.py --list-categories

# Scrape single category for testing
python main.py --category kadin-giyim --limit 1

# Full catalog extraction with parallel processing
python main.py --workers 2

# Rate-limited scraping with custom delay
python main.py --delay 1.5

# Resume interrupted session
python main.py --resume

# Enable debug logging
python main.py --category kadin-giyim -v
```
"""

import argparse
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tqdm import tqdm

import config
import sys
import os

# Add the new location of inflation.py to sys.path
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", "..", "..", "Inflations", "Codes", "ClothingStores", "Koton"
)
sys.path.append(os.path.abspath(_inflation_dir))
import inflation

from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Thread-safety locks ──────────────────────────────────────────────────────
_csv_lock        = threading.Lock()
_checkpoint_lock = threading.Lock()
_counter_lock    = threading.Lock()


# ── Checkpoint helpers ───────────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with _checkpoint_lock:
        with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Output helpers ───────────────────────────────────────────────────────────

def _append_products(new_products: list[dict]) -> None:
    """Thread-safe append of new products to the CSV file."""
    if not new_products:
        return
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)
    with _csv_lock:
        write_header = not os.path.exists(config.CSV_OUTPUT_FILE)
        df_new.to_csv(
            config.CSV_OUTPUT_FILE,
            mode="a",
            index=False,
            header=write_header,
            encoding="utf-8-sig",
        )


def _dedup_csv() -> int:
    """Remove duplicate rows by (pk, sku, name). Returns final row count."""
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    dedup_cols = [c for c in ["pk", "sku", "name"] if c in df.columns]
    if dedup_cols:
        df.drop_duplicates(subset=dedup_cols, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info("Removed %d duplicate rows. Final count: %d", before - len(df), len(df))
    return len(df)


# ── Per-worker session factory ───────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Worker function (runs in a thread) ──────────────────────────────────────

def _scrape_category(cat: dict, delay: float, page_limit: int) -> list[dict]:
    """Scrape one category in its own thread with its own Session."""
    session = _make_session()
    return fetch_products_for_category(
        category=cat,
        session=session,
        delay=delay,
        page_limit=page_limit,
    )


# ── Core scraping logic ──────────────────────────────────────────────────────

def run_scraper(args: argparse.Namespace) -> None:
    # 1. Fetch category list (single-threaded bootstrap)
    logger.info("▶  Fetching category list...")
    bootstrap_session = _make_session()
    try:
        categories = fetch_categories(session=bootstrap_session)
    except Exception as exc:
        logger.error("✗  Could not fetch categories: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("✗  No categories found. Exiting.")
        sys.exit(1)

    # 2. Filter to main categories only (single-word or short categories)
    # Main categories according to Koton's sitemap slugs.
    # "cocuk" already contains all cocuk-kiz-cocuk + cocuk-erkek-cocuk products.
    # "bebek" already contains all bebek-kiz-bebek + bebek-erkek-bebek products.
    # Including both parent and children would double the work for those segments.
    MAIN_CATEGORIES = [
        "kadin", "erkek", "cocuk", "bebek", "evcil-hayvan-kiyafetleri"
    ]
    
    # Filter to main categories only
    categories = [c for c in categories if c["slug"] in MAIN_CATEGORIES]
    logger.info("✓  Filtered to %d main categories: %s", 
                len(categories), ", ".join(c["slug"] for c in categories))
    
    # 3. Filter to a single category if requested
    if args.category:
        categories = [c for c in categories if c["slug"] == args.category]
        if not categories:
            logger.error(
                "✗  Category '%s' not found. Use --list-categories to see available slugs.",
                args.category,
            )
            sys.exit(1)

    # 4. Load checkpoint for resume support
    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    # 5. On a fresh run, clear old output file for today
    if not args.resume:
        if os.path.exists(config.CSV_OUTPUT_FILE):
            os.remove(config.CSV_OUTPUT_FILE)
            logger.info("🗑  Cleared old CSV: %s", config.CSV_OUTPUT_FILE)

    categories_to_scrape = [
        c for c in categories if c["slug"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info("✓  All categories already scraped. Run without --resume to start fresh.")
        return

    total_products = 0

    # Count existing products when resuming
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "↩  Resuming: %d existing products already saved.", total_products
            )
        except Exception as exc:
            logger.warning("⚠  Could not count existing products: %s", exc)

    logger.info(
        "▶  Scraping %d categor%s with %d worker(s)...",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
        args.workers,
    )

    # 6. Parallel scraping with ThreadPoolExecutor
    import time
    start_time = time.time()
    futures = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for cat in categories_to_scrape:
            future = executor.submit(_scrape_category, cat, args.delay, args.limit)
            futures[future] = cat

        with tqdm(total=len(futures), unit="category", desc="Categories") as pbar:
            for future in as_completed(futures):
                cat = futures[future]
                pbar.set_postfix_str(cat["name"])
                try:
                    cat_products = future.result()
                except Exception as exc:
                    logger.error("✗  Category '%s' failed: %s", cat["name"], exc)
                    cat_products = []

                # Save immediately after each category — no data lost on interruption
                if cat_products:
                    _append_products(cat_products)
                    with _counter_lock:
                        total_products += len(cat_products)

                # Mark category done in checkpoint
                with _checkpoint_lock:
                    checkpoint["done"].append(cat["slug"])
                _save_checkpoint(checkpoint)

                if cat_products:
                    logger.info(
                        "✓  Category '%s': +%d products (total: %d)",
                        cat["name"], len(cat_products), total_products,
                    )
                    logger.info("💾 Checkpoint saved")

                pbar.update(1)

    # 7. Calculate elapsed time
    elapsed_time = time.time() - start_time
    logger.info("⏱  Scraping completed in %.1f seconds (%.1f min)", elapsed_time, elapsed_time / 60)

    # 8. Final deduplication pass
    logger.info("🔄 Running final deduplication...")
    final_count = _dedup_csv()
    logger.info("Done! ✓  Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)

    # 9. Calculate Inflation
    logger.info("📈 Calculating inflation metrics...")
    try:
        inflation.calculate_inflation()
        logger.info("✅ Inflation calculation complete")
    except Exception as e:
        logger.error("✗  Failed to calculate inflation: %s", e)



# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="koton-scraper",
        description="Scrape all product data from Koton Türkiye (koton.com).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Print all available categories and exit.",
    )
    parser.add_argument(
        "--category",
        metavar="SLUG",
        default=None,
        help="Scrape only this category slug (e.g. 'kadin-giyim'). Omit to scrape all.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel category workers (default: 1, increase carefully to avoid rate-limits).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SECONDS",
        help=f"Delay between page requests per worker in seconds (default: {config.REQUEST_DELAY}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="PAGES",
        help="Maximum pages to scrape per category (0 = unlimited, useful for testing).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip categories already listed in the checkpoint file.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_categories:
        session = _make_session()
        try:
            categories = fetch_categories(session=session)
        except Exception as exc:
            logger.error(str(exc))
            sys.exit(1)

        print(f"\n{'Slug':<35} {'Name'}")
        print("-" * 60)
        for cat in categories:
            parent = f"  (sub of {cat['parent_slug']})" if cat.get("parent_slug") else ""
            print(f"{cat['slug']:<35} {cat['name']}{parent}")
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
