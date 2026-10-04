"""
Vivense Türkiye Product Scraper — Main Entry Point
==================================================

Orchestrates category discovery, parallel product extraction,
checkpointing and CSV output for Vivense (vivense.com).

Vivense renders product cards directly into category HTML — there is
no public API — so the scraper hits each ``/<slug>.html?page=N`` URL,
parses the embedded ``data-*`` attributes, and walks pagination until
an empty page is returned.

Pipeline
--------
1. Resolve the curated top-level category list via
   ``category_fetcher.fetch_categories``.
2. (Optional) Load today's checkpoint to skip already-completed
   categories.
3. Fan out categories to a ``ThreadPoolExecutor`` — each worker owns
   its own ``requests.Session`` to avoid race conditions.
4. After every completed category: append products to the daily CSV
   and update the checkpoint file.
5. Final deduplication pass on the CSV (by product ``id``).
6. Trigger the inflation calculator (best-effort).

Usage
-----
```bash
# List all available categories
python main.py --list-categories

# Scrape a single category (for testing)
python main.py --category oturma-odasi-mobilyalari --limit 1

# Full catalog extraction with the default number of workers
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
    "Inflations", "Codes", "HomeGoods", "Vivense",
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
        Parsed checkpoint dict.  Schema:
        ``{"done": [<category_id>, ...]}``.  Returns
        ``{"done": []}`` when the checkpoint file does not yet exist
        (i.e. the expected state on a fresh daily run).
    """
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    """Atomically write ``checkpoint`` to :data:`config.CHECKPOINT_FILE`.

    Creates :data:`config.CHECKPOINT_DIR` if it does not yet exist and
    serialises ``checkpoint`` as UTF-8 JSON.  The write is protected by
    ``_checkpoint_lock`` so concurrent worker threads cannot corrupt
    the file.

    Args
    ----
    checkpoint : dict
        Checkpoint dict to serialise.  Expected schema:
        ``{"done": [<category_id>, ...]}``.
    """
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with _checkpoint_lock:
        with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Output helpers ───────────────────────────────────────────────────────────

def _append_products(new_products: list[dict]) -> None:
    """Thread-safely append ``new_products`` to the staging file.

    Called immediately after each category is scraped so that data is
    persisted to disk even if the process is interrupted mid-run.  The
    staging file (:data:`config.PARTIAL_FILE`) is not a ``.csv`` and lives
    outside the folders the daily runner scans, so a failed run never
    leaves a CSV the runner would count as success.  The
    header is written only on the first append (``mode="a"``).  Uses
    UTF-8-with-BOM encoding for wide Excel compatibility.

    Writing is serialised via ``_csv_lock`` so concurrent worker threads
    never interleave their writes.

    Args
    ----
    new_products : list[dict]
        Products scraped from a single category (as returned by
        :func:`product_fetcher.fetch_products_for_category`).  A no-op
        when the list is empty.
    """
    if not new_products:
        return

    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)

    with _csv_lock:
        write_header = not os.path.exists(config.PARTIAL_FILE)
        df_new.to_csv(
            config.PARTIAL_FILE,
            mode="a",
            index=False,
            header=write_header,
            encoding="utf-8-sig",
        )


