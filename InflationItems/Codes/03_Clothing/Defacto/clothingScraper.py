import asyncio
import random
import tempfile
import camoufox
from camoufox.async_api import AsyncCamoufox
import csv
import datetime
import os



USER_DATA_DIR = tempfile.mkdtemp();
month = datetime.date.today().month
day = datetime.date.today().day

base_urls = ["https://www.defacto.com.tr/app/yeni-sezon-secim-kadin","https://www.defacto.com.tr/app/yeni-sezon-secim-erkek","https://www.defacto.com.tr/app/yeni-sezon-secim-cocuk-bebek"]

async def getProductNum(url):
    async with AsyncCamoufox(humanize=True,
            locale="tr-TR",
            headless=True,
            persistent_context=True,
            i_know_what_im_doing=True,
            config={'forceScopeAccess': True},
            disable_coop=True,
            user_data_dir=USER_DATA_DIR,
            args=[f"--remote-debugging-port={random.randint(9222, 9322)}"],
            geoip=True,) as camoufo:
         page = await camoufo.new_page();
         await page.goto(url, timeout=60000)

         product_amount_elem = await page.query_selector("#totalCount")
         product_amount = await product_amount_elem.get_attribute("value")
         product_amount = int(product_amount) if product_amount else 0
         return product_amount
         await page.close()

async def scrape(url):
     product_amount = await getProductNum(url)
     async with AsyncCamoufox(humanize=True,
            locale="tr-TR",
            headless=True,
            persistent_context=True,
            i_know_what_im_doing=True,
            config={'forceScopeAccess': True},
            disable_coop=True,
            user_data_dir=USER_DATA_DIR,
            args=[f"--remote-debugging-port={random.randint(9222, 9322)}"],
            geoip=True,) as camoufo:
         page = await camoufo.new_page();
         await page.goto(url, timeout=60000)
         await page.wait_for_selector(".product-card__details", timeout=15000)
         print(f"Scraping page: {url} total  items: {product_amount}")
         page_data = []

         if product_amount == 0:
             return page_data
         last_height = 0;
         first_index = 0;
         last_index = 25;
         while len(page_data) <= int(product_amount):
             item_elems = await page.query_selector_all(".product-card__details")
             currentItem = len(item_elems)
             try:
                 for item_elem in item_elems[first_index:last_index]:
                     product_title_elem = await item_elem.query_selector(".product-card__title--name");
                     product_title = await product_title_elem.query_selector("span")
                     product_title = await product_title.inner_text() if product_title else "N/A"
                     product_title = product_title.strip()

                     price_elem = await item_elem.query_selector("div.first-line")
                     price_elem = await price_elem.query_selector("div")
                     price = await price_elem.inner_text() if price_elem else 0;
                     price = price.strip()
                     price = price.replace("TL", "") if price else 0;
                     price = float(price) if price else 0;

                     page_data.append([product_title, price])
             except Exception as e:
                 print(e)
                 continue

             a = 0
             while(len(item_elems) < last_index):
                 item_elems = await page.query_selector_all(".product-card__details")
                 await page.evaluate("window.scrollBy(0,1200)")
                 await asyncio.sleep(random.randint(1, 3))
                 print(f"Scrolling down , product amount:{len(page_data)}")
                 a=a+1
                 if a >= 6 and a <= 18:
                     await page.evaluate("window.scrollBy(0,-1400)")
                     await asyncio.sleep(random.randint(1, 3))
                 if a > 18:
                     break
                 if len(item_elems) >= product_amount:
                     break
             if a > 18:
                 break

             first_index = last_index -1;
             last_index = last_index + 24;

     return page_data

async def csvSaver(base_url):
    all_data = await scrape(base_url)
    header = ["Product Title","Price (TL)"]
    filename = f"Cloths{str(month)}-{str(day)}.csv"
    file_exists = os.path.isfile(filename)
    write_header = not file_exists or os.path.getsize(filename) == 0
    with open(filename, 'a', newline='',encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(header)
        writer.writerows(all_data)
    print("Finished index:"+str(len(all_data)))
    await asyncio.sleep(random.randint(1,3))

async def main():
    for a in base_urls:
        await csvSaver(a)


if __name__ == "__main__":
    asyncio.run(main())
