import os
import datetime
import csv

import camoufox
import time
import asyncio
import random
import tempfile
import camoufox.async_api as camoufo
from camoufox import AsyncCamoufox

month = datetime.datetime.today().month
day = datetime.datetime.today().day
USER_DATA_DIR = tempfile.mkdtemp()

BASE_URL = "https://www.afeksyapimarket.com"
items_per_page = 80
categories = ["/Beyaz-Esya","/Mutfak","/Banyo","/Mobilya","/Bahce","/Hirdavat","/Boya","/Elektrikli-El-Aleti","/Aydinlatma-ve-Elektrik","/Dekorasyon-ve-Ev-Gereci","/Isitma-ve-Sogutma","/Seramik-ve-Insaat","/Super-Market","/Oto","/Spor-ve-Outdoor","/Parke-ve-Ahsap","/Evcil-Hayvan","/Kirtasiye"]

async def get_page_num(category_url):
    async with AsyncCamoufox(os="windows",
                             humanize=True,
                             locale="tr-TR",
                             headless=True,
                             persistent_context=True,
                             i_know_what_im_doing=True,
                             config={'forceScopeAccess': True},
                             disable_coop=True,
                             user_data_dir=USER_DATA_DIR,
                             geoip=True,
                             args=[f"--remote-debugging-port={random.randint(9325, 9422)}"],
                             ) as camoufo:
        page = await camoufo.new_page()
        current_url = f"{BASE_URL}{category_url}"
        await page.goto(current_url,timeout=60000)
        await asyncio.sleep(2)
        items_elem = await page.query_selector("div.mobilUrunAdet")
        items = await items_elem.inner_text() if items_elem else 0
        items = items.split(" ") if items else 0
        items = items[1] if items else 0
        return int(items)
async def scrape_page(category_url):
    num_pages = await get_page_num(category_url)
    product_data = []
    if num_pages == 0:
        print("No pages found")
        return product_data
    if num_pages%items_per_page==0:
        num_pages = num_pages/items_per_page
    elif num_pages%items_per_page!=0:
        num_pages = num_pages//items_per_page +1
    print("Total pages: ",num_pages)
    async with AsyncCamoufox(os="windows",
                             humanize=True,
                             locale="tr-TR",
                             headless=True,
                             persistent_context=True,
                             i_know_what_im_doing=True,
                             config={'forceScopeAccess': True},
                             disable_coop=True,
                             user_data_dir=USER_DATA_DIR,
                             geoip=True,
                             args=[f"--remote-debugging-port={random.randint(9325, 9422)}"],) as camoufo:
        page = await camoufo.new_page()

        for page_num in range(num_pages):
            current_url = f"{BASE_URL}{category_url}?sayfa={str(page_num+1)}"
            await page.goto(current_url, timeout=60000)
            print("Scraping page: "+str(current_url))
            await asyncio.sleep(2)
            product_elem = await page.query_selector_all("div.productDetail.videoAutoPlay")

            for product_detail in product_elem:


                product_title_elem = await product_detail.query_selector("a")
                product_title = await product_title_elem.inner_text() if product_title_elem else ""
                product_title = product_title.strip()


                product_price_elem = await product_detail.query_selector("span.discountPriceSpan")
                product_price = await product_price_elem.inner_text() if product_price_elem else 0
                product_price = product_price.strip() if product_price else ""
                product_price = product_price.replace(".","")
                product_price = product_price.replace(",",".")
                product_price = product_price.replace("₺", "")
                product_price = float(product_price)

                product_data.append([product_title, product_price])
            await asyncio.sleep(3)
    return product_data

async def csvAppender(category_url):
    all_data = await scrape_page(category_url)
    headers = ["Product Title", "Price(TL)"]
    filename = f"Datas\\ConstructionProduct{month}-{day}.csv"
    file_exists = os.path.isfile(filename)
    writer_header = not file_exists or os.path.getsize(filename)==0
    with open(filename, "a", newline="",encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if writer_header:
            writer.writerow(headers)
        writer.writerows(all_data)
        print(f"Saved {str(len(all_data))} rows")
    await asyncio.sleep(1)

async def main():
    for urls in categories:
        await csvAppender(urls)
        print("Finished category: "+str(urls) + " Finished index: " + str(categories.index(urls)))

if __name__ == "__main__":
    asyncio.run(main())
