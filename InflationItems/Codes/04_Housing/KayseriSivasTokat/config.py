import datetime as _dt
from pathlib import Path as _Path

_SCRIPTS_DIR  = _Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent.parent.parent

DEFAULT_BRACKETS = [
    (0,       19_999),
    (20_000,  39_999),
    (40_000,  59_999),
    (60_000,  99_999),
    (100_000, 9_999_999),
]

CITIES = [
    {"url_slug": "kayseri", "name": "Kayseri", "brackets": DEFAULT_BRACKETS},
    {"url_slug": "sivas",   "name": "Sivas",   "brackets": DEFAULT_BRACKETS},
    {"url_slug": "tokat",   "name": "Tokat",   "brackets": DEFAULT_BRACKETS},
]

TODAY = _dt.date.today().strftime("%Y-%m-%d")

OUTPUT_BASE_DIR = str(_PROJECT_ROOT / "Datas" / "HousesRent")
CHECKPOINT_DIR  = str(_SCRIPTS_DIR / "checkpoints")

def get_city_output_dir(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name)

def get_city_csv_path(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name / f"{TODAY}.csv")

def get_checkpoint_file() -> str:
    return str(_Path(CHECKPOINT_DIR) / f"checkpoint_{TODAY}.json")

# --- Timing (seconds) ---
PAGE_LOAD_AFTER_GOTO  = (8.0,  12.0)
BETWEEN_BRACKETS      = (4.0,   6.0)
BETWEEN_PAGES         = (8.0,  12.0)
GOTO_RETRY_WAIT       = (13.0, 18.0)
POST_CHECK_WAIT       = (4.0,   6.0)
HOMEPAGE_WAIT         = (3.0,   5.0)
CITY_CLOSE_WAIT       = 30

# --- Rayobrowse ---
# locale= does NOT exist — use browser_language and ui_language
RAYOBROWSE_HEADLESS         = False
RAYOBROWSE_TARGET_OS        = "windows"   # windows has best fingerprint coverage
RAYOBROWSE_BROWSER_LANGUAGE = "tr-TR,tr;q=0.9"
RAYOBROWSE_UI_LANGUAGE      = "tr-TR"

# --- Scraping limits ---
MAX_RESTARTS_PER_CITY = 3
MAX_PAGES_PER_BRACKET = 20
PAGE_SIZE             = 50

# --- Base URL ---
BASE_URL = "https://www.sahibinden.com"
