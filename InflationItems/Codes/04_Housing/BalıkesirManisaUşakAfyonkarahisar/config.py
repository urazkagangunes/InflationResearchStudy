import datetime as _dt
from pathlib import Path as _Path

# ── Paths
_SCRIPTS_DIR   = _Path(__file__).resolve().parent
_SCRAPER_DIR   = _SCRIPTS_DIR
_PROJECT_ROOT  = _SCRIPTS_DIR.parent # Klasör yapına göre burayı kontrol et

# ── City Settings
CITIES = [
    {"url_name": "balikesir", "folder": "Balikesir"},
    {"url_name": "manisa", "folder": "Manisa"},
    {"url_name": "usak", "folder": "Usak"},
    {"url_name": "afyonkarahisar", "folder": "Afyonkarahisar"},
]

# ── Seed Ranges
SEED_RANGES = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999),
]

MAX_LISTINGS_PER_QUERY = 1000
MIN_BRACKET_WIDTH = 50
PAGE_SIZE = 50
PAGE_LOAD_DELAY = 2.5
PAGE_TURN_DELAY_MIN = 2.0
PAGE_TURN_DELAY_MAX = 4.0
BETWEEN_BRACKET_DELAY_MIN = 1.0
BETWEEN_BRACKET_DELAY_MAX = 2.0

SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")
_TODAY = _dt.date.today().strftime("%Y-%m-%d")
OUTPUT_BASE_DIR = _PROJECT_ROOT / "Datas" / "HousesRent"
CHECKPOINT_DIR  = _SCRAPER_DIR / "checkpoints"
