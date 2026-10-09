import csv, os, random, time
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions
import pandas as pd

# --- PATHS ---
BASE_DIR = r"C:\Users\SEDA\OneDrive - ozyegin.edu.tr\Desktop\ai201\sahibinden"
CHROME_BINARY = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = os.path.join(BASE_DIR, "RealUserSession")
DATA_DIR = os.path.join(BASE_DIR, "Datas")

os.makedirs(DATA_DIR, exist_ok=True)

def now_str(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extract_listings(page):
    listings = []
    table = page.ele('#searchResultsTable')
    if not table: return []
    
    rows = table.ele('tag:tbody').eles('tag:tr')
    for row in rows:
        if 'nativeAd' in row.attrs.get('class', '') or 'not-last-child' in row.attrs.get('class', ''):
            continue
        try:
            cells = row.eles('tag:td')
            if len(cells) < 6: continue

            # --- INDEX MAPPING ---
            district = " ".join((cells[1].text or cells[1].raw_text).split())
            rooms = " ".join((cells[3].text or cells[3].raw_text).split())
            price = " ".join((cells[4].text or cells[4].raw_text).split())

            if any(char.isdigit() for char in price):
                listings.append({
                    "District": district,
                    "Rooms": rooms,
                    "Price": price,
                    "Scraped_Date": now_str()
                })
        except: continue
    return listings

def scrape_city(page, city, base_urls):
    all_data = []
    for url in base_urls:
        page.get(f"{url}&pagingSize=50")
        
        for p_idx in range(1, 70):
            print(f"[{city}] Page {p_idx}")
            page.wait.ele_displayed('#searchResultsTable', timeout=15)
            page.scroll.to_bottom()
            
            new_batch = extract_listings(page)
            if not new_batch: break
            
            all_data.extend(new_batch)
            print(f"  -> Found {len(new_batch)} (Total: {len(all_data)})")
            
            next_btn = page.ele('xpath://a[@title="Sonraki"]')
            if next_btn:
                next_btn.click()
                time.sleep(random.uniform(3, 5))
            else: break

    if all_data:
        df = pd.DataFrame(all_data).drop_duplicates(subset=['District', 'Rooms', 'Price'])
        folder = os.path.join(DATA_DIR, {"maras":"Maras", "antep":"Antep", "kilis":"Kilis"}.get(city, city.capitalize()))
        os.makedirs(folder, exist_ok=True)
        out_path = os.path.join(folder, f"{city}_{datetime.now().strftime('%Y-%m-%d')}.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return len(df)
    return 0

def main():
    # Browser Setup
    co = ChromiumOptions().set_browser_path(CHROME_BINARY).set_user_data_path(PROFILE_DIR)
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--start-maximized')
    
    page = ChromiumPage(co)
    report = {}
    try:
        cities = {
            "maras": ["https://www.sahibinden.com/kiralik/kahramanmaras?"],
            "kilis": ["https://www.sahibinden.com/kiralik/kilis?"],
            "antep": [
    "https://www.sahibinden.com/kiralik/gaziantep?price_max=12000",
    "https://www.sahibinden.com/kiralik/gaziantep?price_min=12001&price_max=20000",
    "https://www.sahibinden.com/kiralik/gaziantep?price_min=20001"
]
        }
        for city, urls in cities.items():
            count = scrape_city(page, city, urls)
            report[city] = count
            
        print("\n" + "="*30)
        print("SCRAPING SUMMARY")
        print("="*30)
        for city, count in report.items():
            print(f"{city.capitalize()}: {count} listings saved.")
        print("="*30)
        
    finally: page.quit()

if __name__ == "__main__": main()
