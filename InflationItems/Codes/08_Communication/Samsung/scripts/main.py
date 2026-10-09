"""
Samsung Türkiye Product Scraper — Main Entry Point
==================================================

Orchestrates category discovery, parallel product extraction,
checkpointing and CSV output for Samsung Türkiye (samsung.com/tr).

Samsung's consumer site is powered by AEM + Hybris and the Product
Finder v2 (``pfv2``) widget fetches each category page's product grid
from a public JSON endpoint on ``searchapi.samsung.com``.  This scraper
queries that endpoint directly — no Selenium / HTML parsing is required.

Pipeline
--------
1. Discover top-level categories via
   ``category_fetcher.fetch_categories`` (curated list in ``config.py``
   augmented with live ``totalRecord`` probes).
2. (Optional) Load today's checkpoint to skip already-completed
   categories.
3. Fan out categories to a ``ThreadPoolExecutor`` — each worker owns
   its own ``requests.Session``.
4. After every completed category: append products to the daily CSV
   and update the checkpoint file.
5. Final deduplication pass on the CSV (by ``id`` / modelCode).
6. Trigger the inflation calculator (best-effort import).

Usage
-----
```bash
# List all available categories (with live family counts)
python main.py --list-categories

# Scrape a single category for testing
python main.py --category smartphones --limit 1

# Full catalog extraction (default: 3 parallel workers)
python main.py

# Resume an interrupted run
python main.py --resume
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
from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

# ── Inflation module (best-effort import) ────────────────────────────────────
# Add the location of inflation.py to sys.path so we can call it after a
# successful scrape, mirroring the Migros / Rossmann / Bauhaus convention.
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "..",
    "Inflations", "Codes", "TechnologicalProducts", "Samsung",
)
sys.path.append(os.path.abspath(_inflation_dir))
try:
    import inflation  # type: ignore
except ImportError as e:
    inflation = None
    print(f"Warning: Could not import inflation module: {e}")

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
    """Load today's checkpoint file from disk.

    Returns
    -------
    dict
        Parsed checkpoint dict.  Schema: ``{"done": [<category_id>, ...]}``.
        Returns ``{"done": []}`` when the checkpoint file does not yet
        exist, which is the expected state on a fresh daily run.
    """
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    """Write ``checkpoint`` to :data:`config.CHECKPOINT_FILE` atomically."""
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with _checkpoint_lock:
        tmp = config.CHECKPOINT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        os.replace(tmp, config.CHECKPOINT_FILE)


# ── Output helpers ───────────────────────────────────────────────────────────

def _append_products(new_products: list[dict]) -> None:
    """Thread-safely append ``new_products`` to the daily CSV output file.

    Called immediately after each category is scraped so that data is
    persisted to disk even if the process is interrupted mid-run.  The
    header is written only on first append (``mode="a"``).  Uses
    UTF-8-with-BOM encoding for wide Excel compatibility.
    """
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
    """Remove rows with duplicate ``id`` values from the daily CSV in-place.

    Samsung's mobile-accessories category occasionally features the
    same SKU under multiple top-level categories (e.g. a Galaxy Buds
    case appears both under ``mobile-accessories`` and ``audio-sound``
    as a "related" item).  This final pass drops those duplicates on
    the ``id`` column.
    """
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    if "id" in df.columns:
        df.drop_duplicates(subset=["id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info(
            "Removed %d duplicate rows. Final count: %d",
            before - len(df), len(df),
        )
    return len(df)


# ── Per-worker session factory ──────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a new ``requests.Session`` with the default pfv2 headers."""
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Worker (runs in a thread) ────────────────────────────────────────────────

def _scrape_category_worker(
    cat: dict,
    delay: float,
    page_limit: int,
) -> list[dict]:
    """Scrape one category in an isolated worker thread."""
    session = _make_session()
    return fetch_products_for_category(
        category=cat,
        session=session,
        delay=delay,
        page_limit=page_limit,
    )


# ── Core scraping logic ──────────────────────────────────────────────────────