def _dedup_csv() -> int:
    """Write the deduplicated staging rows to the daily CSV.

    Reads the staging file, drops duplicates on the ``id`` column (keeping
    the first occurrence), writes the daily CSV and removes the staging
    file.  Run once at the very end of a successful scrape to clean up
    products that appear in multiple categories (e.g. decorative items that
    Vivense files under both *Ev Dekorasyonu* and *Sofra*).

    Returns
    -------
    int
        Number of rows in the daily CSV.  Returns ``0`` when the staging
        file does not exist (e.g. no products were scraped).
    """
    if not os.path.exists(config.PARTIAL_FILE):
        return 0
    df = pd.read_csv(config.PARTIAL_FILE, encoding="utf-8-sig")
    before = len(df)
    if "id" in df.columns:
        df.drop_duplicates(subset=["id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df[config.OUTPUT_COLUMNS].to_csv(
        config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig",
    )
    os.remove(config.PARTIAL_FILE)
    if len(df) < before:
        logger.info(
            "Removed %d duplicate rows. Final count: %d",
            before - len(df), len(df),
        )
    return len(df)


# ── Per-worker session factory ───────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a fresh ``requests.Session`` pre-loaded with default headers.

    Each worker thread calls this to obtain its own independent session,
    preventing cross-thread state sharing on the connection pool.

    Returns
    -------
    requests.Session
        A session with :data:`config.DEFAULT_HEADERS` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Worker (runs in a thread) ────────────────────────────────────────────────

def _scrape_category_worker(
    cat: dict,
    delay: float,
    page_limit: int,
) -> list[dict]:
    """Scrape one category in an isolated worker thread.

    Creates a private :class:`requests.Session` so it does not share
    connection state with the other workers, then delegates to
    :func:`product_fetcher.fetch_products_for_category`.  A category that
    raises (fetch failure or coverage below 90 %) is retried once from
    page 1; a second failure propagates to the caller.

    Args
    ----
    cat : dict
        Category dict as returned by
        :func:`category_fetcher.fetch_categories` (must contain ``id``,
        ``name`` and ``url``).
    delay : float
        Base inter-page sleep in seconds (jitter is applied inside the
        product fetcher).
    page_limit : int
        Maximum pages to fetch per category (``0`` = unlimited).

    Returns
    -------
    list[dict]
        Normalised product records for every page of ``cat``.
    """
    try:
        return fetch_products_for_category(
            category=cat,
            session=_make_session(),
            delay=delay,
            page_limit=page_limit,
        )
    except Exception as exc:
        logger.warning(
            "Category '%s' failed (%r); retrying once from the start.",
            cat["name"], exc,
        )
    return fetch_products_for_category(
        category=cat,
        session=_make_session(),
        delay=delay,
        page_limit=page_limit,
    )


# ── Core scraping logic ──────────────────────────────────────────────────────

def run_scraper(args: argparse.Namespace) -> None:
    """Execute the full scraping pipeline according to parsed CLI arguments.

    Steps
    -----
    1. Resolve the curated category list (single-threaded bootstrap).
    2. Optionally filter to a single ``--category`` ID.
    3. Load (or initialise) today's checkpoint.
    4. Clear any stale output file when not resuming.
    5. Dispatch remaining categories to a
       :class:`~concurrent.futures.ThreadPoolExecutor`; persist products
       and update the checkpoint after every completed category.
    6. Run a final deduplication pass on the output file.
    7. Trigger the inflation calculator (when the module is importable).

    Args
    ----
    args : argparse.Namespace
        Parsed command-line arguments produced by
        ``_build_parser().parse_args()``.  Expected attributes:
        ``category``, ``workers``, ``delay``, ``limit``, ``resume``.
    """
    # 1. Resolve categories (single-threaded bootstrap)
    logger.info("Loading category list...")
    try:
        categories = fetch_categories(session=_make_session())
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Could not load categories: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("No categories found. Exiting.")
        sys.exit(1)

    # 2. Filter to a single category if requested
    if args.category:
        categories = [c for c in categories if c["id"] == args.category]
        if not categories:
            logger.error(
                "Category '%s' not found. Use --list-categories to see IDs.",
                args.category,
            )
            sys.exit(1)

    # 3. Load checkpoint for resume support
    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    # 4. On a fresh run, clear any old output and staging file for today
    if not args.resume:
        for path in (config.CSV_OUTPUT_FILE, config.PARTIAL_FILE):
            if os.path.exists(path):
                os.remove(path)
                logger.info("Cleared old file: %s", path)

    categories_to_scrape = [
        c for c in categories if c["id"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info(
            "All categories already scraped. Run without --resume to start fresh."
        )
        return

    total_products = 0
    if args.resume and os.path.exists(config.PARTIAL_FILE):
        try:
            existing_df = pd.read_csv(config.PARTIAL_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "Resuming: %d existing products already saved in %s",
                total_products, config.PARTIAL_FILE,
            )
        except Exception as exc:
            logger.warning("Could not count existing products: %s", exc)

    logger.info(
        "Scraping %d categor%s with %d worker(s)...",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
        args.workers,
    )

    # 5. Parallel scraping with ThreadPoolExecutor
    futures = {}
    failed: list[tuple[str, str]] = []
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
                    logger.exception(
                        "Category '%s' failed: %r", cat["name"], exc,
                    )
                    failed.append((cat["name"], repr(exc)))
                    cat_products = None

                # Persist immediately so nothing is lost on interruption
                if cat_products:
                    _append_products(cat_products)
                    with _counter_lock:
                        total_products += len(cat_products)

                # Failed categories stay out of the checkpoint so that
                # --resume retries them.
                if cat_products is not None:
                    with _checkpoint_lock:
                        checkpoint["done"].append(cat["id"])
                    _save_checkpoint(checkpoint)

                if cat_products:
                    logger.info(
                        "Category '%s': +%d products (total so far: %d)",
                        cat["name"], len(cat_products), total_products,
                    )

                pbar.update(1)

    # The daily runner counts any CSV as success, so a partial catalogue
    # must not produce one.
    if failed:
        logger.error(
            "%d categor%s failed after one retry:",
            len(failed), "y" if len(failed) == 1 else "ies",
        )
        for name, reason in failed:
            logger.error("  %s: %s", name, reason)
        logger.error(
            "No CSV written and inflation step skipped; scraped rows kept in "
            "%s for --resume.", config.PARTIAL_FILE,
        )
        sys.exit(1)

    # 6. Final deduplication pass
    logger.info("Running final deduplication...")
    final_count = _dedup_csv()

    logger.info("Done! Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)

    # 7. Calculate Inflation (no-op if the inflation module is unavailable)
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
    """Construct and return the CLI argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with arguments: ``--list-categories``,
        ``--category``, ``--workers``, ``--delay``, ``--limit``,
        ``--resume``, ``-v``.
    """
    parser = argparse.ArgumentParser(
        prog="vivense-scraper",
        description=(
            "Scrape all product data from Vivense (vivense.com) and "
            "output to CSV."
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
        metavar="ID",
        default=None,
        help="Scrape only this category ID (e.g. 'oturma-odasi-mobilyalari').",
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
    """Parse CLI arguments and dispatch the appropriate action.

    Enables debug-level logging when ``-v``/``--verbose`` is passed,
    then either prints the curated category list
    (``--list-categories``) or delegates to :func:`run_scraper` for a
    full scrape.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_categories:
        cats = fetch_categories(session=_make_session())
        print(f"\n{'ID':<40} {'Name'}")
        print("-" * 70)
        for cat in cats:
            print(f"{cat['id']:<40} {cat['name']}")
        print(f"\nTotal: {len(cats)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
