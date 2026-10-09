"""
Bauhaus Türkiye Product Scraper - Main Entry Point and Orchestration Layer
==========================================================================

This module serves as the primary interface for the Bauhaus product scraping system,
providing comprehensive CLI functionality and coordinating all scraping operations
through a high-performance, multi-threaded architecture.

Core Responsibilities
----------------------
- Command-line argument parsing and validation
- HTML navigation-based category discovery coordination
- Parallel product extraction using ThreadPoolExecutor
- Incremental data persistence and batched checkpoint management
- Cross-category product deduplication
- CSV data export with standardized formatting

Execution Pipeline
-----------------
1. Category Discovery: Parses homepage HTML navigation to extract complete taxonomy
2. Checkpoint Management: Loads previous session state when resume mode is enabled
3. Parallel Processing: Dispatches categories to worker threads with optimized sessions
4. Batched Persistence: Saves data and checkpoints every 5 categories for performance
5. Data Deduplication: Removes duplicate products across category boundaries
6. Export Generation: Creates CSV output file with UTF-8 BOM formatting

Performance Architecture
------------------------
- lxml parser for 3-5x faster HTML processing compared to default parsers
- CSS selectors for efficient DOM traversal and element extraction
- HTTP session reuse across categories for connection pooling
- Batched I/O operations to reduce filesystem overhead
- Adaptive rate limiting to prevent detection while optimizing speed

Threading Model
---------------
- ThreadPoolExecutor manages concurrent category processing
- Each worker maintains an independent requests.Session object
- Configurable worker count (default: 2) for performance tuning
- Batched checkpoint writing reduces I/O contention

Optimization Features
---------------------
The scraper implements six key performance optimizations:
1. **lxml Parser**: High-performance XML/HTML processing
2. **CSS Selectors**: Efficient DOM element targeting
3. **Session Reuse**: Persistent HTTP connections
4. **Batched Checkpoints**: Reduced I/O overhead (every 5 categories)
5. **String Optimization**: Efficient price cleaning operations
6. **Adaptive Rate Limiting**: Intelligent request timing

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
python main.py --category bauhaus-oto --limit 2

# Full catalog extraction with default settings
python main.py

# Parallel processing with custom worker count
python main.py --workers 4

# Rate-limited scraping with custom delay
python main.py --delay 3.0

# Resume interrupted session
python main.py --resume

# Enable debug logging
python main.py --category bauhaus-oto -v
```
"""

import sys
import os
import csv
import json
import logging
import argparse
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import config, category_fetcher, product_fetcher

# Add the location of inflation.py to sys.path
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", "..", "..", "Inflations", "Codes", "ConstructionSuppliesMarkets", "Bauhaus"
)
sys.path.append(os.path.abspath(_inflation_dir))
try:
    import inflation
except ImportError as e:
    inflation = None
    print(f"Warning: Could not import inflation module: {e}")

logger = logging.getLogger(__name__)

def parse_args():
    """
    Parses command line arguments for the scraper.

    Returns:
        argparse.Namespace: The parsed arguments including output format,
                            workers count, resume flags, etc.
    """
    p = argparse.ArgumentParser(description="Bauhaus Türkiye Product Scraper")
    p.add_argument("--list-categories", action="store_true", help="Print all categories and exit")
    p.add_argument("--category", type=str, help="Scrape only one category ID")
    p.add_argument("--workers", type=int, default=config.DEFAULT_WORKERS, help="Parallel workers")
    p.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="Base delay")
    p.add_argument("--limit", type=int, default=0, help="Max pages per category")
    p.add_argument("--resume", action="store_true", help="Resume interrupted run")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p.parse_args()

def save_csv(products, out_path):
    """
    Writes a list of product dictionaries into a UTF-8 encoded CSV file.

    Args:
        products (list[dict]): Normalised list of products to save.
        out_path (str): The absolute path for the target .csv file.
    """
    if not products:
        return
    fieldnames = ["id", "sku", "name", "brand", "category", "regular_price", "shown_price", "discount_rate", "unit", "status"]
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    logger.info(f"✅ Saved {len(products)} products")

def load_checkpoint(cp_path):
    """
    Loads saved category IDs from a previous run to enable resume functionality.

    Args:
        cp_path (str): Path to the checkpoint JSON file.

    Returns:
        set: A set containing the string IDs of categories already scraped.
    """
    if os.path.exists(cp_path):
        with open(cp_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_checkpoint(cp_path, completed):
    """
    Writes the current set of completed category IDs to the checkpoint file.

    Args:
        cp_path (str): Path to the checkpoint JSON file.
        completed (set): Set of completed string IDs.
    """
    # Atomic write: tmp then rename, so an interrupted save can't corrupt the
    # checkpoint file (important now that we save after every category).
    tmp = cp_path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(list(completed), f)
    os.replace(tmp, cp_path)

def load_products_checkpoint(pp_path):
    """
    Loads previously scraped products from a per-category checkpoint file.

    Args:
        pp_path (str): Path to the products JSON file.

    Returns:
        list[dict]: Products accumulated by previous (completed) categories.
                    Empty list if no file is found.
    """
    if os.path.exists(pp_path):
        try:
            with open(pp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"⚠  Could not load products checkpoint {pp_path}: {e}")
    return []

def save_products_checkpoint(pp_path, products):
    """
    Persists the running list of scraped products so that a --resume after an
    interrupted run can recover the data instead of re-scraping every category
    that the previous run had already finished.

    Args:
        pp_path (str): Path to the products JSON file.
        products (list[dict]): All products collected so far this session.
    """
    tmp = pp_path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False)
    os.replace(tmp, pp_path)

