import argparse, json, logging, os, random, time
from config import *
from config import _TODAY
from scraper import setup_driver, scrape_range, save_incremental

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run(args):
    driver = None
    try:
        driver = setup_driver()
        for city in CITIES:
            out_dir = OUTPUT_BASE_DIR / city["folder"]
            out_dir.mkdir(parents=True, exist_ok=True)
            csv_path = out_dir / f"{city['folder']}_{_TODAY}.csv"
            cp_path = CHECKPOINT_DIR / f"cp_{city['folder']}.json"

            if not args.resume and csv_path.exists(): csv_path.unlink()
            
            cp_data = json.load(open(cp_path)) if args.resume and cp_path.exists() else {"done": []}
            done_ranges = {tuple(r) for r in cp_data["done"]}

            def mark_done(mi, ma):
                done_ranges.add((mi, ma))
                with open(cp_path, "w") as f: json.dump({"done": list(done_ranges)}, f)

            for s_min, s_max in SEED_RANGES:
                scrape_range(driver, s_min, s_max, done_ranges, save_incremental, mark_done, 0, city["url_name"], str(csv_path))
                time.sleep(random.uniform(BETWEEN_BRACKET_DELAY_MIN, BETWEEN_BRACKET_DELAY_MAX))
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    run(parser.parse_args())