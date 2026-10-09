#!/usr/bin/env python3
"""
Sahibinden.com rental scraper for Kahramanmaras, Gaziantep, and Kilis

Goals:
- Run daily in GitHub Actions (or self-hosted runner)
- Save CSVs as: {city}_{YYYY-MM-DD}.csv
- Columns: District, Rooms, Price, Scraped_Date
- Always create the CSV even if 0 listings (headers only)
- Avoid long loops when blocked (fail fast)
"""

import csv
import os
import random
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# -----------------------------
# Config
# -----------------------------

CITIES: Dict[str, str] = {
    "maras": "https://www.sahibinden.com/kiralik/kahramanmaras",
    "antep": "https://www.sahibinden.com/kiralik/gaziantep",
    "kilis": "https://www.sahibinden.com/kiralik/kilis",
}

HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
TIMEOUT_SECONDS = 30

# Politeness (not evasion)
SLEEP_MIN = 1.5
SLEEP_MAX = 3.5

PAGING_SIZE = 50
MAX_PAGES_PER_CITY = 5  # keep short + stable; increase only if you are not blocked

# One bracket only (simple + fast)
PRICE_BRACKETS: List[Tuple[int, int]] = [(0, 9_999_999)]


# -----------------------------
# Helpers
# -----------------------------

def is_github_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS") == "true"


def utc_now_str() -> str:
    # Keep a consistent timestamp in UTC for research
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def polite_sleep() -> None:
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))


def get_chrome_major_version() -> Optional[int]:
    """
    Try to detect Chrome major version on Linux runners.
    If unavailable, return None and let uc handle it.
    """
    try:
        result = subprocess.run(
            ["google-chrome", "--version"], capture_output=True, text=True, timeout=5
        )
        # e.g. "Google Chrome 123.0.6312.86"
        parts = result.stdout.strip().split()
        if parts:
            version = parts[-1]
            major = int(version.split(".")[0])
            print(f"Detected Chrome version: {version} (major={major})")
            return major
    except Exception as e:
        print(f"Chrome version detection failed: {e}")
    return None


def get_repo_root() -> str:
    # This file is Codes/HousesRent/Antep_Maras_Kilis/antep_maras_kilis.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "../../../"))


def get_data_dir(city: str) -> str:
    city_folder_map = {"maras": "Maras", "antep": "Antep", "kilis": "Kilis"}
    city_folder = city_folder_map.get(city, city.capitalize())
    return os.path.join(get_repo_root(), "Datas", "HousesRent", city_folder)


def ensure_daily_csv_exists(city: str) -> str:
    """
    Ensure the daily CSV exists with header even if no data is scraped.
    Returns path.
    """
    city_dir = get_data_dir(city)
    os.makedirs(city_dir, exist_ok=True)

    filename = f"{city.lower()}_{today_utc_date()}.csv"
    out_path = os.path.join(city_dir, filename)

    if not os.path.exists(out_path):
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=["District", "Rooms", "Price", "Scraped_Date"]
            )
            writer.writeheader()

    return out_path


def append_rows(out_path: str, rows: List[dict]) -> None:
    if not rows:
        return
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["District", "Rooms", "Price", "Scraped_Date"]
        )
        writer.writerows(rows)


def is_block_page(html: str) -> bool:
    """
    Detect challenge/blocked pages.
    We treat "no results table + challenge signals" as blocked.
    """
    soup = BeautifulSoup(html, "html.parser")

    # If results table exists, assume OK
    if soup.select_one("#searchResultsTable"):
        return False

    lower = html.lower()
    signals = [
        "just a moment",
        "bir dakika lütfen",
        "cf-challenge",
        "cloudflare",
        "güvenlik doğrulama",
        "robot olmadığınızı",
        "captcha",
        "access denied",
        "403 forbidden",
        "forbidden",
    ]
    return any(s in lower for s in signals)


