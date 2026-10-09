from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import csv
from datetime import date

options = webdriver.EdgeOptions()
options.add_argument("--headless=new")    
options.add_argument("--disable-gpu")
options.add_argument("window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...")

driver = webdriver.Edge(
    service=EdgeService(EdgeChromiumDriverManager().install()),
    options=options
)

URL = "https://www.ido.com.tr/tr/tarife/ucret-tarifesi"
print("Loading page...")
driver.get(URL)
try:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "table"))
    )
    print("Tables loaded.")
except:
    print("Tables not found – page may have changed or is slow.")
    driver.quit()
    exit()

soup = BeautifulSoup(driver.page_source, "html.parser")
driver.quit()

tables = soup.find_all("table")
print(f"Found {len(tables)} tables.")

all_rows = []
for table in tables:
    for tr in table.find_all("tr"):
        cols = tr.find_all(["td"])
        if len(cols) >= 2:
            col1 = " ".join(cols[0].get_text(strip=True).split())
            col2 = " ".join(cols[1].get_text(strip=True).split())
            col2 = col2.replace(" ", "")
            col2 = col2.replace(".", "")
            col2 = col2.replace(",", ".")
            col2 = col2.replace("TL", "")
            try:
                col2 = float(col2)
            except Exception as e:
                col2 = 0
            all_rows.append([col1, col2])

if all_rows:
    filename = f"Datas\ido_fares_{date.today().month}-{date.today().day}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(all_rows)
    print(f"Saved {len(all_rows)} rows to {filename}")
else:
    print("No rows extracted.")
