"""Configuration for the Karaca scraper."""

from __future__ import annotations

import datetime as _dt
import os as _os
from pathlib import Path as _Path

BASE_URL = "https://www.karaca.com"
HOME_URL = f"{BASE_URL}/"
# Web navigation menu as JSON; the desktop mega menu is rendered from it.
MENU_URL = f"{BASE_URL}/api/frontend-service/v1/menus/categories"
PLP_LINK_TYPE = "karaca://plp/category"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": HOME_URL,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Pages are requested with a random pause between REQUEST_DELAY and 3x that value.
REQUEST_DELAY = 1.0
CATEGORY_WORKERS = 3
MAX_RETRIES = 4
RETRY_BACKOFF = 5

PROMOTIONAL_MAIN_CATEGORIES = {
    "Hediye",
    "Anneler Günü",
    "Çeyiz Seti",
    "Çok Satan",
    "İndirimli Ürünler",
    "Markalar",
    "Kampanyalar",
}

NON_LISTING_PATHS = {
    "/gift-card",
    "/marka",
}

MAIN_CATEGORY_PRIORITY = {
    "Sofra": 10,
    "Mutfak": 20,
    "Küçük Ev Aletleri": 30,
    "Ev ve Yaşam": 40,
    "Hobi Eğlence": 50,
    "Hediye": 60,
    "Anneler Günü": 70,
    "Çeyiz Seti": 80,
    "Çok Satan": 90,
    "İndirimli Ürünler": 95,
    "Markalar": 100,
    "Kampanyalar": 110,
}

# Food is far outside home goods; everything else the menu lists is kept.
EXCLUDED_TOP_CATEGORIES = {"Gıda"}

# The daily CSV; the partial snapshot keeps CSV_FIELDNAMES for --resume.
OUTPUT_FIELDNAMES = ["product_name", "price"]

CSV_FIELDNAMES = [
    "product_name",
    "price",
    "Product Original Cost",
    "Discount Amount",
    "Discount Rate",
    "Currency",
    "Product ID",
    "Stock Quantity",
    "In Stock",
    "Main Category",
    "Top Category",
    "Category ID",
    "Category Path",
    "Source Category",
    "Source Category URL",
    "Product URL",
    "Image URL",
    "Color",
    "Size",
]

_SCRIPTS_DIR = _Path(__file__).resolve().parent
_SCRAPER_DIR = _SCRIPTS_DIR.parent
_PROJECT_ROOT = next((p for p in _SCRAPER_DIR.parents if (p / ".git").exists()), _SCRAPER_DIR.parents[4])

OUTPUT_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Karaca"
CHECKPOINT_DIR = _SCRAPER_DIR / "checkpoints"

_DATE_OVERRIDE = _os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
if _DATE_OVERRIDE:
    _TODAY = _dt.date.fromisoformat(_DATE_OVERRIDE).strftime("%Y-%m-%d")
else:
    _TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = OUTPUT_DIR / f"karaca_{_TODAY}.csv"
CHECKPOINT_FILE = CHECKPOINT_DIR / f"karaca_checkpoint_{_TODAY}.json"
# Rows of an unfinished run; the dated CSV is written only when every category
# completed. Not ``.csv`` so the daily runner never picks it up.
PARTIAL_FILE = CHECKPOINT_DIR / f"karaca_partial_{_TODAY}.part"
