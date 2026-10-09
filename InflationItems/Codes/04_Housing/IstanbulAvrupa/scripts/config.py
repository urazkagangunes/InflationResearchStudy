"""
Istanbul Avrupa Rent Scraper Configuration Module
===============================================

This module serves as the centralized configuration repository for the Istanbul
European side rental listing scraper, providing algorithm parameters, browser settings,
path management, and adaptive bracket splitting configurations.

Configuration Sections
----------------------
City Configuration
    Geographic targeting parameters for URLs and file organization

Adaptive Algorithm Settings
    Parameters controlling the intelligent bracket splitting strategy

Path Management
    Computed file paths for data exports, checkpoints, and browser profiles
    relative to the configuration file location

Browser Automation Settings
    Selenium configuration for stealth operation and profile management

City Configuration
------------------
Geographic Targeting
- CITY_URL_NAME: "istanbul-avrupa" for URL construction
- FOLDER_NAME: "IstanbulAvrupa" for file path generation
- Target Area: European side of Istanbul rental market

Adaptive Bracket Algorithm
-------------------------
Core Algorithm Parameters
- MAX_LISTINGS_PER_QUERY: 1000 (sahibinden.com hard limit)
- MIN_BRACKET_WIDTH: 50 TL (prevents infinite splitting)
- Algorithm: Binary splitting with recursive resolution

Seed Price Ranges
-----------------
Initial wide ranges covering the complete market spectrum:
- Range 1: 0 - 19,999 TL (High density, will trigger multiple splits)
- Range 2: 20,000 - 39,999 TL (High density)
- Range 3: 40,000 - 59,999 TL
- Range 4: 60,000 - 99,999 TL
- Range 5: 100,000 - 9,999,999 TL (Low density, likely won't split at all)

Splitting Strategy
- **Threshold Detection**: Monitors listing count per range
- **Binary Division**: Splits ranges exceeding 1,000 listings
- **Recursive Resolution**: Continues until all ranges are safe
- **Efficiency**: Uses already-loaded page 1 for immediate scraping

Timing Configuration
--------------------
Page Load Management
- PAGE_LOAD_DELAY: 2.5 seconds base wait time
- JITTER_RANGE: ±50% random variation for natural behavior
- BETWEEN_BRACKET_DELAY: 1.0-2.0 seconds between operations

Rate Limiting Strategy
- Configurable delays prevent detection
- Random jitter simulates human browsing patterns
- Adaptive timing based on server response

Path Resolution
--------------
All paths are computed relative to this configuration file to ensure
consistent operation regardless of execution directory:

OUTPUT_DIR: str
    Target directory for CSV data exports

CHECKPOINT_DIR: str
    Storage location for daily session checkpoint files

SELENIUM_PROFILE_DIR: str
    Persistent browser profile storage location

Daily File Naming
----------------
Files use YYYY-MM-DD format for daily organization:
- CSV Export: IstanbulAvrupa_YYYY-MM-DD.csv
- Checkpoint: checkpoint_YYYY-MM-DD.json

Browser Configuration
---------------------
Selenium Settings
- undetected-chromedriver integration for stealth operation
- Persistent profile storage for session continuity
- Automatic ChromeDriver version management
- Headless mode support for server deployment

Profile Management
- Cookie preservation across scraping sessions
- Login state maintenance when available
- Cache utilization for performance optimization
- User agent rotation for anti-detection

Performance Considerations
-------------------------
Memory Optimization
- Efficient DOM parsing with lxml
- Streaming HTML processing for large pages
- Minimal memory footprint during operation

Error Recovery
- Automatic browser restart on crashes
- Session state restoration from checkpoints
- Configurable retry logic for network issues
- Graceful handling of CAPTCHA events

Import Usage
-------------
Import with 'import config' from any sibling script. All constants are
available as config.CONSTANT_NAME for easy reference throughout the scraper.

Algorithm Dependencies
---------------------
The scraper relies on these configurations for:
- Initial bracket generation from seed ranges
- Recursive splitting threshold management
- Path resolution for data persistence
- Browser automation parameters
- Rate limiting and anti-detection settings
"""

