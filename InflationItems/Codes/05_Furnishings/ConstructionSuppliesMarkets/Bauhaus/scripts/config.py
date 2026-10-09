"""
Bauhaus Scraper Configuration Module
==================================

This module serves as the centralized configuration repository for the Bauhaus
product scraping system, providing all constants, headers, performance settings,
and path management functionality optimized for high-speed operation.

Configuration Sections
----------------------
HTTP Request Configuration
    Headers, authentication parameters, and request settings required
    for successful website communication

Performance Parameters
    Tunable knobs that control request rate, retry behavior, concurrency,
    and rate limiting settings optimized for speed

Path Management
    Computed file paths for data exports, checkpoints, and session storage
    relative to the configuration file location

Request Configuration
---------------------
DEFAULT_HEADERS: dict
    Realistic browser headers for anti-detection:
    - Chrome-based User-Agent for compatibility
    - Standard accept headers for proper content negotiation
    - Turkish language preference for localized content

Base URL Configuration
----------------------
BASE_URL: str
    Root domain for Bauhaus e-commerce platform

Performance Parameters
---------------------
REQUEST_DELAY: float (default: 2.0 seconds)
    Base delay between paginated requests with random jitter applied

JITTER_RANGE: tuple (default: (1.0, 2.0))
    Random multiplier range applied to base delay for request distribution

MAX_RETRIES: int (default: 5)
    Maximum retry attempts for failed HTTP requests before skipping

RETRY_BACKOFF: float (default: 3.0 seconds)
    Seed value for exponential backoff calculation (actual wait = seed × attempt)

DEFAULT_WORKERS: int (default: 2)
    Thread pool size for parallel category processing

Path Resolution
--------------
All paths are computed relative to this configuration file to ensure
consistent operation regardless of execution directory:

OUTPUT_DIR: str
    Target directory for CSV data exports

CHECKPOINT_DIR: str
    Storage location for daily session checkpoint files

Performance Optimization Features
----------------------------------
Configuration supports the six key optimizations:
- lxml parser integration for fast HTML processing
- CSS selector targeting for efficient DOM traversal
- Session reuse for connection pooling
- Batched checkpoint writing (every 5 categories)
- String optimization for price cleaning
- Adaptive rate limiting for intelligent timing

Daily File Naming
----------------
Files use YYYY-MM-DD format for daily organization:
- CSV Export: bauhaus_YYYY-MM-DD.csv
- Checkpoint: bauhaus_checkpoint_YYYY-MM-DD.json

Directory Structure
------------------
Paths are automatically computed relative to project structure:
- Scripts directory location detection
- Project root path resolution
- Output directory creation if needed
- Checkpoint directory management

Import Usage
-------------
Import with 'import config' from any sibling script. All constants are
available as config.CONSTANT_NAME for easy reference throughout the scraper.

Performance Tuning
------------------
The configuration is optimized for:
- Maximum throughput while maintaining server compatibility
- Minimal memory footprint during operation
- Efficient file I/O with batched operations
- Robust error recovery with exponential backoff
"""

import os

# --- Request Settings ---
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Connection": "keep-alive",
}

BASE_URL = "https://www.bauhaus.com.tr"

REQUEST_DELAY = 2.0  # Base delay between requests
JITTER_MIN = 1.0     # Jitter multiplier min
JITTER_MAX = 2.0     # Jitter multiplier max
MAX_RETRIES = 5      # Retry attempts for failed requests
RETRY_BACKOFF = 3    # Exponential backoff seed

DEFAULT_WORKERS = 2  # Number of parallel workers

# Browser TLS fingerprint to impersonate via curl_cffi. Bauhaus blocks
# stock python-requests TLS handshakes with 403 even when headers look fine,
# so we impersonate a real Chrome client at the TLS level.
IMPERSONATE_BROWSER = "chrome124"

MAX_403_RETRIES = 5    # Max retry rounds for 403-blocked categories
COOLDOWN_BASE = 120    # Base cooldown in seconds (multiplied by retry round)

# In-page 403 handling: retry the same page with a fresh session and growing
# backoff before giving up and bubbling a BauhausBlockedException up to the
# category-level retry loop. This recovers from transient IP/TLS rate limits
# that would otherwise wipe an entire category from the day's output.
MAX_403_PAGE_RETRIES = 3       # Per-page 403 retry attempts before bailing
PAGE_403_COOLDOWN_BASE = 30    # Base seconds; actual = BASE * attempt

# --- Paths ---
# By default, save to InflationItems/Datas/ConstructionSuppliesMarkets/Datas/
# Compute absolute paths relative to this config file's location to be robust
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPTS_DIR, "../../../../../"))

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "InflationItems", "Datas", "ConstructionSuppliesMarkets", "Bauhaus")
CHECKPOINT_DIR = os.path.join(SCRIPTS_DIR, "..", "checkpoints")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
