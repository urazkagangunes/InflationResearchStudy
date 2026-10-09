import os
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# ============================================================
# Per-city price brackets
# Calibrated estimates for SE Turkey rental market (2026)
# These cities have lower avg. rents than coastal cities.
# Re-calibrate after first real scrape if any bracket >1000 listings.
# ============================================================

DIYARBAKIR_BRACKETS = [
    (0, 7999),          # budget segment
    (8000, 9999),
    (10000, 11999),
    (12000, 13999),
    (14000, 15999),
    (16000, 17999),
    (18000, 19999),
    (20000, 22999),
    (23000, 26999),
    (27000, 9999999),   # premium segment
]

SANLIURFA_BRACKETS = [
    (0, 6999),
    (7000, 8999),
    (9000, 10999),
    (11000, 12999),
    (13000, 14999),
    (15000, 17499),
    (17500, 19999),
    (20000, 24999),
    (25000, 9999999),
]

MARDIN_BRACKETS = [
    (0, 7999),
    (8000, 10999),
    (11000, 13999),
    (14000, 17999),
    (18000, 22999),
    (23000, 9999999),
]

CITIES = {
    'diyarbakir': {'folder': 'Diyarbakir', 'brackets': DIYARBAKIR_BRACKETS},
    'sanliurfa':  {'folder': 'Sanliurfa',  'brackets': SANLIURFA_BRACKETS},
    'mardin':     {'folder': 'Mardin',     'brackets': MARDIN_BRACKETS},
}

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))

_profile_counter = 0


def _detect_chrome_version():
    """Auto-detect installed Chrome major version to avoid driver mismatch."""
    import subprocess
    for cmd in [
        ["google-chrome", "--version"],
        ["google-chrome-stable", "--version"],
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
        ["chromium-browser", "--version"],
    ]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            ver = int(out.split()[-1].split(".")[0])
            print(f"🔍 Detected Chrome version: {ver}")
            return ver
        except Exception:
            continue
    print("⚠️ Could not detect Chrome version, letting UC auto-detect.")
    return None


def setup_driver():
    """Creates a fresh Chrome instance with a brand-new profile."""
    global _profile_counter
    _profile_counter += 1

    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, f"SeleniumProfile_{_profile_counter}")
    options.add_argument(f"--user-data-dir={profile_path}")

    if os.environ.get('HEADLESS', '').lower() in ('1', 'true', 'yes'):
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    chrome_ver = _detect_chrome_version()
    if chrome_ver:
        driver = uc.Chrome(options=options, version_main=chrome_ver)
    else:
        driver = uc.Chrome(options=options)

    print(f"🚀 New Chrome instance #{_profile_counter} started.")
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    print("🔒 Chrome instance closed.")


def is_waiting_page(page_source):
    lower = page_source.lower()
    return any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz", "just a moment", "challenge-error-text", "cf-challenge"])


def is_login_page(page_source):
    lower = page_source.lower()
    login_signals = [
        "giriş yap",
        "üye girişi",
        "captcha",
        "güvenlik doğrulama",
        "robot olmadığınızı",
    ]
    strong_hits = sum(1 for s in login_signals if s in lower)
    return strong_hits >= 1 and "searchresultstable" not in lower


def wait_for_challenge(driver, url, max_wait=20):
    print(f"⏳ Waiting for challenge page to resolve (up to {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(2)
        if not is_waiting_page(driver.page_source):
            print(f"✅ Challenge resolved after ~{(i+1)*2}s")
            return True
    print("⏰ Challenge did not resolve in time.")
    return False


def save_to_csv_incremental(folder_name, data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"✅ Appended {len(data_batch)} records to {file_path}")


def scrape_city(driver, city_url_name, folder_name, brackets):
    print(f"\n{'='*50}")
    print(f"STARTING FULL SCRAPE FOR: {folder_name.upper()}")
    print(f"{'='*50}")

    for min_price, max_price in brackets:
        print(f"\n>>> Price Range: {min_price} TL - {max_price} TL")

        bracket_data = []
        page_num = 1

        url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )
        driver.get(url)

        while True:
            time.sleep(random.uniform(2.5, 4.5))
            page_source = driver.page_source

            # Stage 1: Cloudflare waiting page
            if is_waiting_page(page_source):
                resolved = wait_for_challenge(driver, url)
                if resolved:
                    page_source = driver.page_source
                else:
                    print("🔄 Challenge stuck. Restarting Chrome...")
                    close_driver(driver)
                    time.sleep(random.uniform(5, 10))
                    driver = setup_driver()
                    driver.get(url)
                    time.sleep(random.uniform(4, 7))
                    page_source = driver.page_source
                    if is_waiting_page(page_source):
                        wait_for_challenge(driver, url)
                        page_source = driver.page_source

            # Stage 2: Login / CAPTCHA wall
            if is_login_page(page_source):
                print("🔄 Login/CAPTCHA detected! Restarting Chrome...")
                close_driver(driver)
                time.sleep(random.uniform(5, 10))
                driver = setup_driver()
                driver.get(url)
                time.sleep(random.uniform(4, 7))
                page_source = driver.page_source

                if is_waiting_page(page_source):
                    wait_for_challenge(driver, url)
                    page_source = driver.page_source

                if is_login_page(page_source):
                    print("❌ Still blocked after Chrome restart. Skipping bracket.")
                    break

            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                lower = page_source.lower()
                print(f"🔍 Current URL: {driver.current_url}")
                print(f"🔍 Page title: {soup.title.string if soup.title else 'N/A'}")
                print(f"🔍 Page snippet: {page_source[500:1000]}")
                if "ilan bulunamadı" in lower or "bulunamamıştır" in lower:
                    print(f"No listings in {min_price}-{max_price} TL range.")
                else:
                    print("⚠️ No listings found on this page. Moving to next bracket.")
                break

            print(f"Page {page_num} — {len(listings)} listings")

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    if price != "N/A" and district != "N/A":
                        bracket_data.append({"District": district, "Rooms": rooms, "Price": price})
                except Exception as e:
                    print(f"Row parse error: {e}")
                    continue

            if bracket_data:
                save_to_csv_incremental(folder_name, bracket_data)
                bracket_data = []

            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                driver.get("https://www.sahibinden.com" + next_button['href'])
                page_num += 1
                time.sleep(random.uniform(2, 4))
            else:
                print(f"✅ Finished bracket {min_price}-{max_price} TL.")
                break

    return driver


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            path = os.path.join(SCRIPT_DIR, item)
            try:
                shutil.rmtree(path)
                print(f"🧹 Cleaned up profile: {item}")
            except Exception:
                pass


def main():
    driver = setup_driver()
    try:
        for city_url_name, city_data in CITIES.items():
            driver = scrape_city(driver, city_url_name, city_data['folder'], city_data['brackets'])
            time.sleep(3)
    finally:
        close_driver(driver)
        cleanup_profiles()


if __name__ == "__main__":
    main()
