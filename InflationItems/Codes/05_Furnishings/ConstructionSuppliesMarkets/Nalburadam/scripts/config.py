"""
config.py — Nalburadam scraper configuration settings.

This module defines the constants, headers, paths, and delay settings used
by the Nalburadam scraper pipeline.
"""

import os

# --- Request Settings ---
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

BASE_URL = "https://www.nalburadam.com"

REQUEST_DELAY = 0.5  # Base delay between requests (mean)
REQUEST_FLOOR = 0.4  # Minimum delay floor
MAX_RETRIES = 20      # Retry attempts for failed requests
RETRY_BACKOFF = 4    # Exponential backoff seed

DEFAULT_WORKERS = 10  # Number of parallel workers

# --- Paths ---
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
# The data folder mirrors the scraper folder (InflationItems/Codes/... ->
# InflationItems/Datas/...), so the path holds in any category layout.
_parts = os.path.dirname(SCRIPTS_DIR).split(os.sep)
_root = _parts.index("InflationItems")
OUTPUT_DIR = os.sep.join(_parts[:_root + 1] + ["Datas"] + _parts[_root + 2:])
CHECKPOINT_DIR = os.path.join(SCRIPTS_DIR, "..", "checkpoints")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
