import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import os

class ArabamScraper:
    def __init__(self, base_url="https://www.arabam.com/ikinci-el/otomobil"):
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        self.data = []
        
    def scrape_page(self, page_num):
        url = f"{self.base_url}?page={page_num}"
        print(f"Scraping Arabam.com - Page {page_num}: {url}")
        
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            print(f"Failed to fetch page {page_num}, status code: {response.status_code}")
            return False
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # arabam.com listings usually have a table with class 'listing-list-item' or tr with class 'listing-list-item'
        # we will look for 'tr' tags inside tbody that have an id or specific class.
        listings = soup.find_all("tr", class_="listing-list-item")
        
        if not listings:
            # Let's try alternative selectors if layout changed. Usually they use specific tr/div classes.
            listings = soup.select("tr.listing-list-item, div.listing-list-item")
            
        if not listings:
            print("No listings found on this page. Reached the end or structure changed.")
            return False
            
        for item in listings:
            try:
                # Basic extraction: title, model, year, km, price
                # Note: precise CSS selectors depend on the current live structure of arabam.com
                # We use generic text finding combined with typical classes.
                
                title_elem = item.find("td", class_="listing-modelname")
                if not title_elem:
                    title_elem = item.select_one(".modelName")
                title = title_elem.text.strip() if title_elem else "Unknown Title"
                
                price_elem = item.find("td", class_="price")
                if not price_elem:
                    price_elem = item.select_one(".price")
                price = price_elem.text.strip() if price_elem else ""
                
                year_elem = item.select_one("td.listing-text a") # Sometimes year is here
                # Let's just collect all td text and map them if specific classes fail
                tds = item.find_all("td")
                
                # In arabam standard view:
                # td[1] -> model, td[2] -> title, td[3] -> year, td[4] -> km, td[5] -> color, td[6] -> price, td[7] -> date, td[8] -> location
                
                model = ""
                year = ""
                km = ""
                
                if len(tds) >= 8:
                    model = tds[1].text.strip()
                    title = tds[2].text.strip()
                    year = tds[3].text.strip()
                    km = tds[4].text.strip()
                    price = tds[6].text.strip()
                
                link_elem = item.find("a")
                link = "https://www.arabam.com" + link_elem['href'] if link_elem and link_elem.has_attr('href') else ""
                
                self.data.append({
                    "Date_Scraped": datetime.now().strftime("%Y-%m-%d"),
                    "Source": "arabam.com",
                    "Category": "Otomobil",
                    "Title": title,
                    "Model": model,
                    "Year": year,
                    "KM": km,
                    "Price": price,
                    "URL": link
                })
            except Exception as e:
                print(f"Error parsing an item: {e}")
                
        return True
        
    def run(self, max_pages=5):
        """Runs the scraper for a defined number of pages"""
        for page in range(1, max_pages + 1):
            success = self.scrape_page(page)
            if not success:
                break
            time.sleep(1) # Be polite
            
    def export_csv(self, filename=None):
        if not self.data:
            print("No data to export.")
            return
            
        if filename is None:
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"arabam_verileri_{today}.csv"
            
        df = pd.DataFrame(self.data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Data successfully exported to {filename} ({len(self.data)} records)")

if __name__ == "__main__":
    print("Starting Arabam.com Scraper...")
    scraper = ArabamScraper()
    scraper.run(max_pages=2) # Test with 2 pages
    scraper.export_csv()