def run_scraper(args: argparse.Namespace) -> None:
    """Execute the full scraping pipeline according to parsed CLI arguments.

    Steps
    -----
    1. Fetch the full category list (single-threaded bootstrap).
    2. Optionally filter to a single ``--category`` ID, slug or type code.
    3. Load (or initialise) today's checkpoint.
    4. Clear stale output files when not resuming.
    5. Dispatch remaining categories to a ``ThreadPoolExecutor``; save
       products and update the checkpoint after every completed category.
    6. Run a final deduplication pass on the output file.
    7. Trigger the inflation calculator (when the module is importable).
    """
    # 1. Fetch categories (single-threaded bootstrap)
    logger.info("Fetching category list...")
    bootstrap_session = _make_session()
    try:
        categories = fetch_categories(session=bootstrap_session)
    except Exception as exc:
        logger.error("Could not fetch categories: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("No categories found. Exiting.")
        sys.exit(1)

    # 2. Filter to a single category if requested.  Accept either the
    #    slug id (``smartphones``), the 8-digit type code (``01010000``)
    #    or a case-insensitive display name match.
    if args.category:
        want = args.category.strip().lower()
        filtered = [
            c for c in categories
            if c["id"].lower() == want
            or c["type"] == want
            or c["name"].lower() == want
        ]
        if not filtered:
            logger.error(
                "Category '%s' not found. Use --list-categories to see IDs.",
                args.category,
            )
            sys.exit(1)
        categories = filtered

    # 3. Load checkpoint for resume support.
    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    # 4. On a fresh run, clear any old output file for today.
    if not args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("Cleared old output file: %s", config.CSV_OUTPUT_FILE)

    categories_to_scrape = [
        c for c in categories if c["id"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info(
            "All categories already scraped. Run without --resume to start fresh."
        )
        return

    total_products = 0

    # Count products already in the CSV (when resuming).
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "Resuming: %d existing products already saved in %s",
                total_products, config.CSV_OUTPUT_FILE,
            )
        except Exception as exc:
            logger.warning("Could not count existing products: %s", exc)

    logger.info(
        "Scraping %d categor%s with %d worker(s)...",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
        args.workers,
    )

    # 5. Parallel scraping with ThreadPoolExecutor.
    futures = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for cat in categories_to_scrape:
            future = executor.submit(
                _scrape_category_worker, cat, args.delay, args.limit,
            )
            futures[future] = cat

        with tqdm(total=len(futures), unit="category", desc="Categories") as pbar:
            for future in as_completed(futures):
                cat = futures[future]
                pbar.set_postfix_str(cat["name"])
                try:
                    cat_products = future.result()
                except Exception as exc:
                    logger.error("Category '%s' failed: %s", cat["name"], exc)
                    cat_products = []

                # Persist immediately so nothing is lost on interruption.
                if cat_products:
                    _append_products(cat_products)
                    with _counter_lock:
                        total_products += len(cat_products)

                # Mark category done in checkpoint.
                with _checkpoint_lock:
                    checkpoint["done"].append(cat["id"])
                _save_checkpoint(checkpoint)

                if cat_products:
                    logger.info(
                        "Category '%s': +%d products (total so far: %d)",
                        cat["name"], len(cat_products), total_products,
                    )

                pbar.update(1)

    # 6. Final deduplication pass.
    logger.info("Running final deduplication...")
    final_count = _dedup_csv()

    logger.info("Done! Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)

    # 7. Calculate Inflation (no-op if the inflation module is unavailable).
    if inflation is not None:
        logger.info("Calculating inflation metrics...")
        try:
            inflation.calculate_inflation()
        except Exception as e:
            logger.error("Failed to calculate inflation: %s", e)
    else:
        logger.warning("Skipping inflation calculation (module not imported).")


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="samsung-scraper",
        description=(
            "Scrape all product data from Samsung Türkiye (samsung.com/tr) "
            "via its public Product Finder v2 JSON API and output to CSV."
        ),
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
        metavar="ID_OR_TYPE",
        default=None,
        help=(
            "Scrape only this category. Accepts the slug id (e.g. "
            "'smartphones'), the 8-digit type code (e.g. '01010000') "
            "or the display name (e.g. 'Smartphones')."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config.DEFAULT_WORKERS,
        metavar="N",
        help=f"Parallel category workers (default: {config.DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SECONDS",
        help=(
            "Base delay between page requests per worker in seconds "
            f"(default: {config.REQUEST_DELAY})."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="PAGES",
        help="Maximum pages to scrape per category (0 = unlimited).",
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
    """Parse CLI arguments and run the appropriate action."""
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

        print(f"\n{'type':<10} {'id':<22} {'count':<7} {'Name'}")
        print("-" * 70)
        for cat in categories:
            count = cat.get("product_count")
            print(
                f"{cat['type']:<10} {cat['id']:<22} "
                f"{('?' if count is None else count):<7} {cat['name']}"
            )
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
