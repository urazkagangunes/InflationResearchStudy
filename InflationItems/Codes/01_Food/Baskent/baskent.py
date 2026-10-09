import requests
from bs4 import BeautifulSoup
import csv
import os
from datetime import datetime


def scrape():
    url = "https://www.baskentmarket.com.tr/kategori/tum-urunler"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    product_count = 0
    index = 2
    previous_products = None
    all_data = []

    print(f"--- Scraping started at {datetime.now()} ---")

    # First request
    answer = requests.get(url, headers=headers)

    while answer.status_code == 200:
        soup = BeautifulSoup(answer.content, "html.parser")
        products = soup.find_all("div", class_="showcase")

        if products == previous_products or not products:
            break

        previous_products = products

        for product in products:
            name_tag = product.find("div", class_="showcase-title")
            price_tag = product.find("div", class_="showcase-price")

            if name_tag and price_tag:
                clean_name = name_tag.text.strip()
                clean_price = " ".join(price_tag.text.split())
                all_data.append([ clean_name, clean_price])
                product_count+=1

        url = f"https://www.baskentmarket.com.tr/kategori/tum-urunler?tp={index}"
        answer = requests.get(url, headers=headers)
        index += 1

    # Save to CSV file - Updated for the new directory structure
    # Path: InflationResearchStudy/InflationItems/Datas/Markets/Baskent/
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    folder_path = os.path.join(base_dir, "Datas", "Markets", "Baskent")

    today_str = datetime.now().strftime("%Y-%m-%d")
    file_name = f"baskent_{today_str}.csv"
    file_path = os.path.join(folder_path, file_name)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)

    with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow([ 'Product Name', 'Price'])
        writer.writerows(all_data)

    print(f"Success: {product_count} items saved to: {file_path}")

if __name__ == "__main__":
    scrape()