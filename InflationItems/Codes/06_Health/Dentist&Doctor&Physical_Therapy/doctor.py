"""
Data Collection Engine - Doctor Consultation Price Indexation
Description: Automated pipeline designed to extract official private
             examination fees (Özel Muayene) from state/university hospital
             registries. Converts string currency to normalized integers.
"""

import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime


def scrape_university_doctor_fees():
    """
    Connects to the hospital's patient guide registry, isolates the pricing tables,
    cleans the currency formatting into pure integers, and saves the output.
    """
    url = "https://hastane.adu.edu.tr/hasta-rehberi.asp?id=6"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    scraped_data = []

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
    print("Step 2: Parsing DOM Structures for Medical Branches...")

    # The prices are generally held in standard HTML table rows
    rows = soup.find_all("tr")
    processed_count = 0

    for row in rows:
        cols = row.find_all(["td", "th"])
        # Ensure the row has a pair: Service Name and Price
        if len(cols) >= 2:
            service_name = cols[0].text.replace("\n", "").strip()
            raw_price = cols[1].text.replace("\n", "").strip()

            # Filter Block: Verify this is a data row containing currency ("TL")
            if "TL" in raw_price.upper():
                # Extraction Block: Clean string to isolate base integer
                # Split at the comma to drop the decimal "kuruş" values (e.g., "712,00 TL" -> "712")
                base_price_str = raw_price.split(',')[0]
                # Strip all remaining non-numeric characters
                numeric_str = re.sub(r'\D', '', base_price_str)

                if numeric_str and service_name:
                    scraped_data.append({
                        "Service": service_name,
                        "Price": int(numeric_str)
                    })
                    processed_count += 1

    if not scraped_data:
        print("Pipeline Status: Operations complete. No tabular data matched the extraction criteria.")
        return

    print(f"-> Extraction complete. Captured {processed_count} medical branches.")

    # Process and map matrix into standardized tabular structures
    df = pd.DataFrame(scraped_data)

    # Establish relative pipeline storage pathways inside project structures
    current_date = datetime.now().strftime("%Y-%m-%d")
    output_dir = os.path.join("..", "..", "..", "Datas", "Health", "Doctor")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"adu_hospital_{current_date}.csv")

    # Save formatted dataset utilizing UTF-8 with BOM to safely preserve local characters
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nPipeline Status: Process Complete. Output saved successfully ({len(df)} entries).")
    print(f"Target Path: {output_file}")


if __name__ == "__main__":
    scrape_university_doctor_fees()