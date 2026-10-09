import csv
import os
import platform
import random
import shutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

# =========================
# Config
# =========================

CITIES: Dict[str, str] = {
    "Duzce": "https://www.sahibinden.com/kiralik/duzce",
    "Kocaeli": "https://www.sahibinden.com/kiralik/kocaeli",
    "Sakarya": "https://www.sahibinden.com/kiralik/sakarya",
}

DATA_GROUP_FOLDER = "Duzce_Kocaeli_Sakarya"
HEADLESS = os.environ.get("HEADLESS", "").strip().lower() in {"1", "true", "yes"}

SLEEP_MIN = 2.5
SLEEP_MAX = 4.5

# Brave major version on Windows (from your earlier error message).
# On Linux, version is auto-detected from the installed Chromium.
BROWSER_MAJOR_VERSION = 145

# Persistent profile so manual verification/cookies stick
PROFILE_DIR_NAME = "SeleniumProfile_PERSISTENT"

PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 120  # raise a bit; Kocaeli can be big

# Default brackets
PRICE_BRACKETS_DEFAULT: List[Tuple[int, int]] = [
    (0, 7999),
    (8000, 9999),
    (10000, 11999),
    (12000, 13999),
    (14000, 15999),
    (16000, 17999),
    (18000, 19999),
    (20000, 22999),
    (23000, 26999),
    (27000, 9999999),
]

# More granular brackets for Kocaeli (bigger market)
PRICE_BRACKETS_KOCAELI: List[Tuple[int, int]] = [
    (0, 9999),
    (10000, 12999),
    (13000, 14999),
    (15000, 16999),
    (17000, 18999),
    (19000, 20999),
    (21000, 22999),
    (23000, 24999),
    (25000, 27999),
    (28000, 31999),
    (32000, 37999),
    (38000, 44999),
    (45000, 54999),
    (55000, 9999999),
]


# =========================
# Paths
# =========================

def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))


def data_dir_for_city(city: str) -> str:
    return os.path.join(repo_root(), "Datas", "HousesRent", DATA_GROUP_FOLDER, city)


# =========================
# Browser path
# =========================

def find_browser_exe() -> str:
    # Explicit override via env var (works on any platform)
    for env_var in ("BROWSER_PATH", "BRAVE_PATH"):
        val = os.environ.get(env_var, "").strip()
        if val and os.path.isfile(val):
            return val

    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
    else:  # Linux / macOS
        candidates = [
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
        ]

    for p in candidates:
        if p and os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "Browser executable not found. "
        "Set BROWSER_PATH environment variable to the full path of your browser binary."
    )


# =========================
# Driver
# =========================

def setup_driver() -> uc.Chrome:
    browser_exe = find_browser_exe()

    options = uc.ChromeOptions()
    profile_path = os.path.join(os.path.dirname(__file__), PROFILE_DIR_NAME)
    options.add_argument(f"--user-data-dir={profile_path}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")

    # Slightly more "human"
    options.add_argument("--lang=tr-TR")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if HEADLESS:
        options.add_argument("--headless=new")

    # On Linux use Chromium with pinned version (146); on Windows use pinned Brave version.
    version = 146 if platform.system() != "Windows" else BROWSER_MAJOR_VERSION

    return uc.Chrome(
        options=options,
        browser_executable_path=browser_exe,
        version_main=version,
    )


def close_driver(driver: Optional[uc.Chrome]) -> None:
    if driver is None:
        return
    try:
        driver.quit()
    except Exception:
        pass


def polite_sleep() -> None:
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))


# =========================
# Block detection (table-based)
# =========================

def is_block_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    # If listings table exists, not blocked
    if soup.select_one("#searchResultsTable"):
        return False

    lower = html.lower()
    signals = [
        "just a moment",
        "bir dakika lütfen",
        "lütfen bekleyiniz",
        "cf-challenge",
        "challenge-error-text",
        "access denied",
        "forbidden",
        "güvenlik doğrulama",
        "robot olmadığınızı",
        "captcha",
        "üye girişi",
        "giriş yap",
    ]
    return any(s in lower for s in signals)


