"""
Configuration — Sarıyer Market scraper
"""

BASE_URL = "https://www.sariyermarket.com"

PRODUCT_LIST_URL = f"{BASE_URL}/Catalog/OBAjaxFilterProducts"
CATEGORY_API_URL = f"{BASE_URL}/OBComponents/GetHomePageCategories"

DEFAULT_HEADERS = {
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer":  BASE_URL + "/",
    "Origin":   BASE_URL,
}

REQUEST_DELAY  = 0.7
MAX_RETRIES    = 3
RETRY_BACKOFF  = 2
PAGE_SIZE      = 24
DEFAULT_SORT   = "default"

import datetime as _dt
from pathlib import Path as _Path

_SCRIPTS_DIR   = _Path(__file__).resolve().parent
_MARKET_DIR    = _SCRIPTS_DIR.parent
_PROJECT_ROOT  = _MARKET_DIR.parent.parent

OUTPUT_DIR     = str(_PROJECT_ROOT / "Datas" / "Markets" / "Sariyer")
CHECKPOINT_DIR = str(_SCRIPTS_DIR / "checkpoints")

_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)     / f"sariyermarket_{_TODAY}.csv")
JSON_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"sariyermarket_{_TODAY}.json")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR) / f"sariyermarket_checkpoint_{_TODAY}.json")
