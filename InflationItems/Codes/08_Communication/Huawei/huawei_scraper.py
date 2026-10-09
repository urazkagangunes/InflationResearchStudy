from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime

# 1. Complete Category Map for Huawei Turkey
CATEGORY_URLS = {
    "Telefon": "https://consumer.huawei.com/tr/phones/",
    "PC": "https://consumer.huawei.com/tr/laptops/",
    "Tablet": "https://consumer.huawei.com/tr/tablets/",
    "Akıllı Saat": "https://consumer.huawei.com/tr/wearables/",
    "Ses": "https://consumer.huawei.com/tr/audio/",
    "Router": "https://consumer.huawei.com/tr/routers/"
}


def get_save_path():
    """
    Dynamically maps the path for the daily CSV export.
    From: .../InflationItems/Codes/TechnologicalProducts/Huawei
    To:   .../InflationItems/Datas/TechnologicalProducts/Huawei
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Go up 3 levels to reach the main 'InflationItems' folder
    level_1_up = os.path.dirname(current_dir)
    level_2_up = os.path.dirname(level_1_up)
    inflation_items_dir = os.path.dirname(level_2_up)

    # Build the path down into the target Datas directory
    target_dir = os.path.join(inflation_items_dir, "Datas", "TechnologicalProducts", "Huawei")

    os.makedirs(target_dir, exist_ok=True)
    today_date = datetime.now().strftime("%Y-%m-%d")

    return os.path.join(target_dir, f"huawei_{today_date}.csv")


def scrape_category_popup(driver, category_name, url):
    """Navigates to a category, opens the popup menu, and scrapes the raw data."""
    print(f"\n--- Navigating to {category_name} ---")
    driver.get(url)

    time.sleep(3)

    try:
        print("Looking for the 'Tümünü Görüntüle' or 'Tümü Göster' button...")
        # Smart XPath to handle different naming conventions across Huawei's site
        xpath = "(//*[contains(text(), 'Tümünü Görüntüle') or contains(text(), 'Tümünü görüntüle') or contains(text(), 'Tümü Göster') or contains(text(), 'Tümünü Göster')])[1]"

        button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

        # Scroll to the button and click it
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", button)

        print("Button clicked! Waiting for popup to inject data...")

        # Wait until at least one product card renders inside the popup
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-item"))
        )
        time.sleep(2)

        # Parse the live HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_popups = soup.find_all('div', class_='popup-wrap')

        discovered_data = []
        total_seen_in_category = 0

        for popup in all_popups:
            product_cards = popup.find_all('div', class_='product-item')
            total_seen_in_category += len(product_cards)

            for card in product_cards:
                try:
                    # Extract Name
                    name_tag = card.find('a', class_='product-title')
                    prod_name = name_tag.text.strip() if name_tag else ""

                    # Extract Price
                    price_div = card.find('div', class_='price-height')
                    prod_price = price_div.text.strip() if price_div else ""

                    # Prevent duplicates if a product is listed multiple times in the menu
                    if prod_name and not any(d['Product Name'] == prod_name for d in discovered_data):
                        discovered_data.append({
                            "Product Name": prod_name,
                            "Price": prod_price,
                            "Category": category_name
                        })
                except Exception as inner_e:
                    continue

        total_collected = len(discovered_data)
        print(f"-> Seen:      {total_seen_in_category} raw product cards in HTML.")
        print(f"-> Collected: {total_collected} valid, unique products.")

        return discovered_data, total_seen_in_category

    except Exception as e:
        print(f"-> No button found or failed to load items for {category_name}.")
        return [], 0


if __name__ == "__main__":
    print("Starting Huawei Full-Catalog Selenium Scraper...")

    # Configure Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-notifications')
    # Uncomment the next line to run in the background (no visible browser window)
    # options.add_argument('--headless=new')

    driver = webdriver.Chrome(options=options)

    all_category_data = []
    grand_total_seen = 0

    try:
        # 1. Loop through all specified categories
        for category, url in CATEGORY_URLS.items():
            data, seen_count = scrape_category_popup(driver, category, url)

            all_category_data.extend(data)
            grand_total_seen += seen_count

        # 2. Process and Export Data
        if all_category_data:
            save_path = get_save_path()
            df = pd.DataFrame(all_category_data, columns=["Product Name", "Price", "Category"])

            # Print Final Summary Block
            print(f"\n=========================================")
            print(f"          FINAL SCRAPING SUMMARY         ")
            print(f"=========================================")
            print(f"Total HTML Cards Seen    : {grand_total_seen}")
            print(f"Total Duplicates Skipped : {grand_total_seen - len(df)}")
            print(f"Total Unique Items Saved : {len(df)}")
            print(f"=========================================\n")

            # Save to the dynamically calculated path
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"Data successfully saved to:\n{save_path}")
        else:
            print("\nPipeline finished, but no data was collected.")

    finally:
        # Ensure the browser instance is always closed
        driver.quit()