def ensure_access(driver: uc.Chrome, url: str) -> None:
    driver.get(url)
    polite_sleep()

    if is_block_page(driver.page_source):
        print("\n[BLOCK DETECTED] Waiting 30s and retrying automatically...")
        time.sleep(30)
        driver.get(url)
        polite_sleep()


# =========================
# Parsing
# =========================

def extract_listings_from_html(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Widen selector: some rows might not have 'searchResultsItem'
    rows = soup.select("#searchResultsTable tbody tr")

    out: List[dict] = []
    for row in rows:
        price_elem = row.select_one(".searchResultsPriceValue")
        loc_elem = row.select_one(".searchResultsLocationValue")
        attr_elems = row.select(".searchResultsAttributeValue")

        price = price_elem.get_text(strip=True) if price_elem else ""
        district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""
        rooms = attr_elems[1].get_text(strip=True) if len(attr_elems) > 1 else ""

        if price and district:
            out.append({"District": district, "Rooms": rooms, "Price": price})

    return out


def find_next_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    next_a = soup.find("a", title="Sonraki")
    if next_a and next_a.get("href"):
        return "https://www.sahibinden.com" + next_a["href"]
    return None


# =========================
# CSV
# =========================

def append_to_daily_csv(city: str, rows: List[dict]) -> str:
    os.makedirs(data_dir_for_city(city), exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{city.lower()}_{today}.csv"  # city prefix added
    out_path = os.path.join(data_dir_for_city(city), filename)

    file_exists = os.path.isfile(out_path)
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            w.writeheader()
        w.writerows(rows)

    return out_path


# =========================
# Bracket URL
# =========================

def build_bracket_url(base_url: str, min_p: int, max_p: int) -> str:
    return f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"


# =========================
# Scraper
# =========================

def scrape_city(driver: uc.Chrome, city: str, base_url: str) -> Tuple[uc.Chrome, str]:
    print(f"\n=== Scraping: {city} ===")
    last_out_path = ""

    brackets = PRICE_BRACKETS_KOCAELI if city == "Kocaeli" else PRICE_BRACKETS_DEFAULT

    for (min_p, max_p) in brackets:
        print(f"\n--- Bracket {min_p} - {max_p} ---")
        url = build_bracket_url(base_url, min_p, max_p)

        page_idx = 0
        while True:
            page_idx += 1
            if page_idx > MAX_PAGES_PER_BRACKET:
                print("Bracket page limit reached. Consider splitting brackets smaller.")
                break

            try:
                ensure_access(driver, url)
                html = driver.page_source

                # If still blocked, pause/retry (no skipping!)
                if is_block_page(html):
                    print("Still blocked on this bracket page. Waiting 60s and retrying...")
                    time.sleep(60)
                    continue

                rows = extract_listings_from_html(html)
                print(f"Page {page_idx}: {len(rows)} listings")

                # Critical fix: do NOT skip zero-listing pages silently
                if len(rows) == 0:
                    print("Zero listings on page (possible soft-block). URL:", driver.current_url)
                    print("Skipping this bracket automatically...")
                    break

                last_out_path = append_to_daily_csv(city, rows)
                print(f"Appended {len(rows)} rows -> {last_out_path}")

                next_url = find_next_url(html)
                if not next_url:
                    break

                url = next_url
                polite_sleep()

            except WebDriverException as e:
                msg = str(e).lower()
                if "connection refused" in msg or "max retries exceeded" in msg or "disconnected" in msg:
                    print("\n[DRIVER DIED] Recreating driver and continuing...")
                    close_driver(driver)
                    time.sleep(2.0)
                    driver = setup_driver()
                    continue
                raise

    return driver, last_out_path


def main() -> None:
    driver: Optional[uc.Chrome] = None
    try:
        driver = setup_driver()
        for city, url in CITIES.items():
            driver, out_path = scrape_city(driver, city, url)
            if out_path:
                print(f"\nDone: {city} -> {out_path}")
            else:
                print(f"\nDone: {city} (no output file written)")
            time.sleep(2.0)
    finally:
        close_driver(driver)
        # Keep profile for next day (so you don't verify again)
        # If you want cleanup, uncomment:
        # shutil.rmtree(os.path.join(os.path.dirname(__file__), PROFILE_DIR_NAME), ignore_errors=True)


if __name__ == "__main__":
    main()