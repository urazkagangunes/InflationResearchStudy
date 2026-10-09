import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time


def scrape_sahibinden():
    cities = ['hatay', 'osmaniye', 'adiyaman']
    all_data = []

    # These headers trick the server into thinking this is a real Chrome browser, not a Python script
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.sahibinden.com/'
    }

    for city in cities:
        url = f"https://www.sahibinden.com/kiralik-daire/{city}"

        # A 3-second delay prevents the firewall from detecting unnatural speed
        time.sleep(3)

        try:
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                print(f"Failed to load {city}. Status code: {response.status_code}. You may be blocked.")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # Sahibinden stores each housing ad in a table row with this specific class
            listings = soup.find_all('tr', class_='searchResultsItem')

            for item in listings:
                try:
                    # Extracts and cleans the text (e.g., converts multi-line "Antakya \n Odabaşı" to "Antakya / Odabaşı")
                    location_raw = item.find('td', class_='searchResultsLocationValue').text.strip()
                    district = ' / '.join([line.strip() for line in location_raw.splitlines() if line.strip()])

                    # The first attribute value is always the room count
                    rooms = item.find_all('td', class_='searchResultsAttributeValue')[0].text.strip()

                    # Extracts the price and removes extra whitespace
                    price = item.find('td', class_='searchResultsPriceValue').text.strip()

                    all_data.append({
                        'District': f"{city.capitalize()} - {district}",
                        'Rooms': rooms,
                        'Price': price
                    })
                except (AttributeError, IndexError):
                    # Silently skips hidden ads, promoted banners, or empty rows
                    continue

        except Exception as e:
            print(f"Error scraping {city}: {e}")

    # Convert the scraped list into a Pandas DataFrame
    df = pd.DataFrame(all_data)

    # Setup the file path to match the team's repository structure
    today_date = datetime.now().strftime("%Y-%m-%d")
    save_dir = "Datas/HousesRent/Hatay_Osmaniye_Adiyaman"

    os.makedirs(save_dir, exist_ok=True)
    filename = f"{save_dir}/{today_date}.csv"

    # Save as CSV without the index numbers, using utf-8-sig to preserve Turkish characters (ş, ı, ğ)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"Data successfully saved to {filename}")


if __name__ == "__main__":
    scrape_sahibinden()