def scrape_category_worker(cat, limit, session, cp_path, completed_ids, resume_state=None):
    """
    Worker function to scrape a single category. Writes its ID to the checkpoint when done.

    Args:
        cat (dict): The category directory to fetch.
        limit (int): The page limit (for testing).
        session (requests.Session): Reusable HTTP session for this worker.
        cp_path (str): The checkpoint file to update.
        completed_ids (set): The shared set of completed IDs.
        resume_state (dict, optional): State from a previous blocked attempt for
            this category, containing 'start_page', 'seed_products',
            'seed_last_skus', and 'seed_delay'. When provided, the scraper
            resumes mid-pagination instead of restarting at page 1.

    Returns:
        list[dict]: Extracted product data for the category.
    """
    kwargs = {}
    if resume_state:
        kwargs = {
            "start_page": resume_state.get("start_page", 1),
            "seed_products": resume_state.get("seed_products"),
            "seed_last_skus": resume_state.get("seed_last_skus"),
            "seed_delay": resume_state.get("seed_delay"),
        }
    products = product_fetcher.fetch_products_for_category(cat, session, limit, **kwargs)
    completed_ids.add(cat["id"])
    return products

def main():
    """
    Main orchestrator logic. Loops together all pieces: Category discovery ->
    Parallel Fetching -> Checkpointing -> Deduplication -> File saving -> Inflation.
    """
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config.REQUEST_DELAY = args.delay

    cats = category_fetcher.fetch_categories()
    if not cats:
        logger.error("✗  Failed to load categories.")
        sys.exit(1)

    if args.list_categories:
        for c in cats:
            print(f"{c['id']} - {c['name']}")
        sys.exit(0)

    # Filter to main categories only to avoid redundant product fetching.
    # Subcategories are subsets of main categories, so scraping only the main
    # ones eliminates ~70k duplicate product fetches (110k -> ~37k unique).
    MAIN_CATEGORIES = [
        "bauhaus-bahce",
        "bauhaus-banyo",
        "bauhaus-mutfak",
        "bauhaus-mobilya",
        "bauhaus-hirdavat",
        "bauhaus-aydinlatma-ve-elektro",
        "bauhaus-makine-ve-el-aletleri",
        "bauhaus-dekorasyon-ve-ev-gerecleri",
        "bauhaus-isitma-ve-sogutma",
        "bauhaus-parke-ve-kapilar",
        "bauhaus-boya-ve-insaat",
        "bauhaus-oto",
    ]

    cats = [c for c in cats if c["id"] in MAIN_CATEGORIES]
    logger.info("✓  Filtered to %d main categories: %s",
                len(cats), ", ".join(c["id"] for c in cats))

    # Filter to a single category if requested
    if args.category:
        cats = [c for c in cats if c["id"] == args.category]
        if not cats:
            logger.error(f"✗  Category '{args.category}' not found.")
            sys.exit(1)

    date_str = datetime.now().strftime("%Y-%m-%d")
    checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"bauhaus_checkpoint_{date_str}.json")
    products_checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"bauhaus_products_{date_str}.json")

    completed_ids = set()
    all_products = []
    if args.resume:
        completed_ids = load_checkpoint(checkpoint_file)
        all_products = load_products_checkpoint(products_checkpoint_file)
        logger.info(
            f"↩  Resuming: {len(completed_ids)} categories already completed, "
            f"{len(all_products)} products restored from checkpoint."
        )

    cats_to_scrape = [c for c in cats if c["id"] not in completed_ids]
    cat_count = len(cats_to_scrape)
    logger.info(f"▶  Scraping {cat_count} categor{'y' if cat_count == 1 else 'ies'} with {args.workers} worker(s)…")

    # Checkpointing strategy: after every completed category we persist both
    # (a) the set of completed category IDs and (b) the running products list.
    # This way an interrupted run (Ctrl+C, crash, transient infra issue) can be
    # resumed via --resume without re-scraping anything that already finished
    # *and* without losing the products that were collected.

    completed_count = 0
    count_lock = threading.Lock()
    checkpoint_interval = 1  # Save checkpoint after every completed category
    
    import time
    start_time = time.time()

    # Retry loop: when 403 blocks occur, cooldown and retry. We now keep
    # per-category resume state (last page reached, seen SKUs, delay) so each
    # retry continues mid-pagination instead of restarting at page 1 and
    # repeatedly re-fetching the same prefix that the server just blocked on.
    retry_round = 0
    pending_cats = list(cats_to_scrape)
    # Map cat_id -> {start_page, seed_products, seed_last_skus, seed_delay}
    resume_by_cat = {}

    while pending_cats and retry_round <= config.MAX_403_RETRIES:
        # Create fresh sessions each round (important after a 403 block)
        worker_sessions = [product_fetcher.create_session() for _ in range(args.workers)]

        if retry_round > 0:
            cooldown = config.COOLDOWN_BASE * retry_round
            logger.info(f"⏳ 403 cooldown: waiting {cooldown}s before retry round {retry_round}/{config.MAX_403_RETRIES}…")
            time.sleep(cooldown)
            logger.info(f"🔄 Retrying {len(pending_cats)} blocked categories with fresh sessions "
                        f"(resuming from last reached page)…")

        blocked_cats = []

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_cat = {}
            for i, cat in enumerate(pending_cats):
                worker_session = worker_sessions[i % args.workers]
                resume_state = resume_by_cat.get(cat["id"])
                future = executor.submit(
                    scrape_category_worker,
                    cat, args.limit, worker_session,
                    checkpoint_file, completed_ids,
                    resume_state,
                )
                future_to_cat[future] = cat

            for future in as_completed(future_to_cat):
                cat = future_to_cat[future]
                try:
                    cat_prods = future.result()
                    all_products.extend(cat_prods)
                    # Clear any stale resume state now that the category finished
                    resume_by_cat.pop(cat["id"], None)

                    with count_lock:
                        completed_count += 1
                        logger.info(f"✓  Category '{cat['name']}': +{len(cat_prods)} products (total: {len(all_products)})")

                        if completed_count % checkpoint_interval == 0 or completed_count == cat_count:
                            save_checkpoint(checkpoint_file, completed_ids)
                            save_products_checkpoint(products_checkpoint_file, all_products)
                            logger.info(
                                f"💾 Checkpoint saved: {completed_count}/{cat_count} categories, "
                                f"{len(all_products)} products on disk"
                            )

                except product_fetcher.BauhausBlockedException as blocked:
                    partial = blocked.products
                    blocked_cats.append(cat)
                    # Remember where this category got to so the next round can
                    # resume instead of restarting at page 1. Bump the starting
                    # delay so retries are gentler on the server.
                    prev_delay = blocked.adaptive_delay if blocked.adaptive_delay is not None else config.REQUEST_DELAY
                    next_delay = min(max(prev_delay * 1.5, config.REQUEST_DELAY * 2.0), 10.0)
                    resume_by_cat[cat["id"]] = {
                        "start_page": max(1, blocked.last_page + 1),
                        "seed_products": list(partial),
                        "seed_last_skus": set(blocked.last_page_skus),
                        "seed_delay": next_delay,
                    }
                    logger.warning(
                        f"⚠  Category '{cat['name']}' blocked (403) at page "
                        f"{blocked.last_page + 1}. Saved {len(partial)} partial products. "
                        f"Will resume from page {blocked.last_page + 1} next round."
                    )

                except Exception as exc:
                    logger.error(f"✗  Category '{cat['id']}' failed: {exc}")

        save_checkpoint(checkpoint_file, completed_ids)
        save_products_checkpoint(products_checkpoint_file, all_products)

        if not blocked_cats:
            break

        retry_round += 1
        pending_cats = blocked_cats

    # After all retry rounds are exhausted, any category still in resume_by_cat
    # never finished. Flush its last-known partial products into the output so
    # we don't lose them (previous code extended all_products on every block,
    # which duplicated items across rounds; we defer the flush to here instead
    # and rely on final dedup as a safety net).
    for cat in pending_cats:
        state = resume_by_cat.get(cat["id"])
        if state and state.get("seed_products"):
            all_products.extend(state["seed_products"])
            logger.info(
                f"↪  Category '{cat['name']}' never fully completed; kept "
                f"{len(state['seed_products'])} partial products from last attempt."
            )

    if pending_cats and retry_round > config.MAX_403_RETRIES:
        logger.warning(f"⚠  {len(pending_cats)} categories still blocked after {config.MAX_403_RETRIES} retries: "
                       f"{[c['name'] for c in pending_cats]}")

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    logger.info("Scraping completed in %.1f seconds (%.1f min)", elapsed_time, elapsed_time / 60)
    
    # Deduplicate
    before_count = len(all_products)
    unique_products = list({p["id"]: p for p in all_products}.values())
    after_count = len(unique_products)
    
    if before_count > after_count:
        logger.info(f"Running final deduplication…")
        logger.info(f"Removed {before_count - after_count} duplicate records. Final count: {after_count}")
    
    # Save Outputs
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        
    base_name = f"bauhaus_{date_str}"
    csv_path = os.path.join(config.OUTPUT_DIR, f"{base_name}.csv")

    save_csv(unique_products, csv_path)
    logger.info("Done! ✓  Total unique products: %d", after_count)
    logger.info("Output → %s", csv_path)

    if inflation:
        logger.info("Calculating inflation metrics...")
        try:
            inflation.calculate_inflation()
        except Exception as e:
            logger.error(f"✗  Failed to calculate inflation: {e}")
    else:
        logger.warning("⚠  Skipping inflation calculation (module not imported).")

if __name__ == "__main__":
    main()
