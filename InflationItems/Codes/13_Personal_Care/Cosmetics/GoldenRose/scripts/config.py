"""Configuration for the Golden Rose scraper."""

from __future__ import annotations

import datetime as _dt
import os as _os
from pathlib import Path as _Path

BASE_URL = "https://shop.goldenrose.com.tr"
HOME_URL = f"{BASE_URL}/"

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

REQUEST_DELAY = 0.35
MAX_RETRIES = 3
RETRY_BACKOFF = 2

PROMOTIONAL_CATEGORY_NAMES = {"Yeni Ürünler", "Kampanyalar"}

TOP_LEVEL_PRIORITY = {
    "Yüz": 10,
    "Göz": 20,
    "Dudak": 30,
    "Tırnak": 40,
    "Cilt Bakımı": 50,
    "Aksesuar": 60,
    "Parfüm": 70,
    "Emily": 80,
    "Mini Ürünler": 90,
    "Setler": 100,
    "Koleksiyonlar": 110,
    "Yeni Ürünler": 120,
    "Kampanyalar": 130,
}

CSV_FIELDNAMES = [
    "product_name",
    "price",
    "Product Original Cost",
    "Discount Amount",
    "Discount Rate",
    "Currency",
    "Product ID",
    "SKU",
    "Brand",
    "Stock Quantity",
    "In Stock",
    "Top Category",
    "Category Path",
    "Leaf Category",
    "Full Category",
    "Model",
    "Variant 1",
    "Variant 2",
    "Subproduct ID",
    "Subproduct Code",
    "Category ID",
    "Source Category",
    "Source Category URL",
    "Product URL",
    "Image URL",
]

_SCRIPTS_DIR = _Path(__file__).resolve().parent
_SCRAPER_DIR = _SCRIPTS_DIR.parent
_PROJECT_ROOT = next((p for p in _SCRAPER_DIR.parents if (p / ".git").exists()), _SCRAPER_DIR.parents[4])

OUTPUT_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "13_Personal_Care" / "Cosmetics" / "GoldenRose"
CHECKPOINT_DIR = _SCRAPER_DIR / "checkpoints"

_DATE_OVERRIDE = _os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
if _DATE_OVERRIDE:
    _TODAY = _dt.date.fromisoformat(_DATE_OVERRIDE).strftime("%Y-%m-%d")
else:
    _TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = OUTPUT_DIR / f"goldenrose_{_TODAY}.csv"
CHECKPOINT_FILE = CHECKPOINT_DIR / f"goldenrose_checkpoint_{_TODAY}.json"
