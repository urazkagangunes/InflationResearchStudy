"""
Migros Scraper Configuration Module
==================================

This module serves as the centralized configuration repository for the Migros
product scraping system, providing all constants, settings, and path management
functionality.

Configuration Sections
----------------------
Base URLs and Endpoints
    Root domain and API endpoint definitions for all scraper operations

HTTP Request Configuration
    Headers, authentication parameters, and request settings required
    for successful API communication

Scraping Parameters
    Performance tuning parameters including delays, retries, concurrency,
    and rate limiting settings

Path Management
    Computed file paths for data exports, checkpoints, and session storage
    relative to the configuration file location

API Configuration
-----------------
BASE_URL: str
    Root domain for Migros e-commerce platform

SEARCH_ENDPOINT: str
    REST API endpoint for product search functionality

Required Headers
---------------
Custom headers are mandatory for Migros API access:
- X-Device-PWA: Required for API authentication
- X-FORWARDED-REST: Required for REST endpoint access
- Standard browser headers for compatibility

Performance Parameters
---------------------
REQUEST_DELAY: float (default: 0.5 seconds)
    Base delay between paginated API requests with random jitter applied

MAX_RETRIES: int (default: 3)
    Maximum retry attempts for failed HTTP requests before skipping

RETRY_BACKOFF: float (default: 2.0 seconds)
    Seed value for exponential backoff calculation (actual wait = seed × attempt)

DEFAULT_SORT: str (default: "onerilenler")
    Product sorting parameter for API requests

DEFAULT_WORKERS: int (default: 3)
    Thread pool size for parallel category processing

JITTER_RANGE: tuple (default: (0.5, 1.5))
    Random multiplier range applied to base delay for request distribution

Path Resolution
--------------
All paths are computed relative to this configuration file to ensure
consistent operation regardless of execution directory:

OUTPUT_DIR: str
    Target directory for CSV and JSON data exports

CHECKPOINT_DIR: str
    Storage location for daily session checkpoint files

Daily File Naming
----------------
Files use YYYY-MM-DD format for daily organization:
- CSV Export: migros_YYYY-MM-DD.csv
- JSON Export: migros_YYYY-MM-DD.json
- Checkpoint: migros_checkpoint_YYYY-MM-DD.json

Import Usage
-------------
Import with 'import config' from any sibling script. All constants are
available as config.CONSTANT_NAME for easy reference throughout the scraper.
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.migros.com.tr"

# REST product search API endpoint
PRODUCT_SEARCH_URL = f"{BASE_URL}/rest/products/search"

# Category sitemap (lists all category URLs)
CATEGORY_SITEMAP_URL = f"{BASE_URL}/hermes/api/sitemaps/sitemap-categories-1.xml"

# ── Request Headers ──────────────────────────────────────────────────────────
# These headers are required to avoid 403 Forbidden responses from the API.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "X-Device-PWA": "true",
    "X-FORWARDED-REST": "true",
    "X-PWA": "true",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests to avoid rate limiting
REQUEST_DELAY = 0.5

# Maximum retries on a failed request before skipping
MAX_RETRIES = 3

# Retry backoff in seconds (doubles each retry)
RETRY_BACKOFF = 2

# Default sort order (onerilenler = recommended)
DEFAULT_SORT = "onerilenler"

# Number of parallel category workers
DEFAULT_WORKERS = 3

# Jitter multiplier range applied to REQUEST_DELAY (uniform random between these)
JITTER_MIN = 0.5
JITTER_MAX = 1.5

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR    = _Path(__file__).resolve().parent          # …/InflationItems/Codes/Markets/Migros/scripts
_MIGROS_DIR     = _SCRIPTS_DIR.parent                       # …/InflationItems/Codes/Markets/Migros
_PROJECT_ROOT   = _MIGROS_DIR.parent.parent.parent.parent   # …/InflationResearchStudy

# Base output directory
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "Markets" / "Migros")

# CSV / JSON output  →  InflationItems/Datas/Markets/Migros/
OUTPUT_DIR      = str(_Path(BASE_OUTPUT_DIR))
INFLATION_DIR   = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

# Checkpoint files   →  InflationItems/Codes/Markets/Migros/checkpoints/
CHECKPOINT_DIR  = str(_MIGROS_DIR / "checkpoints")

# Files are named with today's date so each daily run produces its own set.
# Re-running on the same day with --resume picks up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)     / f"migros_{_TODAY}.csv")
JSON_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"migros_{_TODAY}.json")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR) / f"migros_checkpoint_{_TODAY}.json")

