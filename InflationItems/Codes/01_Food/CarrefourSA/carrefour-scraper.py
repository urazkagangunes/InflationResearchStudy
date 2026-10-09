from bs4 import BeautifulSoup
from datetime import datetime
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
# from webdriver_manager.chrome import ChromeDriverManager
import os
import undetected_chromedriver as uc

market_url = "https://www.carrefoursa.com"
categories = [
    "/meyve-sebze/c/1014",
    "/et-tavuk-balik/c/1044",
    "/sut-urunleri/c/1310",
    "/kahvaltilik-urunler/c/1363",
    "/temel-gida/c/1110",
    "/atistirmalik/c/1493",
    "/hazir-yemek-donuk-urunler/c/1064",
    "/firin/c/1275",
    "/icecekler/c/1409",
    "/saglikli-yasam/c/1938",
    "/dondurma/c/1260",
    "/bebek-urunleri/c/1846",
    "/pet-shop/c/2054",
    "/temizlik-urunleri/c/1556",
    "/kisisel-bakim/c/1674",
    "/elektronik/c/2286"
]

def scroll_to_bottom(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            break

        last_height = new_height

options = uc.ChromeOptions()
driver = uc.Chrome(options=options)

data_dir = "InflationItems/Datas/Markets/CarrefourSA"
os.makedirs(data_dir, exist_ok=True)
date = datetime.now().strftime("%Y-%m-%d")
filename = f"InflationItems/Datas/Markets/CarrefourSA/carrefourSA_{date}.csv"

with open(filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["product_name", "price (TL)"])

for cat in categories:
    driver.get(market_url + cat)
    time.sleep(5)

    scroll_to_bottom(driver)

    # collect all links to pages with full list of products
    links = driver.find_elements(By.XPATH, "//span[@class='cat-title']/a")
    category_links = [link.get_attribute("href") for link in links]
    print(f"count categories for {cat}:", len(category_links))

    for url in category_links:
        driver.get(url)
        time.sleep(5)

        scroll_to_bottom(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        cards = soup.find_all("div", class_="product-card") # collect all cards to parse
        # print("cards count:", len(cards))

        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for card in cards:
                name_tag = card.find("h3", class_="item-name")
                name = name_tag.text.strip() if name_tag else None

                price = None
                price_tag = card.find("span", class_="item-price")
                if price_tag and price_tag.has_attr("content"):
                    raw_content = price_tag["content"].strip()
                    if raw_content:
                        try:
                            raw_price = float(raw_content)
                            price = round(raw_price, 2)
                        except ValueError:
                            price = None

                if name and price:
                    writer.writerow([name, price])

driver.quit()

print("done.")
