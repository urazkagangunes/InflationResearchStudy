"""
main.py - Erzurum / Erzincan / Bayburt Rent Scraper (CLI entry point)
=====================================================================

Uses SeleniumBase in UC (undetected) mode for Apple Silicon compatibility.
SeleniumBase automatically fetches the correct ARM64 chromedriver binary.

Usage:
  python main.py                  # Full fresh scrape (all 3 cities)
  python main.py --resume         # Resume an interrupted run
  python main.py --city erzurum   # Scrape only one city
  python main.py -v               # Verbose debug output
"""

import argparse
import json
import logging
import os
import sys
import time
import random
import threading
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed

from seleniumbase import SB

import config
from scraper import scrape_range, save_incremental

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


_checkpoint_lock = threading.Lock()
_total_lock      = threading.Lock()

def _load_checkpoint() -> dict:
    cp_file = config.get_checkpoint_file()
    if os.path.exists(cp_file):
        with open(cp_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ranges": [], "done_cities": []}


def _save_checkpoint(data: dict) -> None:
    with _checkpoint_lock:
        os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
        with open(config.get_checkpoint_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# -- Main run --------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    checkpoint = _load_checkpoint() if args.resume else {"done_ranges": [], "done_cities": []}

    done_ranges: set[tuple[str, int, int]] = {
        (r[0], r[1], r[2]) for r in checkpoint.get("done_ranges", [])
    }
    done_cities: set[str] = set(checkpoint.get("done_cities", []))

    # Filter cities if --city flag is used
    cities_to_scrape = config.CITIES
    if args.city:
        target = args.city.lower()
        cities_to_scrape = [c for c in config.CITIES if c["url_slug"] == target]
        if not cities_to_scrape:
            valid = ", ".join(c["url_slug"] for c in config.CITIES)
            logger.error("City '%s' not found. Valid options: %s", args.city, valid)
            sys.exit(1)

    # On a fresh run, clear today's CSVs
    if not args.resume:
        for city_cfg in cities_to_scrape:
            csv_path = config.get_city_csv_path(city_cfg["name"])
            if os.path.exists(csv_path):
                os.remove(csv_path)
                logger.info("Cleared old CSV: %s", csv_path)
        _save_checkpoint({"done_ranges": [], "done_cities": []})
        done_ranges = set()
        done_cities = set()

    # -- Checkpoint callbacks ----------------------------------------------
    def mark_range_done(slug: str, min_p: int, max_p: int) -> None:
        done_ranges.add((slug, min_p, max_p))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        _save_checkpoint(checkpoint)

    def mark_city_done(slug: str) -> None:
        done_cities.add(slug)
        checkpoint["done_cities"] = list(done_cities)
        _save_checkpoint(checkpoint)

    logger.info(
        "Starting adaptive scrape for %d city/cities (%d ranges already completed)...",
        len(cities_to_scrape), len(done_ranges),
    )

    logger.info(
        "Starting stable serial scrape for %d city/cities (%d ranges already completed)...",
        len(cities_to_scrape), len(done_ranges),
    )

    grand_total = 0
    # Single SB instance for all cities - use base profile for stability
    with SB(
        uc=True,
        page_load_strategy="eager",
        user_data_dir=config.SELENIUM_PROFILE_DIR,
    ) as sb:
        for city_idx, city_cfg in enumerate(cities_to_scrape, 1):
            city_name = city_cfg["name"]
            city_slug = city_cfg["url_slug"]
            seed_ranges = city_cfg["seed_ranges"]

            if city_slug in done_cities and args.resume:
                logger.info("\u21a9  City '%s' already completed. Skipping.", city_name)
                continue

            logger.info(f"[PROGRESS] [{city_idx}/{len(cities_to_scrape)}] {city_name} | starting...")

            city_total = 0
            city_save_fn = partial(save_incremental, city_name)
            
            try:
                for seed_min, seed_max in seed_ranges:
                    saved = scrape_range(
                        sb=sb,
                        city_url_slug=city_slug,
                        min_price=seed_min,
                        max_price=seed_max,
                        done_ranges=done_ranges,
                        save_fn=city_save_fn,
                        save_checkpoint_fn=mark_range_done,
                        indent=0,
                    )
                    city_total += saved

                    delay = max(config.BETWEEN_BRACKET_DELAY_FLOOR, random.normalvariate(config.BETWEEN_BRACKET_DELAY_MEAN, config.BETWEEN_BRACKET_DELAY_STDEV))
                    time.sleep(delay)

                mark_city_done(city_slug)
                grand_total += city_total
                logger.info(f"Finished {city_name}: {city_total} items.")
                logger.info(f"[ITEMS] {grand_total} items collected so far")

                # Delay between cities
                if city_cfg != cities_to_scrape[-1]:
                    delay = max(config.BETWEEN_CITY_DELAY_FLOOR, random.normalvariate(config.BETWEEN_CITY_DELAY_MEAN, config.BETWEEN_CITY_DELAY_STDEV))
                    logger.info("   Waiting %.1fs before next city...", delay)
                    time.sleep(delay)

            except Exception as exc:
                logger.error(f"City {city_name} failed with error: {exc}")

    logger.info("\n[DONE] %d items saved across all cities", grand_total)

    logger.info("\n[DONE] %d items saved across all cities", grand_total)


# -- CLI -------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erzurum-erzincan-bayburt-scraper",
        description="Scrape rental listings for Erzurum, Erzincan, Bayburt from sahibinden.com",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.")
    parser.add_argument("--city", type=str, default=None, help="Scrape only one city (erzurum/erzincan/bayburt).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    run(args)


if __name__ == "__main__":
    main()
