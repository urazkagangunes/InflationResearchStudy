import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ── Configuration ─────────────────────────────────────────────────────────────

# HEAVY_BRACKETS: 17 micro-brackets for massive cities to avoid the 1,000 limit
HEAVY_BRACKETS = [
    (0, 11999), (12000, 13999), (14000, 14999), (15000, 15999), (16000, 16999),
    (17000, 17999), (18000, 18999), (19000, 19999), (20000, 20999),
    (21000, 22999), (23000, 24999), (25000, 26999),
    (27000, 29999), (30000, 34999), (35000, 39999), (40000, 49999),
    (50000, 9999999)
]

# LIGHT_BRACKETS: Just 5 wide brackets for smaller cities
LIGHT_BRACKETS = [
    (0, 10000), (10001, 15000), (15001, 20000), (20001, 25000), (25001, 9999999)
]

CITIES = {
    'bursa':   {'folder': 'Bursa',   'brackets': HEAVY_BRACKETS},
    'yalova':  {'folder': 'Yalova',  'brackets': LIGHT_BRACKETS},
    'bilecik': {'folder': 'Bilecik', 'brackets': LIGHT_BRACKETS},
    'kutahya': {'folder': 'Kütahya', 'brackets': LIGHT_BRACKETS}
}

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))

# ── Adaptive delay config ─────────────────────────────────────────────────────
# After this many consecutive clean pages, the inter-page delay shrinks.
FAST_MODE_THRESHOLD = 3   # pages in a row without issues → use SHORT delays
DELAY_PAGE_SHORT    = (0.8, 1.5)   # used once in fast mode
DELAY_PAGE_NORMAL   = (1.5, 2.8)   # default inter-page delay
DELAY_BRACKET       = (1.5, 2.5)   # between brackets (was 2–4 s)
DELAY_CITY          = (2.0, 3.5)   # between cities   (was 3–5 s)
DELAY_INITIAL       = (1.8, 2.8)   # first page of each bracket (was 3.5–5 s)

MAX_RETRIES = 2  # how many times to retry a page before giving up


# ── Driver ────────────────────────────────────────────────────────────────────

def setup_driver():
    """Sets up an undetected Chrome driver with a persistent profile."""
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    # Slightly faster page loads — we control the wait ourselves
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.page_load_strategy = "eager"   # don't wait for images/fonts
    driver = uc.Chrome(options=options, version_main=145)
    driver.set_page_load_timeout(30)
    return driver


# ── CSV ───────────────────────────────────────────────────────────────────────

