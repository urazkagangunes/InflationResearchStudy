"""
Samsung Türkiye Scraper Configuration Module
============================================

Central configuration for the Samsung Türkiye (samsung.com/tr) product
scraping system.  Samsung's consumer site is powered by AEM + Hybris; the
Product Finder v2 (``pfv2``) widget populates each category page by
calling a public JSON endpoint on ``searchapi.samsung.com``.  We talk to
that endpoint directly instead of parsing HTML.

Sections
--------
API endpoint, default HTTP headers, performance parameters
(delays, retries, workers, jitter) and path resolution for the daily
CSV / checkpoint files.

API
---
- Endpoint: ``https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris``
- Method:   GET
- Response: JSON with ``response.resultData.productList[...]``
            Each family contains ``modelList[...]`` entries (real SKUs).

Key query parameters
~~~~~~~~~~~~~~~~~~~~
- ``type``         – 8-digit category type code (e.g. ``01010000`` for
                     smartphones).  Values are extracted from the
                     ``pfCategoryTypeCode`` hidden input on each "all-*"
                     category page.
- ``siteCode``     – Country code (``tr``).
- ``start``/``num``– 1-indexed pagination; tested-max ``num=500`` per
                     request.  Requests with ``num>=1000`` return
                     ``resultData: null``.
- ``sort``         – ``newest`` / ``recommended`` / ``priceascending`` /
                     ``pricedecending``.
- ``onlyFilterInfoYN`` – ``N`` to get products back (``Y`` returns only
                     the filter tree).

Paths
-----
All paths are resolved relative to this config file so the scraper works
regardless of the working directory from which ``main.py`` is invoked.

- CSV output   → ``InflationItems/Datas/TechnologicalProducts/Samsung/samsung_YYYY-MM-DD.csv``
- Checkpoints  → ``InflationItems/Codes/TechnologicalProducts/Samsung/checkpoints/samsung_checkpoint_YYYY-MM-DD.json``
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.samsung.com"

# Public Product Finder v2 (pfv2) endpoint used by every /tr/<cat>/all-*/ page.
# ``newhybris`` is the variant selected when ``shopIntegrationFlag`` is
# ``Hybris-new`` (the current setting for Samsung Türkiye).
PRODUCT_FINDER_URL = (
    "https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris"
)

# Site code sent with every request.  Samsung routes pricing, stock and
# language off this value.
SITE_CODE = "tr"

# ── Request Headers ──────────────────────────────────────────────────────────
# Realistic browser headers.  The pfv2 endpoint does not require any auth /
# token but it does look at ``Accept`` and the ``Referer`` of a real
# Samsung Türkiye page.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": f"{BASE_URL}/tr/",
    "Origin": BASE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests (jitter applied).
REQUEST_DELAY = 0.5

# Maximum retries on a failed request before skipping.
MAX_RETRIES = 4

# Retry backoff seed in seconds (actual wait = seed × attempt).
RETRY_BACKOFF = 2

# Number of parallel category workers.
DEFAULT_WORKERS = 3

# Jitter multiplier range applied to REQUEST_DELAY (uniform random).
JITTER_MIN = 0.5
JITTER_MAX = 1.5

# Page size for the pfv2 endpoint.  Tested-safe upper bound is ~500 per
# request (``num>=1000`` returns ``resultData: null``).  200 keeps the
# payload reasonable while still finishing every known category in <=2
# requests as of 2026-04.
PAGE_SIZE = 200

# Default sort order.  ``newest`` is what Samsung's own "all" pages use
# when no user preference is set.
DEFAULT_SORT = "newest"

# ── Category Taxonomy ────────────────────────────────────────────────────────
# Curated list of Samsung Türkiye top-level category pages.  Each entry
# maps 1-to-1 to an "all-*" landing page whose ``pfCategoryTypeCode``
# hidden input gives the 8-digit type code consumed by the pfv2
# endpoint.  Codes were extracted live from each page on 2026-05.
#
# ``tuik_group`` indicates the TUIK CPI main group we classify the
# category under (used by the downstream inflation calculator).
#
# We deliberately restrict scraping to the "all" landing pages because
# every sub-category page is a strict subset of its parent — scraping
# both would only duplicate SKUs.
TOP_LEVEL_CATEGORIES = [
    # ── Mobile (01xx) ────────────────────────────────────────────────
    {"id": "smartphones",         "type": "01010000",
     "name": "Smartphones",
     "landing_path": "/tr/smartphones/all-smartphones/"},
    {"id": "tablets",             "type": "01020000",
     "name": "Tablets",
     "landing_path": "/tr/tablets/all-tablets/"},
    {"id": "watches",             "type": "01030000",
     "name": "Watches",
     "landing_path": "/tr/watches/all-watches/"},
    {"id": "audio-sound",         "type": "01040000",
     "name": "Audio Sound",
     "landing_path": "/tr/audio-sound/all-audio-sound/"},
    {"id": "mobile-accessories",  "type": "01050000",
     "name": "Mobile Accessories",
     "landing_path": "/tr/mobile-accessories/all-mobile-accessories/"},
    {"id": "rings",               "type": "01090000",
     "name": "Rings",
     "landing_path": "/tr/rings/all-rings/"},

    # ── Audio / Video (04xx, 05xx) ───────────────────────────────────
    {"id": "tvs",                 "type": "04010000",
     "name": "TVs",
     "landing_path": "/tr/tvs/all-tvs/"},
    {"id": "tv-accessories",      "type": "04030000",
     "name": "TV Accessories",
     "landing_path": "/tr/tv-accessories/all-tv-accessories/"},
    {"id": "projectors",          "type": "04050000",
     "name": "Projectors",
     "landing_path": "/tr/projectors/all-projectors/"},
    {"id": "audio-devices",       "type": "05010000",
     "name": "Audio Devices",
     "landing_path": "/tr/audio-devices/all-audio-devices/"},

    # ── Monitors / IT (07xx, 09xx) ───────────────────────────────────
    {"id": "monitors",            "type": "07010000",
     "name": "Monitors",
     "landing_path": "/tr/monitors/all-monitors/"},
    {"id": "memory-storage",      "type": "09010000",
     "name": "Memory & Storage",
     "landing_path": "/tr/memory-storage/all-memory-storage/"},

    # ── Home Appliances (08xx) ───────────────────────────────────────
    {"id": "washers-and-dryers",  "type": "08010000",
     "name": "Washers & Dryers",
     "landing_path": "/tr/washers-and-dryers/all-washers-and-dryers/"},
    {"id": "refrigerators",       "type": "08030000",
     "name": "Refrigerators",
     "landing_path": "/tr/refrigerators/all-refrigerators/"},
    {"id": "air-care",            "type": "08040000",
     "name": "Air Purifier",
     "landing_path": "/tr/air-care/air-purifier/"},
    {"id": "air-conditioners",    "type": "08050000",
     "name": "Air Conditioners",
     "landing_path": "/tr/air-conditioners/all-air-conditioners/"},
    {"id": "vacuum-cleaners",     "type": "08070000",
     "name": "Vacuum Cleaners",
     "landing_path": "/tr/vacuum-cleaners/all-vacuum-cleaners/"},
    {"id": "cooking-appliances",  "type": "08080000",
     "name": "Cooking Appliances",
     "landing_path": "/tr/cooking-appliances/ovens/"},
    {"id": "dishwashers",         "type": "08090000",
     "name": "Dishwashers",
     "landing_path": "/tr/dishwashers/all-dishwashers/"},
    {"id": "microwave-ovens",     "type": "08110000",
     "name": "Microwave Ovens",
     "landing_path": "/tr/microwave-ovens/all-microwave-ovens/"},
]

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR  = _Path(__file__).resolve().parent                    # …/TechnologicalProducts/Samsung/scripts
_SAMSUNG_DIR  = _SCRIPTS_DIR.parent                                  # …/TechnologicalProducts/Samsung
_PROJECT_ROOT = _SAMSUNG_DIR.parent.parent.parent.parent              # …/InflationResearchStudy

# CSV output → InflationItems/Datas/TechnologicalProducts/Samsung/
BASE_OUTPUT_DIR = str(
    _PROJECT_ROOT / "InflationItems" / "Datas" / "TechnologicalProducts" / "Samsung"
)
OUTPUT_DIR = BASE_OUTPUT_DIR

# Checkpoints → InflationItems/Codes/TechnologicalProducts/Samsung/checkpoints/
CHECKPOINT_DIR = str(_SAMSUNG_DIR / "checkpoints")

# Daily-dated file names so each run produces its own set and --resume picks
# up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"samsung_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"samsung_checkpoint_{_TODAY}.json")
