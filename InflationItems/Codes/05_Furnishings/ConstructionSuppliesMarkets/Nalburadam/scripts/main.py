"""
main.py — Nalburadam Scraper Orchestrator
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

import config
import category_fetcher
import product_fetcher

logger = logging.getLogger(__name__)

def parse_args():
    p = argparse.ArgumentParser(description="Nalburadam Product Scraper")
    p.add_argument("--list-categories", action="store_true", help="Print all categories and exit")
    p.add_argument("--category", type=str, help="Scrape only one category ID")
    p.add_argument("--workers", type=int, default=config.DEFAULT_WORKERS, help="Parallel workers")
    p.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="Base delay")
    p.add_argument("--limit", type=int, default=0, help="Max pages per category")
    p.add_argument("--resume", action="store_true", help="Resume interrupted run")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p.parse_args()

def save_csv(products, out_path):
    if not products:
        return
    fieldnames = ["product_name", "price", "id", "sku", "brand", "category", "regular_price", "discount_rate", "unit", "status"]
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    logger.info(f"Saved {len(products)} products to {out_path}")

def load_checkpoint(cp_path):
    if os.path.exists(cp_path):
        with open(cp_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_checkpoint(cp_path, completed):
    with open(cp_path, 'w', encoding='utf-8') as f:
        json.dump(list(completed), f)

def scrape_category_worker(cat, limit, session, cp_path, completed_ids):
    products = product_fetcher.fetch_products_for_category(cat, session, limit)
    completed_ids.add(cat["id"])
    return products

def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config.REQUEST_DELAY = args.delay

    cats = category_fetcher.fetch_categories()
    if not cats:
        logger.error("Failed to load categories.")
        sys.exit(1)

    if args.list_categories:
        for c in cats:
            print(f"{c['id']} - {c['name']}")
        sys.exit(0)

    if args.category:
        cats = [c for c in cats if c["id"] == args.category]
        if not cats:
            logger.error(f"Category {args.category} not found.")
            sys.exit(1)

    override_date = os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
    if override_date:
        date_str = datetime.fromisoformat(override_date).strftime("%Y-%m-%d")
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"nalburadam_checkpoint_{date_str}.json")
    
    completed_ids = set()
    if args.resume:
        completed_ids = load_checkpoint(checkpoint_file)
        logger.info(f"Resuming with {len(completed_ids)} categories already completed.")

    all_products = []
    cats_to_scrape = [c for c in cats if c["id"] not in completed_ids]
    total_cats = len(cats)
    logger.info(f"Beginning scrape for {total_cats} categories using {args.workers} workers...")

    completed_count = 0
    count_lock = threading.Lock()
    checkpoint_interval = 5

    worker_sessions = [product_fetcher.create_session() for _ in range(args.workers)]

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_cat = {}
        for i, cat in enumerate(cats_to_scrape):
            worker_session = worker_sessions[i % args.workers]
            future = executor.submit(scrape_category_worker, cat, args.limit, worker_session, checkpoint_file, completed_ids)
            future_to_cat[future] = cat
            
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_prods = future.result()
                all_products.extend(cat_prods)
                
                with count_lock:
                    completed_count += 1
                    logger.info(f"[PROGRESS] [{completed_count}/{total_cats}] {cat['name']} | +{len(cat_prods)} items")
                    logger.info(f"[ITEMS] {len(all_products)} items collected so far")
                    
                    if completed_count % checkpoint_interval == 0 or completed_count == total_cats:
                        save_checkpoint(checkpoint_file, completed_ids)
                        logger.info(f"Checkpoint saved: {completed_count}/{total_cats} categories completed")
                    
            except Exception as exc:
                logger.error(f"Category {cat['id']} generated an exception: {exc}")
        
        save_checkpoint(checkpoint_file, completed_ids)

    unique_products = {p["id"]: p for p in all_products}.values()
    
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        
    base_name = f"nalburadam_{date_str}"
    csv_path = os.path.join(config.OUTPUT_DIR, f"{base_name}.csv")

    save_csv(unique_products, csv_path)
    logger.info(f"[DONE] {len(list(unique_products))} items saved to {csv_path}")

if __name__ == "__main__":
    main()