def save_to_csv_incremental(folder_name, data_batch):
    """Appends a batch of scraped data to the daily CSV file."""
    today_str  = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path  = os.path.join(target_dir, f"{folder_name}_{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"  ✅ Appended {len(data_batch)} records → {file_path}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def wait_for_listings(driver, timeout=12):
    """
    Waits for the results table. Returns the parsed listings list directly
    so the caller does NOT need to re-parse the page source again.
    Returns an empty list on timeout.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#searchResultsTable tbody tr.searchResultsItem")
            )
        )
    except TimeoutException:
        return []

    # Parse once here — avoids a second BS4 pass in the main loop
    soup     = BeautifulSoup(driver.page_source, 'lxml')
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    return listings, soup   # return both so pagination link is accessible


def handle_captcha(driver):
    """
    Pauses and waits for the user to solve a CAPTCHA manually.
    Returns (listings, soup) after confirmation, or ([], None) if still blocked.
    """
    print("\n" + "=" * 55)
    print("⚠️  ACTION REQUIRED: CAPTCHA or Login detected.")
    print("   1. Solve the puzzle in the Chrome window.")
    print("   2. Wait until you can clearly see the listings.")
    print("=" * 55)
    input("   Press ENTER here once listings are visible …\n")

    soup     = BeautifulSoup(driver.page_source, 'lxml')
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    return (listings, soup) if listings else ([], None)


def parse_listings(listings):
    """Extracts District / Rooms / Price from a list of BS4 row elements."""
    records = []
    for row in listings:
        try:
            price_elem    = row.select_one(".searchResultsPriceValue")
            location_elem = row.select_one(".searchResultsLocationValue")
            attributes    = row.select(".searchResultsAttributeValue")

            price    = price_elem.text.strip()    if price_elem    else "N/A"
            district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"
            rooms    = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

            if price != "N/A" and district != "N/A":
                records.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as e:
            print(f"    ⚠ Row parse error: {e}")
    return records


def get_next_url(soup):
    """Returns the next-page URL or None if on the last page."""
    btn = soup.find('a', title='Sonraki')
    if btn and 'href' in btn.attrs:
        return "https://www.sahibinden.com" + btn['href']
    return None


# ── Core scraper ──────────────────────────────────────────────────────────────

def scrape_city(driver, city_url_name, folder_name, brackets):
    print(f"\n{'='*55}")
    print(f"  CITY: {folder_name}")
    print(f"{'='*55}")

    for min_price, max_price in brackets:
        print(f"\n  ▶ Bracket {min_price:,} – {max_price:,} TL")

        url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )
        driver.get(url)
        time.sleep(random.uniform(*DELAY_INITIAL))  # shorter initial delay

        bracket_data       = []
        page_num           = 1
        consecutive_clean  = 0   # tracks pages scraped without issues
        retry_count        = 0

        while True:
            result = wait_for_listings(driver, timeout=12)

            # ── No listings returned ──────────────────────────────────────────
            if not result or not result[0]:
                page_src = driver.page_source.lower()

                # Genuinely empty bracket — move on immediately
                if "ilan bulunamadı" in page_src or "bulunamamıştır" in page_src:
                    print(f"    ↳ Empty bracket — skipping.")
                    break

                # Possible CAPTCHA / block
                listings, soup = handle_captcha(driver)

                if not listings:
                    if retry_count < MAX_RETRIES:
                        retry_count += 1
                        print(f"    ↳ Retry {retry_count}/{MAX_RETRIES} for bracket {min_price}–{max_price} TL …")
                        driver.get(url if page_num == 1 else driver.current_url)
                        time.sleep(random.uniform(3.0, 5.0))
                        continue
                    else:
                        print(f"    ✗ Giving up on bracket {min_price}–{max_price} TL after {MAX_RETRIES} retries.")
                        break

                consecutive_clean = 0  # reset streak after CAPTCHA
                retry_count       = 0

            else:
                listings, soup    = result
                consecutive_clean += 1
                retry_count       = 0

            # ── Parse ─────────────────────────────────────────────────────────
            records = parse_listings(listings)
            bracket_data.extend(records)
            print(f"    Page {page_num:>3} → {len(records):>3} rows  "
                  f"(streak: {consecutive_clean})")

            # ── Pagination ────────────────────────────────────────────────────
            next_url = get_next_url(soup)
            if next_url:
                driver.get(next_url)
                page_num += 1

                # Adaptive delay: go faster once we have a clean streak
                if consecutive_clean >= FAST_MODE_THRESHOLD:
                    time.sleep(random.uniform(*DELAY_PAGE_SHORT))
                else:
                    time.sleep(random.uniform(*DELAY_PAGE_NORMAL))
            else:
                print(f"    ↳ Done with bracket {min_price:,}–{max_price:,} TL "
                      f"({len(bracket_data)} total rows).")
                break

        if bracket_data:
            save_to_csv_incremental(folder_name, bracket_data)

        time.sleep(random.uniform(*DELAY_BRACKET))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    driver = setup_driver()
    try:
        for city_url_name, city_data in CITIES.items():
            scrape_city(driver, city_url_name, city_data['folder'], city_data['brackets'])
            time.sleep(random.uniform(*DELAY_CITY))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()