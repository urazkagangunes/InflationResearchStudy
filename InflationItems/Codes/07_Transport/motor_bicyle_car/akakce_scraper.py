from curl_cffi import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import os
import re
import json

class AkakceScraper:
    def __init__(self):
        self.categories = {
            "Motosiklet": "https://www.akakce.com/motosiklet.html",
            "Bisiklet": "https://www.akakce.com/bisiklet.html"
        }
        self.data_current = []
        self.data_history = []
        
    def fetch_page(self, url):
        try:
            # Impersonate Chrome to bypass Cloudflare
            response = requests.get(url, impersonate="chrome110")
            if response.status_code == 200:
                return response.text
            else:
                print(f"Failed to fetch {url}, status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def scrape_category(self, category_name, base_url, max_pages=2):
        for page_num in range(1, max_pages + 1):
            url = f"{base_url}?p={page_num}" if page_num > 1 else base_url
            print(f"Scraping Akakce Category - {category_name} Page {page_num}: {url}")
            
            html = self.fetch_page(url)
            if not html:
                break
                
            soup = BeautifulSoup(html, 'html.parser')
            products = soup.select("ul.pl_v9 > li")
            if not products:
                # alternative check if they changed classes
                products = soup.select("ul#p_lst > li")
                
            if not products:
                print("No products found. Layout might have changed or end of pagination.")
                break
                
            for product in products:
                try:
                    a_tag = product.find("a")
                    if not a_tag or not a_tag.has_attr("href"):
                        continue
                    
                    product_url = "https://www.akakce.com" + a_tag['href']
                    
                    # title
                    title_tag = product.find("h3")
                    title = title_tag.text.strip() if title_tag else ""
                    
                    # price
                    price_tag = product.select_one(".pt_v9")
                    if not price_tag:
                        price_tag = product.find("span", class_="pt_v9")
                    price = price_tag.text.strip() if price_tag else ""
                    
                    # Append current price
                    self.data_current.append({
                        "Date_Scraped": datetime.now().strftime("%Y-%m-%d"),
                        "Source": "akakce.com",
                        "Category": category_name,
                        "Title": title,
                        "Price": price,
                        "URL": product_url
                    })
                    
                    # Optional: Scrape product page for 1-month price history
                    self.scrape_product_history(product_url, title, category_name)
                    time.sleep(1) # Be polite
                    
                except Exception as e:
                    print(f"Error parsing product item: {e}")

    def scrape_product_history(self, product_url, title, category_name):
        # Visit the product page to see if we can find the history chart data
        html = self.fetch_page(product_url)
        if not html:
            return
            
        # The history data is usually in a javascript block
        # e.g., 'var pd_v8 = [...data...]' or something related to highcharts
        # We will attempt a regex search to extract JSON-like structures that represent prices
        
        # Example pattern: look for an array of timestamp-price pairs or similar. 
        # Since exact structure needs reverse-engineering, we will try to find generic price graph data.
        # Often it's within a JSON payload in script tags.
        
        # For this example, we capture if we find a specific recognizable pattern.
        # Because we can't reliably guess without seeing the actual page source, 
        # we will leave a stub for the 1-month history that users can adapt.
        
        try:
            # Let's search for some typical keywords
            match = re.search(r'var\s+chartData\s*=\s*(\[.*?\]);', html, re.DOTALL)
            if match:
                # If we hypothetically find chart data
                # We would parse the JSON and filter for the last 30 days
                pass 
                
            # As a placeholder, we just log that we visited it
            # In a real deep scraping scenario, one would analyze the exact JS object used by Akakce's chart
        except Exception as e:
            pass

    def run(self, max_pages=1):
        for category, url in self.categories.items():
            self.scrape_category(category, url, max_pages=max_pages)
            
    def export_csv(self):
        if self.data_current:
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"akakce_guncel_{today}.csv"
            df = pd.DataFrame(self.data_current)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"Data successfully exported to {filename} ({len(self.data_current)} records)")
        else:
            print("No current data to export for Akakce.")

if __name__ == "__main__":
    print("Starting Akakce.com Scraper...")
    scraper = AkakceScraper()
    scraper.run(max_pages=1) # Limit to 1 page for quick test
    scraper.export_csv()
