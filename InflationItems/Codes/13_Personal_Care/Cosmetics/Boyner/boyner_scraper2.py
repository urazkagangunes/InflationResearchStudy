from pathlib import Path
import os
import re
import pandas as pd
import time
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# ── PARALLEL CONFIGURATION ───────────────────────────────────────────────────

# 1. Give this script a unique name (e.g., "part1", "parfum", "makyaj").
# This ensures it saves to its own file: boyner_part1_2026-04-25.csv
SCRIPT_IDENTIFIER = "part2"

# 2. Leave ONLY the categories you want THIS specific script to scrape.
# Delete the others so your other 3 scripts can handle them.
CATEGORY_URLS = {
    "Nemlendirici": "https://www.boyner.com.tr/yuz-nemlendirici-x-c400202",
    "Kore Kozmetik": "https://www.boyner.com.tr/kampanya/kore-kozmetik-urunleri-x-c23894732",
    "Saç Bakım": "https://www.boyner.com.tr/sampuan-sac-bakim-x-c3405682",
    "Güneş Bakım": "https://www.boyner.com.tr/gunes-urunleri-x-c3340247",
}

# ── Tuning ────────────────────────────────────────────────────────────────────
SCROLL_AMOUNT = 600  # Reduced from 1000
SCROLL_PAUSE = 1
MAX_RETRIES = 3
MAX_DRY_ROUNDS = 6


# ─────────────────────────────────────────────────────────────────────────────