import datetime as _dt
from pathlib import Path as _Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR   = _Path(__file__).resolve().parent          # …/InflationItems/Codes/HousesRent/IstanbulAvrupa/scripts
_SCRAPER_DIR   = _SCRIPTS_DIR.parent                       # …/InflationItems/Codes/HousesRent/IstanbulAvrupa
_PROJECT_ROOT  = _SCRAPER_DIR.parent.parent.parent.parent  # …/InflationResearchStudy

# ── City Settings ─────────────────────────────────────────────────────────────
CITY_URL_NAME = "istanbul-avrupa"
FOLDER_NAME   = "IstanbulAvrupa"

# ── Seed Ranges ───────────────────────────────────────────────────────────────
# Wide starting ranges. The scraper will automatically slice these into optimal
# brackets using the "Total Listings" count on the first page.
SEED_RANGES = [
    (0,      19_999),   # High density, will trigger multiple splits
    (20_000, 39_999),   # High density
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999), # Low density, likely won't split at all
]

# ── Adaptive Splitting Settings ─────────────────────────────────────────────────
# Sahibinden limits queries to 1000 listings (20 pages of 50).
# We split if the total count exceeds this threshold.
MAX_LISTINGS_PER_QUERY = 1000

# Minimum bracket width (TL). A safety valve against infinite recursion if >1000
# listings share the exact same price.
MIN_BRACKET_WIDTH = 50

# Density-aware splitting: split more aggressively in high-density ranges
HIGH_DENSITY_THRESHOLD = 800            # Split earlier if count exceeds this

# ── Request / Timing Settings ─────────────────────────────────────────────────
PAGE_SIZE              = 50             # Listings per page (sahibinden max)
PAGE_LOAD_DELAY        = 2.5            # Seconds to wait after a page loads
                                        # Also the base for the per-page jitter:
                                        #   actual wait = PAGE_LOAD_DELAY * uniform(0.5, 1.5)
BETWEEN_BRACKET_DELAY_MIN = 1.0         # Random range between splits during discovery (s)
BETWEEN_BRACKET_DELAY_MAX = 2.0

# ── Adaptive Rate Limiting Settings ───────────────────────────────────────────
ADAPTIVE_DELAY_ENABLED = True           # Enable adaptive delay adjustments
MIN_DELAY              = 1.5            # Minimum delay (seconds) - safety floor
MAX_DELAY              = 8.0            # Maximum delay (seconds) - cap for errors
DELAY_DECREASE_FACTOR  = 0.95           # Multiply delay by this on success
DELAY_INCREASE_FACTOR  = 1.5            # Multiply delay by this on error
SUCCESS_THRESHOLD      = 3              # Consecutive successes before reducing delay

# ── Retry Settings ─────────────────────────────────────────────────────────────
MAX_RETRIES            = 3              # Maximum retry attempts for failed requests
RETRY_BACKOFF_BASE     = 2.0            # Base delay for exponential backoff (seconds)
RETRY_BACKOFF_MAX      = 30.0           # Maximum backoff delay (seconds)

# ── Browser Settings ──────────────────────────────────────────────────────────
SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")
CHROMEDRIVER_PATH    = str(_SCRAPER_DIR / ".." / "chromedriver")

# ── Output Settings ───────────────────────────────────────────────────────────
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

# Base output directory
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "HousesRent" / FOLDER_NAME)

OUTPUT_DIR      = BASE_OUTPUT_DIR
INFLATION_DIR   = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

CHECKPOINT_DIR  = str(_SCRAPER_DIR / "checkpoints")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"{FOLDER_NAME}_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"checkpoint_{_TODAY}.json")
