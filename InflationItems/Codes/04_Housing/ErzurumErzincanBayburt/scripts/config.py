"""
Configuration settings for the Erzurum / Erzincan / Bayburt rent scraper.
Source: sahibinden.com

Adapted from the IstanbulAvrupa scraper by Batu Koray Masak.
Uses SeleniumBase (UC mode) for Apple Silicon compatibility.

Bracket Strategy: Smart Adaptive Brackets with Early Peek
---------------------------------------------------------
Instead of static brackets, we use wide seed ranges. On the first page of any
range, the scraper peeks at the "Total Listings Found" text.
  - If <= 1000: It safely scrapes all pages.
  - If > 1000: It immediately splits the range in half and recurses.
"""

import datetime as _dt
import os as _os
from pathlib import Path as _Path

# -- Paths -----------------------------------------------------------------
_SCRIPTS_DIR  = _Path(__file__).resolve().parent          # .../ErzurumErzincanBayburt/scripts
_SCRAPER_DIR  = _SCRIPTS_DIR.parent                       # .../ErzurumErzincanBayburt
_PROJECT_ROOT = _SCRAPER_DIR.parent.parent.parent         # .../InflationResearchStudy

FOLDER_NAME = "ErzurumErzincanBayburt"

# -- City definitions ------------------------------------------------------
CITIES = [
    {
        "url_slug": "erzurum",
        "name": "Erzurum",
        "seed_ranges": [
            (0,      9_999),
            (10_000, 19_999),
            (20_000, 39_999),
            (40_000, 9_999_999),
        ],
    },
    {
        "url_slug": "erzincan",
        "name": "Erzincan",
        "seed_ranges": [
            (0,      9_999),
            (10_000, 19_999),
            (20_000, 39_999),
            (40_000, 9_999_999),
        ],
    },
    {
        "url_slug": "bayburt",
        "name": "Bayburt",
        "seed_ranges": [
            (0,      14_999),
            (15_000, 9_999_999),
        ],
    },
]

# -- Adaptive Splitting Settings -------------------------------------------
MAX_LISTINGS_PER_QUERY = 1000
MIN_BRACKET_WIDTH = 50

# -- Request / Timing Settings ---------------------------------------------
PAGE_SIZE              = 50
PAGE_LOAD_DELAY        = 1.2   # Mean page load wait
PAGE_LOAD_STDEV        = 0.6
PAGE_LOAD_FLOOR        = 0.2
PAGE_TURN_DELAY_MEAN   = 1.2
PAGE_TURN_DELAY_STDEV  = 0.6
PAGE_TURN_DELAY_FLOOR  = 0.2
BETWEEN_BRACKET_DELAY_MEAN = 1.6
BETWEEN_BRACKET_DELAY_STDEV = 0.6
BETWEEN_BRACKET_DELAY_FLOOR = 0.2
BETWEEN_CITY_DELAY_MEAN    = 1.9
BETWEEN_CITY_DELAY_STDEV   = 1.2
BETWEEN_CITY_DELAY_FLOOR   = 0.2

# -- Output Settings -------------------------------------------------------
_DATE_OVERRIDE = _os.getenv("SCRAPE_DATE_OVERRIDE", "").strip()
if _DATE_OVERRIDE:
    TODAY = _dt.date.fromisoformat(_DATE_OVERRIDE).strftime("%Y-%m-%d")
else:
    TODAY = _dt.date.today().strftime("%Y-%m-%d")

OUTPUT_BASE_DIR = str(_PROJECT_ROOT / "Datas" / "HousesRent" / FOLDER_NAME)
CHECKPOINT_DIR  = str(_SCRAPER_DIR / "checkpoints")


def get_city_output_dir(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name)

def get_city_csv_path(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name / f"{city_name}_{TODAY}.csv")

def get_checkpoint_file() -> str:
    return str(_Path(CHECKPOINT_DIR) / f"checkpoint_{TODAY}.json")


def get_city_profile_dir(city_name: str) -> str:
    return str(_Path(SELENIUM_PROFILE_DIR) / city_name.lower())


# -- Browser Settings ------------------------------------------------------
SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")