def clean_price(price_text):
    if not price_text:
        return None
    cleaned = price_text.replace("Sepette", "").replace("TL", "").replace("\n", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_save_path():
    current_dir = Path(__file__).resolve()
    root = next((p for p in current_dir.parents if (p / ".git").exists()), current_dir.parents[5])
    out_dir = os.path.join(root, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "Boyner")
    os.makedirs(out_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    # Uses the unique SCRIPT_IDENTIFIER to prevent file overwrite collisions
    return os.path.join(out_dir, f"boyner_{SCRIPT_IDENTIFIER}_{date_str}.csv")


def append_to_csv(new_products):
    if not new_products:
        return

    df = pd.DataFrame(new_products)[["Product Name", "Price", "Category"]]
    path = get_save_path()

    file_exists = os.path.isfile(path)
    # Mode 'a' continuously adds rows to the bottom without erasing old data
    df.to_csv(path, mode='a', index=False, header=not file_exists, encoding="utf-8-sig")


def get_total_count(driver):
    SELECTORS = [
        "//*[contains(@class,'result') and contains(text(),'Sonuç')]",
        "//*[contains(@class,'Result') and contains(text(),'Sonuç')]",
        "//*[contains(text(),'Sonuç')]",
    ]
    for xpath in SELECTORS:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                txt = el.text.strip()
                m = re.search(r"([\d\.]+)\s*Sonuç", txt)
                if m:
                    return int(m.group(1).replace(".", ""))
        except Exception:
            continue
    return None


def grab_products(driver):
    titles = driver.find_elements(By.XPATH, "//a[contains(@class,'productInfoBoxTextWrapperTitle')]")
    prices = driver.find_elements(By.XPATH, "//h5[contains(@class,'price_priceMain')]")
    return titles, prices


def retry_call(fn, retries=MAX_RETRIES):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except WebDriverException:
            time.sleep(3 * attempt)
    return None


def wait_for_brand_count(driver, category_count, timeout=15):
    """Poll every 0.5 s until the result counter differs from the full-category count."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = get_total_count(driver)
        if current is not None and current != category_count:
            return current
        time.sleep(0.5)
    return get_total_count(driver)  # last-chance read


def click_brand_with_retry(driver, label, category_count, base_url, max_attempts=3):
    """
    Scroll the label into view, click it, and confirm the page count changed.
    Retries up to max_attempts times.  Returns (brand_count, success_bool).
    """
    for attempt in range(1, max_attempts + 1):
        # Scroll label to center of viewport so it is truly visible
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", label)
        time.sleep(0.4)

        # Prefer a real Selenium click; fall back to JS click
        try:
            label.click()
        except Exception:
            driver.execute_script("arguments[0].click();", label)

        time.sleep(1.5)  # give the XHR request time to fire

        brand_count = wait_for_brand_count(driver, category_count, timeout=15)
        if brand_count is not None and brand_count != category_count:
            return brand_count, True

        print(f"    ⚠️  Click attempt {attempt}/{max_attempts}: count still {category_count}. Retrying...")
        time.sleep(1)

    return get_total_count(driver), False


def scroll_and_collect(driver, category_name, brand_expected=None):
    """
    Scroll the current filtered page and collect products in a single pass.
    """
    collected = {}
    dry_streak = 0
    consecutive_errors = 0

    total_expected = brand_expected if brand_expected is not None else get_total_count(driver)
    if total_expected:
        print(f"    🎯 Target: {total_expected} products.")

    while True:
        result = retry_call(lambda: grab_products(driver))
        if result is not None:
            titles, prices = result
            count_before = len(collected)
            for i in range(min(len(titles), len(prices))):
                try:
                    name = titles[i].text.strip()
                    price = clean_price(prices[i].text)

                    # Combined unique key (name + price) to capture product variants
                    unique_key = f"{name}_{price}"

                    if name and price is not None and unique_key not in collected:
                        collected[unique_key] = {"name": name, "price": price}
                except Exception:
                    continue

            new_items = len(collected) - count_before
            if new_items > 0:
                dry_streak = 0
                print(f"    📦 +{new_items} items (Total: {len(collected)})")
            else:
                dry_streak += 1

        # Break if we hit the target
        if total_expected and len(collected) >= total_expected:
            break

        # Stop if we haven't found anything new for a while (prevents infinite loops)
        if dry_streak >= MAX_DRY_ROUNDS:
            break

        # Detect if we are at the bottom and nothing new is loading
        try:
            at_bottom = driver.execute_script(
                "return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 150")
            if at_bottom and new_items == 0:
                break
        except:
            pass

        # Scroll down
        result = retry_call(lambda: driver.execute_script(f"window.scrollBy(0, {SCROLL_AMOUNT}); return true;"))
        if result is None:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                break
            continue

        consecutive_errors = 0
        time.sleep(SCROLL_PAUSE)

    # Log the final result for this brand
    if total_expected and len(collected) < total_expected:
        shortfall = total_expected - len(collected)
        print(f"    ⚠️ Final result: {len(collected)}/{total_expected} ({shortfall} missing). Saving what we have.")

    return [{"Product Name": d["name"], "Price": d["price"], "Category": category_name} for d in collected.values()]


def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")

    # --- Prevent Chrome from sleeping when out of focus ---
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    # ------------------------------------------------------

    return uc.Chrome(options=options)


def run_boyner_scraper():
    driver = create_driver()
    cookie_accepted = False
    total_session_items = 0

    try:
        for category_name, base_url in CATEGORY_URLS.items():
            print(f"\n{'=' * 60}")
            print(f"📂 [{SCRIPT_IDENTIFIER}] CATEGORY: {category_name.upper()}")
            print(f"{'=' * 60}")

            retry_call(lambda: driver.get(base_url))
            time.sleep(3)

            if not cookie_accepted:
                try:
                    btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                    )
                    btn.click()
                    cookie_accepted = True
                    time.sleep(1)
                except:
                    pass

            print("🔍 Finding brands...")
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'b-panel')]")))
                panels = driver.find_elements(By.XPATH, "//div[contains(@class, 'b-panel')]")

                marka_panel = next((p for p in panels if "Marka" in p.text), None)
                if not marka_panel:
                    print("⚠️ No brands found. Skipping.")
                    continue

                brand_labels = marka_panel.find_elements(By.XPATH,
                                                         ".//label[contains(@class, 'filter_filterItemsCheckbox')]")
                total_brands = len(brand_labels)
                print(f"📋 Found {total_brands} brands.")

            except Exception as e:
                print(f"⚠️ Error reading sidebar: {e}")
                continue

            for i in range(total_brands):
                try:
                    panels = driver.find_elements(By.XPATH, "//div[contains(@class, 'b-panel')]")
                    marka_panel = next((p for p in panels if "Marka" in p.text), None)
                    current_labels = marka_panel.find_elements(By.XPATH,
                                                               ".//label[contains(@class, 'filter_filterItemsCheckbox')]")

                    target_label = current_labels[i]
                    raw_text = target_label.text.strip()
                    brand_name = raw_text.split("(")[0].strip() if raw_text else f"Brand_{i + 1}"

                    print(f"\n  👉 [{i + 1}/{total_brands}] {brand_name}")

                    # Read category-level count BEFORE clicking so we can detect the change
                    category_count = get_total_count(driver)

                    # Scroll into view + click with retry until the page count changes
                    brand_count, confirmed = click_brand_with_retry(
                        driver, target_label, category_count, base_url, max_attempts=2)

                    if confirmed:
                        print(f"    ✅ Brand count confirmed: {brand_count} products.")
                    else:
                        print(f"    ❌ Could not confirm brand filter after 3 click attempts. Skipping brand.")
                        retry_call(lambda: driver.get(base_url))
                        time.sleep(2)
                        continue

                    driver.execute_script("window.scrollTo(0, 0); return true;")
                    products = scroll_and_collect(
                        driver, category_name,
                        brand_expected=brand_count
                    )

                    if products:
                        total_session_items += len(products)
                        print(f"  ✨ Added {len(products)} products to CSV.")
                        append_to_csv(products)
                    else:
                        print(f"  🤷 0 products listed.")

                    retry_call(lambda: driver.get(base_url))
                    time.sleep(2)

                except Exception as e:
                    print(f"  ❌ Error on brand #{i + 1}: {e}")
                    retry_call(lambda: driver.get(base_url))
                    time.sleep(2)
                    continue

    except KeyboardInterrupt:
        print("\n⚠️ Script stopped manually. Data is safely stored in CSV.")

    finally:
        try:
            driver.quit()
        except OSError:
            pass

    print(f"\n🏆 SCRAPING FINISHED FOR {SCRIPT_IDENTIFIER.upper()}!")
    print(f"📊 {total_session_items} products successfully collected.")


if __name__ == "__main__":
    run_boyner_scraper()