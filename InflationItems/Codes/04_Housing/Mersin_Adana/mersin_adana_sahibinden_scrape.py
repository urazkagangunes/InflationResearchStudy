import csv
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

CITIES: Dict[str, str] = {
    "Mersin": "https://www.sahibinden.com/kiralik/mersin",
    "Adana": "https://www.sahibinden.com/kiralik/adana",
}

HEADLESS = os.environ.get("HEADLESS", "").strip().lower() in {"1", "true", "yes"}

SLEEP_MIN = 2.5
SLEEP_MAX = 4

BROWSER_MAJOR_VERSION = 145

PROFILE_DIR_NAME = "SeleniumProfile_Sahibinden"

PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 150

PRICE_BRACKETS: List[Tuple[int, int]] = [
    (0, 10999),
    (11000, 12999),
    (13000, 14999),
    (15000, 16999),
    (17000, 18999),
    (19000, 20999),
    (21000, 23999),
    (24000, 26999),
    (27000, 30999),
    (31000, 35999),
    (36000, 44999),
    (45000, 59999),
    (60000, 9999999),
]


# Paths
def repo_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))

def data_dir_for_city(city: str) -> str:
    return os.path.join("InflationItems", "Datas", "HousesRent", city)

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    profile_path = os.path.join(os.path.dirname(__file__), PROFILE_DIR_NAME)
    options.add_argument(f"--user-data-dir={profile_path}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")

    if HEADLESS:
        options.add_argument("--headless=new")

    return uc.Chrome(
        options=options,
        version_main=147
    )

def close_driver(driver: Optional[uc.Chrome]) -> None:
    if driver is None: return
    try:
        driver.quit()
    except Exception:
        pass


def polite_sleep() -> None:
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

# Block detection
def is_block_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("#searchResultsTable"):
        return False

    lower = html.lower()
    signals = [
        "just a moment", "bir dakika lütfen", "lütfen bekleyiniz",
        "cf-challenge", "access denied", "robot olmadığınızı", "captcha"
    ]
    return any(s in lower for s in signals)


def ensure_access(driver: uc.Chrome, url: str) -> None:
    driver.get(url)
    polite_sleep()

    if is_block_page(driver.page_source):
        print("\n[BLOCK DETECTED] manual verification")
        input("press ENTER while you see the rental cards")
        driver.get(url)
        polite_sleep()


# Parsing
def extract_listings_from_html(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#searchResultsTable tbody tr.searchResultsItem")

    out: List[dict] = []
    for row in rows:
        price_elem = row.select_one(".searchResultsPriceValue")
        loc_elem = row.select_one(".searchResultsLocationValue")
        attr_elems = row.select(".searchResultsAttributeValue")

        price = price_elem.get_text(strip=True) if price_elem else ""
        district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""
        rooms = attr_elems[1].get_text(strip=True) if len(attr_elems) > 1 else ""

        if price and district:
            clean_price = price.replace("TL", "").replace(".", "").strip()
            out.append({"District": district, "Rooms": rooms, "Price": clean_price})
    return out


def find_next_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    next_a = soup.find("a", title="Sonraki")
    if next_a and next_a.get("href"):
        return "https://www.sahibinden.com" + next_a["href"]
    return None

def append_to_daily_csv(city: str, rows: List[dict]) -> str:
    path = data_dir_for_city(city)
    os.makedirs(path, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{city.lower()}_{today}.csv"
    out_path = os.path.join(path, filename)

    file_exists = os.path.isfile(out_path)
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            w.writeheader()
        w.writerows(rows)

    return out_path

def build_bracket_url(base_url: str, min_p: int, max_p: int) -> str:
    return f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"

def scrape_city(driver: uc.Chrome, city: str, base_url: str) -> Tuple[uc.Chrome, str]:
    print(f"Starting sity: {city}")
    last_out_path = ""

    # Выбор корзин в зависимости от города
    brackets = PRICE_BRACKETS

    for (min_p, max_p) in brackets:
        print(f"\n--- Range: {min_p} - {max_p} TL ---")
        url = build_bracket_url(base_url, min_p, max_p)

        page_idx = 0
        while True:
            page_idx += 1
            if page_idx > MAX_PAGES_PER_BRACKET:
                break

            try:
                ensure_access(driver, url)
                html = driver.page_source

                if is_block_page(html):
                    input("[!] blocked. solve and press enter")
                    continue

                rows = extract_listings_from_html(html)

                if len(rows) == 0:
                    print(f"empty page: {url}.")
                    input("solve the problem and press ENTER")
                    rows = extract_listings_from_html(driver.page_source)
                    if not rows: break

                last_out_path = append_to_daily_csv(city, rows)
                next_url = find_next_url(html)
                if not next_url:
                    break

                url = next_url
                polite_sleep()

            except WebDriverException:
                print("\n[DRIVER ERROR]")
                close_driver(driver)
                time.sleep(5)
                driver = setup_driver()
                continue

    return driver, last_out_path


def main() -> None:
    driver: Optional[uc.Chrome] = None
    try:
        driver = setup_driver()
        for city, url in CITIES.items():
            driver, out_path = scrape_city(driver, city, url)
            print(f"Finished {city}")
            time.sleep(5.0)
    finally:
        close_driver(driver)

if __name__ == "__main__":
    main()