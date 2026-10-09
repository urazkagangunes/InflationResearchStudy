"""
Data Collection Engine - Dental Care Price Indexation
Description: Automated pipeline designed to parse accordion-style DOM
             structures from private dental clinic registries, extracting
             standardized procedure costs and dynamic pricing ranges.
"""

import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime


def scrape_dentgroup():
    """
    Executes a direct HTML parsing routine to extract the public fee schedule.
    Bypasses internal structural headers and maps the output into a strict
    two-column (Service, Price) format.
    """
    url = "https://dentgroup.com.tr/fiyat-listesi"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("Initializing Data Collection Pipeline...")
    print(f"Step 1: Connecting to Official Registry -> {url}")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"-> Execution anomaly: Received Status Code {response.status_code}. Terminating batch.")
            return
    except requests.exceptions.RequestException as e:
        print(f"-> Network request failed: {e}. Terminating pipeline.")
        return

    soup = BeautifulSoup(response.content, "html.parser")
    current_date = datetime.now().strftime("%Y-%m-%d")
    scraped_data = []

    print("Step 2: Parsing Accordion DOM Structures for Service Categories...")

    # Locate all modular accordion components containing the categorized fee schedules
    accordions = soup.find_all("div", class_="accordion-item")

    cards_processed = 0
    for item in accordions:
        # Target the inner container holding the actual tabular pricing data
        content_panel = item.find("div", class_="collapse") or item.find("div", class_="accordion-content")
        if not content_panel:
            continue

        # Select each functional row of services nested inside the accordion panel
        rows = content_panel.find_all("div", class_="row")
        for row in rows:
            # recursive=False ensures we only grab the direct child columns, avoiding nested layout divs
            cols = row.find_all("div", recursive=False)

            # Validation Block: Ensure the row structure supports the required key-value pair
            if len(cols) >= 2:
                service_name = cols[0].text.strip()
                # Aggregate remaining column data to safely capture static prices or dynamic ranges (e.g., "1.650 - 4.200 TL")
                price_text = " ".join([c.text.strip() for c in cols[1:]]).strip()

                # Filter Block: Drop empty elements AND the repeating internal table headers ("Tedavi Adı")
                if service_name and price_text and service_name != "Tedavi Adı":
                    scraped_data.append({
                        "Service": service_name,
                        "Price": price_text
                    })
                    cards_processed += 1

    if not scraped_data:
        print("Pipeline Status: Operations complete. No tabular data matched the extraction criteria.")
        print("Please verify if the target website's DOM layout has been updated.")
        return

    print(f"-> Extraction complete. Captured {cards_processed} dental service items.")

    # Process and map matrix into standardized tabular structures
    df = pd.DataFrame(scraped_data)

    # Establish relative pipeline storage pathways inside project structures
    output_dir = os.path.join("..", "..", "..", "Datas", "Health", "Dentist")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"dentgroup_{current_date}.csv")

    # Save formatted dataset utilizing UTF-8 with BOM to safely preserve local characters
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nPipeline Status: Process Complete. Output saved successfully ({len(df)} entries).")
    print(f"Target Path: {output_file}")


if __name__ == "__main__":
    scrape_dentgroup()