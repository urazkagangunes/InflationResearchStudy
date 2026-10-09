"""
Data Collection Engine - Physical Therapy Price Indexation
Description: Automated pipeline designed to dynamically map, paginate, and extract
             localized price datasets from private physical therapy provider registries,
             filtering by engagement criteria (user reviews).
"""

import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def scrape_physical_therapy():
    """
    Executes full lifecycle pagination scraping to retrieve physical therapy fees.
    Identifies bounds dynamically via initial DOM traversal, drops low-engagement profiles,
    and structures data into a normalized, two-column layout.
    """
    base_url = "https://ozelfizyoterapist.net/lokasyonlar/istanbul-fizyoterapist-fizik-tedavi"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    scraped_data = []
    page = 1
    max_pages = 35  # Operational default fallback ceiling

    print("Initializing Data Collection Pipeline...")
    print("Step 1: Evaluating Pagination Bounds via Target DOM Node Entry...")

    try:
        init_res = requests.get(f"{base_url}?page=1", headers=headers, timeout=15)
        if init_res.status_code == 200:
            init_soup = BeautifulSoup(init_res.content, "html.parser")

            # Locate the absolute right pagination boundary terminal button (»)
            last_page_icon = init_soup.find("i", class_="fa-angle-double-right")
            if last_page_icon:
                # Extract link references from parent anchor block to calculate upper terminal index
                last_page_link = last_page_icon.find_parent("a", href=True)
                if last_page_link and "?page=" in last_page_link["href"]:
                    max_pages = int(last_page_link["href"].split("?page=")[-1])
                    print(f"-> Target Boundary Successfully Identified. Terminal Index: {max_pages}")
            else:
                print("-> Warning: Terminal anchor icon not resolved. Utilizing fallback range index.")
    except Exception as e:
        print(f"-> Initialization failure during boundary discovery: {e}. Reverting to standard range bounds.")

    print("\nStep 2: Commencing Continuous Extraction Loop...")

    # Iterate exactly through the dynamically calculated range boundaries
    while page <= max_pages:
        url = f"{base_url}?page={page}"
        print(f"Processing Page {page}/{max_pages}: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"-> Execution anomaly: Received Status Code {response.status_code}. Terminating batch.")
                break
        except requests.exceptions.RequestException as e:
            print(f"-> Network request failed: {e}. Skipping block framework.")
            break

        soup = BeautifulSoup(response.content, "html.parser")

        # Isolate practitioner profile containers specifically, avoiding structural footers or review streams
        therapist_cards = [
            div for div in soup.find_all("div", class_="card")
            if "mb-3" in div.get("class", []) and "rounded" in div.get("class", [])
        ]

        cards_processed = 0
        for card in therapist_cards:
            # Filter Block: Extract and evaluate engagement metrics (Total Reviews)
            review_tag = card.find("span", class_="float-start")
            if not review_tag or "Görüş" not in review_tag.text:
                continue  # Exclude listing due to lack of standard feedback properties

            review_text = review_tag.text.strip()
            if "0 Görüş" in review_text:
                continue  # Exclude listing to maintain dataset relevancy bounds

            # Extraction Block: Parse targeting attributes
            price_tag = card.find("span", class_="fwb")
            price_int = None
            if price_tag:
                raw_price = price_tag.text.strip()
                # Isolate the base number from suffixes like "/ Seans"
                base_price_str = raw_price.split('/')[0]
                # Regex mapping: Strip all non-digit characters (removes '₺', dots, and spaces)
                numeric_str = re.sub(r'\D', '', base_price_str)
                if numeric_str:
                    price_int = int(numeric_str)

            location_ul = card.find("ul", class_="list-unstyled")
            place_text = None
            if location_ul:
                # Standardize location string matrices to remove extraneous formatting layouts
                place_text = location_ul.text.replace("\n", "").strip()
                place_text = " ".join(place_text.split())
                # Truncate trailing availability counts (e.g., "+22 daha fazla")
                if "+" in place_text:
                    place_text = place_text.split("+")[0].strip()

            # Normalization Block: Append valid metrics matching schema constraints
            if place_text and price_int is not None:
                scraped_data.append({
                    "Place": place_text,
                    "Price": price_int
                })
                cards_processed += 1

        print(f"-> Page {page} finalized. Captured Records: {cards_processed}")
        page += 1

    if not scraped_data:
        print("Pipeline Status: Operations complete. Resulting matrix contains empty dimensions.")
        return

    # Process and map matrix into standardized tabular structures
    df = pd.DataFrame(scraped_data)

    # Establish relative pipeline storage pathways inside project structures
    current_date = datetime.now().strftime("%Y-%m-%d")
    output_dir = os.path.join("..", "..", "..", "Datas", "Health", "Physical_Therapy")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"physical_therapy_{current_date}.csv")

    # Save formatted dataset utilizing UTF-8 with BOM to safely preserve local characters (Turkish letters)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nPipeline Status: Process Complete. Output saved successfully ({len(df)} entries).")
    print(f"Target Path: {output_file}")

if __name__ == "__main__":
    scrape_physical_therapy()