import csv
import logging
import os
import random
import re
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import config

logger = logging.getLogger(__name__)

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={config.SELENIUM_PROFILE_DIR}")
    # Sürücü çakışmalarını önlemek için otomatik versiyon seçimi
    try:
        driver = uc.Chrome(options=options, version_main=145)
    except Exception as e:
        logger.warning(f"Sürüm 145 ile başlatılamadı, otomatik sürüm deneniyor... Hata: {e}")
        driver = uc.Chrome(options=options)
        
    return driver

def _extract_total_listings(soup: BeautifulSoup) -> int | None:
    res_elem = soup.select_one(".result-text")
    text = res_elem.get_text(strip=True) if res_elem else ""
    if not text:
        for tag in soup.find_all(string=lambda t: t and "ilan" in t.lower()):
            if tag.parent.name not in ["script", "style"]:
                text = tag.strip()
                break
    
    clean_text = text.replace(".", "").replace(",", "")
    match = re.search(r"(\d+)\s*ilan", clean_text, re.IGNORECASE)
    return int(match.group(1)) if match else None

def _parse_listings(soup: BeautifulSoup, rooms_idx: int | None) -> list[dict]:
    records = []
    for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
        try:
            price = row.select_one(".searchResultsPriceValue").text.strip()
            loc_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"
            attrs = row.select(".searchResultsAttributeValue")
            rooms = attrs[rooms_idx].text.strip() if (rooms_idx is not None and len(attrs) > rooms_idx) else "N/A"
            records.append({"District": district, "Rooms": rooms, "Price": price})
        except: continue
    return records

def _wait_for_listings(driver: uc.Chrome) -> BeautifulSoup:
    time.sleep(config.PAGE_LOAD_DELAY)
    if "captcha" in driver.current_url or "olağandışı" in driver.page_source:
        print("\n⚠️  CAPTCHA Engeli! Lütfen tarayıcıda çözün ve ENTER'a basın...")
        input("Devam etmek için hazır mısın? ")
    return BeautifulSoup(driver.page_source, "html.parser")

def scrape_range(driver, min_price, max_price, done_ranges, save_fn, save_checkpoint_fn, indent, city_url_name, csv_path):
    pad = "  " * indent
    if (min_price, max_price) in done_ranges:
        return 0

    url = f"https://www.sahibinden.com/kiralik-daire/{city_url_name}?price_min={min_price}&price_max={max_price}&pagingSize={config.PAGE_SIZE}"
    driver.get(url)
    soup = _wait_for_listings(driver)
    total = _extract_total_listings(soup)

    # Split Kararı
    if total and total > config.MAX_LISTINGS_PER_QUERY and (max_price - min_price) > config.MIN_BRACKET_WIDTH:
        logger.info(f"{pad}✂️ {total} ilan bulundu, bölünüyor...")
        mid = (min_price + max_price) // 2
        t1 = scrape_range(driver, min_price, mid, done_ranges, save_fn, save_checkpoint_fn, indent+1, city_url_name, csv_path)
        time.sleep(random.uniform(config.BETWEEN_BRACKET_DELAY_MIN, config.BETWEEN_BRACKET_DELAY_MAX))
        t2 = scrape_range(driver, mid+1, max_price, done_ranges, save_fn, save_checkpoint_fn, indent+1, city_url_name, csv_path)
        return t1 + t2

    # Veri Toplama
    records = []
    rooms_idx = 2 # Genelde 2. sütundur ama dinamik de aranabilir
    page = 1
    while True:
        records.extend(_parse_listings(soup, rooms_idx))
        next_btn = soup.find("a", title="Sonraki")
        if next_btn and page < 20:
            driver.get("https://www.sahibinden.com" + next_btn["href"])
            page += 1
            time.sleep(random.uniform(config.PAGE_TURN_DELAY_MIN, config.PAGE_TURN_DELAY_MAX))
            soup = _wait_for_listings(driver)
        else: break

    if records: save_fn(records, csv_path)
    save_checkpoint_fn(min_price, max_price)
    return len(records)

def save_incremental(data, path):
    exists = os.path.isfile(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not exists: writer.writeheader()
        writer.writerows(data)