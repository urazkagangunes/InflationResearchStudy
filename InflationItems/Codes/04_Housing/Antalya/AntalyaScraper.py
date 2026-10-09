import hashlib
import asyncio
import random
from camoufox.async_api import AsyncCamoufox
from camoufox_captcha import solve_captcha
import csv
import datetime
import os

base_urls=["https://www.sahibinden.com/kiralik-rezidans/antalya",
"https://www.sahibinden.com/kiralik-mustakil-ev/antalya",
"https://www.sahibinden.com/kiralik-villa/antalya",
"https://www.sahibinden.com/kiralik-ciftlik-evi/antalya",
"https://www.sahibinden.com/kiralik-daire/antalya"]
stuff=["a103713=true","a103713=false"]  #eşyalı / eşyasız
heaterType=["a23=38514&a23=284406&a23=38511&a23=38512&a23=1133903&a23=1263048&a23=38513&a23=1199428&a23=38516&a23=1259599&a23=149999&a23=1199436&a23=1174010&a23=1182365","a23=38517","a23=38515","a23=38518"] #Diğer / Isıtma yok  / Kombi(doğalgaz)  / klima
isInEstate=["a103651=1139073","a103651=1139074"] #site değil / site
ageOfBuilding=["a812=1297863","a812=40602","a812=40603","a812=40604","a812=40605","a812=40606","a812=40607","a812=1297865","a812=43901","a812=43902","a812=43903","a812=43904"]
MAX_PAGES = 50


def combineFilters(arr1, arr2):
    return [f"{a}&{b}" for a in arr1 for b in arr2]
naturalG = combineFilters([heaterType[2]], isInEstate)#doğalgazlı kombiler bunu kullanacak
airConPre = combineFilters(stuff, isInEstate)
airCon = combineFilters(combineFilters(airConPre, ageOfBuilding),[heaterType[3]] )#klimalı daireler bunu kullanacak

month = datetime.datetime.now().month
day = datetime.datetime.now().day
USER_DATA_DIR = "./camoufox_profile"
is_first_run = True
async def get_total_pages(url, filters):
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
        ) as fox:
        page = await fox.new_page()
        success = await solve_captcha(
            page,
            challenge_type="turnstile",
            captcha_type='cloudflare',
            expected_content_selector="tr.searchResultsItem",
            solve_attempts=3,
            solve_click_delay=2.0,
            checkbox_click_attempts=3,
            wait_checkbox_attempts=5
        )
        page = await fox.new_page()
        full_url = f"{url}?pagingOffset=0&sorting=date_asc&{filters}"
        await page.goto(full_url)

        total_elem = await page.query_selector(".result-text-sub-group span")
        if total_elem:
            total_text = await total_elem.inner_text()

            total = int(''.join(filter(str.isdigit, total_text)))
            if total == 0:
                return 0
            return (total // 20) + 1
        return 1

async def scrape_page(page, page_num,BASE_URL,filters):

    offset = (page_num - 1) * 20
    url = f"{BASE_URL}?pagingOffset={offset}&sorting=date_asc&{filters}"

    await page.goto(url, timeout=60000)
    await page.wait_for_selector("tr.searchResultsItem", timeout=15000)


    await page.mouse.move(
        random.randint(100, 800),
        random.randint(100, 600),
        steps=random.randint(10, 20)
    )

    await asyncio.sleep(random.uniform(1, 3))


    listings = await page.query_selector_all("tr.searchResultsItem")
    page_data = []
    for item in listings:
        try:
            title_elem = await item.query_selector(".classifiedTitle")
            title = await title_elem.inner_text() if title_elem else "N/A"
            title = title.strip()

            price_elem = await item.query_selector(".classified-price-container")
            price = await price_elem.inner_text() if price_elem else "N/A"
            price = price.strip()

            data_id_elem = await item.get_attribute("data-id")
            data_id = data_id_elem if data_id_elem else "N/A"
            data_id = data_id.strip()

            location_elem = await item.query_selector(".searchResultsLocationValue")
            location = await location_elem.inner_text() if location_elem else "N/A"
            location = location.strip()
            location = location.replace("\n", "/")

            attr_elems = await item.query_selector_all(".searchResultsAttributeValue")
            room = "N/A"
            for elem in attr_elems:
                text = await elem.inner_text()

                if "+" in text.lower():
                    room = text.strip()
                    break
                if attr_elems.index(elem) == 1:
                    room = text.strip()
                    break
            page_data.append([data_id,title, price, location,room])
        except Exception as e:
            print(f"Error: {e}")
            continue

    return page_data


async def scrape_all_pages(base_url, filters, property_name):
    all_data = []
    total_pages = await get_total_pages(base_url, filters)
    if total_pages == 0:
        print("No pages found")
        return all_data
    batch_size = 50
    for batch_start in range(1, total_pages + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, total_pages)
        print(f"Scraping {property_name} with filters {filters}: pages {batch_start}-{batch_end}")


        async with AsyncCamoufox(
                os="windows",
                humanize=True,
                locale="tr-TR",
                headless=True,
                persistent_context=True,
                i_know_what_im_doing=True,
                config={'forceScopeAccess': True},
                disable_coop=True,
                user_data_dir=USER_DATA_DIR,
                geoip=True,
        ) as fox:
            page = await fox.new_page()
            success = await solve_captcha(
                page,
                challenge_type="turnstile",
                captcha_type='cloudflare',
                expected_content_selector="tr.searchResultsItem",
                solve_attempts=3,
                solve_click_delay=2.0,
                checkbox_click_attempts=3,
                wait_checkbox_attempts=5
            )

            for page_num in range(batch_start, batch_end + 1):
                data = await scrape_page(page, page_num, base_url, filters)
                if not data:
                    break
                all_data.extend(data)
                await asyncio.sleep(random.uniform(3, 8))


        await asyncio.sleep(random.uniform(15, 30))



    filter_string = filters
    hash_object = hashlib.md5(filter_string.encode())
    filters_hash = hash_object.hexdigest()[:8]
    filename = f"{property_name}_{filters_hash}.csv"
    combined_filename = f"AntalyaRent{month}-{day}.csv"
    header = ["Id", "Title", "Price", "Location", "Rooms"]
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(all_data)
    print(f"Saved {len(all_data)} rows to {filename}")
    file_exists = os.path.isfile(combined_filename)
    write_header = not file_exists or os.path.getsize(combined_filename) == 0
    with open(combined_filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerows(all_data)


async def main():

    for i in range(4):
       await scrape_all_pages(base_urls[i], "", ["rezidans", "mustakil-ev", "villa", "ciftlik"][i])

    # 2. Apartments with basic heating filters
    for heater in heaterType[:2]:  # "Diğer" and "Isıtma yok"
        await scrape_all_pages(base_urls[4], heater, "daire")

    # 3. Apartments with natural gas (kombi) + site status
    for filter_str in naturalG:
        await scrape_all_pages(base_urls[4], filter_str, "daire_dogalgaz")

    # 4. Apartments with air conditioning + all other filters
    for filter_str in airCon:
        await scrape_all_pages(base_urls[4], filter_str, "daire_klima")





if __name__ == "__main__":
    asyncio.run(main())