def wait_for_results_or_timeout(driver: uc.Chrome, timeout: int = 10) -> bool:
    """
    Wait briefly for the search results table to appear.
    Returns True if found.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#searchResultsTable"))
        )
        return True
    except TimeoutException:
        return False


def build_bracket_url(base_url: str, min_p: int, max_p: int) -> str:
    return f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"


def find_next_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    next_a = soup.find("a", title="Sonraki")
    if next_a and next_a.get("href"):
        href = next_a["href"]
        return href if href.startswith("http") else "https://www.sahibinden.com" + href
    return None


def extract_listings_from_html(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#searchResultsTable tbody tr")

    listings: List[dict] = []
    for row in rows:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            loc_elem = row.select_one(".searchResultsLocationValue")
            attr_elems = row.select(".searchResultsAttributeValue")

            price = price_elem.get_text(strip=True) if price_elem else ""
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""

            # Sahibinden layout can shift; guard indexes
            rooms = ""
            if len(attr_elems) >= 2:
                rooms = attr_elems[1].get_text(strip=True)

            if price and district:
                listings.append(
                    {
                        "District": district,
                        "Rooms": rooms,
                        "Price": price,
                        "Scraped_Date": utc_now_str(),
                    }
                )
        except Exception:
            continue

    return listings


# -----------------------------
# Driver
# -----------------------------

# In your scraper.py, modify setup_driver:
def setup_driver():
    options = uc.ChromeOptions()
    
    # Add proxy - you'll need a proxy service
    PROXY = "http://user:pass@proxy-provider.com:port"
    options.add_argument(f'--proxy-server={PROXY}')
    
    # Rest of your setup...

    # Keep profile location deterministic
    profile_path = "/tmp/chrome-profile" if is_github_actions() else "ChromeProfile"
    options.add_argument(f"--user-data-dir={profile_path}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")

    # Headless controlled by env
    if HEADLESS:
        options.add_argument("--headless=new")

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    browser_path = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
    version_main = get_chrome_major_version()

    driver = uc.Chrome(
        options=options,
        browser_executable_path=browser_path,
        version_main=version_main,
        headless=HEADLESS,
    )
    driver.set_page_load_timeout(TIMEOUT_SECONDS)
    return driver


def close_driver(driver: Optional[uc.Chrome]) -> None:
    if driver:
        try:
            driver.quit()
        except Exception:
            pass


# -----------------------------
# Scrape logic
# -----------------------------

def load_page(driver: uc.Chrome, url: str) -> Tuple[bool, str]:
    """
    Returns (ok, status):
      ok=True  -> page loaded and looks like listings page OR empty results page
      ok=False -> blocked/challenged or hard error
    """
    try:
        print(f"GET {url[:120]}...")
        driver.get(url)

        # quick wait for results
        _ = wait_for_results_or_timeout(driver, timeout=10)

        html = driver.page_source or ""
        if is_block_page(html):
            return False, "blocked"

        # Not blocked; maybe empty, but OK
        return True, "ok"
    except TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, f"error:{e.__class__.__name__}"


def scrape_city(driver: uc.Chrome, city: str, base_url: str) -> str:
    out_path = ensure_daily_csv_exists(city)

    total = 0
    blocked_count = 0

    for (min_p, max_p) in PRICE_BRACKETS:
        url = build_bracket_url(base_url, min_p, max_p)

        for page_idx in range(1, MAX_PAGES_PER_CITY + 1):
            ok, status = load_page(driver, url)
            if not ok:
                print(f"Status={status} on {city} page {page_idx}.")
                blocked_count += 1

                # Fail-fast: if blocked once, stop this city for today
                if status == "blocked":
                    print(f"Blocked for city={city}. Stop scraping this city today.")
                    return out_path

                # If timeout/error, try a small pause then stop city (avoid loops)
                polite_sleep()
                return out_path

            html = driver.page_source or ""
            rows = extract_listings_from_html(html)
            print(f"{city}: page {page_idx} -> {len(rows)} listings")
            if rows:
                append_rows(out_path, rows)
                total += len(rows)

            next_url = find_next_url(html)
            if not next_url:
                break

            url = next_url
            polite_sleep()

    print(f"Done city={city}. total_rows={total}, blocked_events={blocked_count}")
    return out_path


def main() -> None:
    print("=" * 70)
    print("Starting Sahibinden rental scraper")
    print(f"UTC time: {utc_now_str()}")
    print(f"GitHub Actions: {is_github_actions()}")
    print(f"Headless: {HEADLESS}")
    print("=" * 70)

    driver: Optional[uc.Chrome] = None
    try:
        driver = setup_driver()

        for city, url in CITIES.items():
            print("\n" + "#" * 70)
            print(f"City: {city} | URL: {url}")
            print("#" * 70)

            out_path = scrape_city(driver, city, url)
            print(f"Output CSV: {out_path}")

            # small pause between cities
            time.sleep(2)

        print("\nAll done.")
    finally:
        close_driver(driver)
        # cleanup profile on GitHub Actions
        if is_github_actions() and os.path.exists("/tmp/chrome-profile"):
            shutil.rmtree("/tmp/chrome-profile", ignore_errors=True)


if __name__ == "__main__":
    main()
