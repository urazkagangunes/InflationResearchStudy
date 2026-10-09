"""
Rossmann Scraper Configuration Module
=====================================

Central configuration for the Rossmann Türkiye (rossmann.com.tr) product
scraping system. Rossmann runs on Magento 2 and exposes a public GraphQL
endpoint at ``/graphql`` — the scraper talks to that endpoint directly
instead of parsing HTML.

Sections
--------
GraphQL endpoint, default HTTP headers, performance parameters
(delays, retries, workers, jitter) and path resolution for the daily
CSV / checkpoint files.

Paths
-----
All paths are resolved relative to this config file so the scraper works
regardless of the working directory from which ``main.py`` is invoked.

- CSV output   → ``InflationItems/Datas/Cosmetics/Rossmann/rossmann_YYYY-MM-DD.csv``
- Checkpoints  → ``InflationItems/Codes/Cosmetics/Rossmann/checkpoints/rossmann_checkpoint_YYYY-MM-DD.json``
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.rossmann.com.tr"

# Magento 2 GraphQL endpoint (public; no auth required for read queries)
GRAPHQL_URL = f"{BASE_URL}/graphql"

# ── Request Headers ──────────────────────────────────────────────────────────
# Realistic browser headers. Magento's GraphQL endpoint accepts both GET and
# POST; we use POST with a JSON body to keep queries readable in logs.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Store": "default",
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated GraphQL requests (jitter applied)
REQUEST_DELAY = 0.5

# Maximum retries on a failed request before skipping
MAX_RETRIES = 3

# Retry backoff seed in seconds (actual wait = seed × attempt)
RETRY_BACKOFF = 2

# Number of parallel category workers
DEFAULT_WORKERS = 3

# Jitter multiplier range applied to REQUEST_DELAY (uniform random)
JITTER_MIN = 0.5
JITTER_MAX = 1.5

# Page size used for product queries. The Magento GraphQL endpoint accepts up
# to 500 per call, which keeps the total request count low.
PAGE_SIZE = 200

# Top-level navigation categories (level 2 children of the Rossmann root
# category). Scraping only these covers the full product catalog while
# avoiding the many small campaign sub-categories that duplicate products.
#
# IDs come from a `{ categoryList { children { id name url_key } } }` probe.
TOP_LEVEL_CATEGORIES = [
    {"id": "3",  "name": "Makyaj",        "url_key": "makyaj"},
    {"id": "49", "name": "Cilt Bakımı",   "url_key": "cilt-bakimi"},
    {"id": "4",  "name": "Kişisel Bakım", "url_key": "kisisel-bakim"},
    {"id": "5",  "name": "Anne & Bebek",  "url_key": "anne-bebek"},
    {"id": "6",  "name": "Sağlık & Gıda", "url_key": "saglik-gida"},
    {"id": "7",  "name": "Temizlik",      "url_key": "temizlik"},
    {"id": "8",  "name": "Ev & Yaşam",    "url_key": "ev-yasam"},
]

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR   = _Path(__file__).resolve().parent          # …/Cosmetics/Rossmann/scripts
_ROSSMANN_DIR  = _SCRIPTS_DIR.parent                       # …/Cosmetics/Rossmann
_PROJECT_ROOT  = _ROSSMANN_DIR.parent.parent.parent.parent # …/InflationResearchStudy

# CSV output → InflationItems/Datas/Cosmetics/Rossmann/
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "Cosmetics" / "Rossmann")
OUTPUT_DIR      = BASE_OUTPUT_DIR

# Checkpoints → InflationItems/Codes/Cosmetics/Rossmann/checkpoints/
CHECKPOINT_DIR  = str(_ROSSMANN_DIR / "checkpoints")

# Daily-dated file names so each run produces its own set and --resume picks
# up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"rossmann_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"rossmann_checkpoint_{_TODAY}.json")
