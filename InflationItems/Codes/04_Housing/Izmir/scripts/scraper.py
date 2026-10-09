import csv
import logging
import math
import os
import random
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys

import config

logger = logging.getLogger(__name__)


# Custom Exception for the hard login block
class LoginRequiredException(Exception):
    pass


IZMIR_DISTRICT_SLUGS = [
    "izmir-aliaga", "izmir-balcova", "izmir-bayindir", "izmir-bayrakli",
    "izmir-bergama", "izmir-beydag", "izmir-bornova", "izmir-buca",
    "izmir-cesme", "izmir-cigli", "izmir-dikili", "izmir-foca",
    "izmir-gaziemir", "izmir-guzelbahce", "izmir-karabaglar", "izmir-karaburun",
    "izmir-karsiyaka", "izmir-kemalpasa", "izmir-kinik", "izmir-kiraz",
    "izmir-konak", "izmir-menderes", "izmir-menemen", "izmir-narlidere",
    "izmir-odemis", "izmir-seferihisar", "izmir-selcuk", "izmir-tire",
    "izmir-torbali", "izmir-urla",
]

IZMIR_SLUG_TO_DISTRICT = {
    "izmir-aliaga": "Aliağa", "izmir-balcova": "Balçova", "izmir-bayindir": "Bayındır",
    "izmir-bayrakli": "Bayraklı", "izmir-bergama": "Bergama", "izmir-beydag": "Beydağ",
    "izmir-bornova": "Bornova", "izmir-buca": "Buca", "izmir-cesme": "Çeşme",
    "izmir-cigli": "Çiğli", "izmir-dikili": "Dikili", "izmir-foca": "Foça",
    "izmir-gaziemir": "Gaziemir", "izmir-guzelbahce": "Güzelbahçe", "izmir-karabaglar": "Karabağlar",
    "izmir-karaburun": "Karaburun", "izmir-karsiyaka": "Karşıyaka", "izmir-kemalpasa": "Kemalpaşa",
    "izmir-kinik": "Kınık", "izmir-kiraz": "Kiraz", "izmir-konak": "Konak",
    "izmir-menderes": "Menderes", "izmir-menemen": "Menemen", "izmir-narlidere": "Narlıdere",
    "izmir-odemis": "Ödemiş", "izmir-seferihisar": "Seferihisar", "izmir-selcuk": "Selçuk",
    "izmir-tire": "Tire", "izmir-torbali": "Torbalı", "izmir-urla": "Urla"
}


def _check_login_wall(driver: WebDriver):
    """Helper to check if we hit the hard login block."""
    page_source = driver.page_source.lower()
    current_url = driver.current_url.lower()

    if "sahibinden.com" in current_url:
        if "giriş yapmanız gerekmektedir" in page_source or "secure.sahibinden.com/giris" in current_url:
            logger.error("🚨 Hard login block detected!")
            raise LoginRequiredException("Login wall hit.")


def human_like_scroll(driver: WebDriver, target_duration: float = 1.5):
    """Simulates a natural scroll while collecting data on a strict time budget."""
    start_time = time.time()
    logger.info(f"      🖱️  Simulating human scroll behavior (~{target_duration}s)...")

    while (time.time() - start_time) < target_duration:
        total_height = driver.execute_script("return document.body.scrollHeight")
        current_pos = driver.execute_script("return window.pageYOffset;")

        step = random.randint(200, 400)
        new_pos = current_pos + step

        if new_pos > total_height:
            new_pos = max(0, total_height - random.randint(100, 300))

        driver.execute_script(f"window.scrollTo({{top: {new_pos}, behavior: 'smooth'}});")
        time.sleep(random.uniform(0.05, 0.2))

        if random.random() < 0.10:
            current_pos = driver.execute_script("return window.pageYOffset;")
            new_pos = max(0, current_pos - random.randint(50, 150))
            driver.execute_script(f"window.scrollTo({{top: {new_pos}, behavior: 'smooth'}});")
            time.sleep(random.uniform(0.05, 0.2))

    driver.execute_script(f"window.scrollTo({{top: {random.randint(100, 400)}, behavior: 'smooth'}});")
    time.sleep(0.1)


def _wait_for_listings(driver: WebDriver) -> BeautifulSoup:
    """Manual intervention logic for CAPTCHAs and auto-restart for login blocks."""
    time.sleep(random.uniform(0.5, 0.8))

    for _ in range(12):
        # 1. DETECT THE LOGIN WALL
        _check_login_wall(driver)

        # 2. CHECK IF LISTINGS LOADED
        page_source = driver.page_source.lower()
        soup = BeautifulSoup(driver.page_source, "lxml")
        if soup.select("#searchResultsTable tbody tr.searchResultsItem") or "ilan bulunamadı" in page_source:
            return soup

        time.sleep(0.5)

        # 3. MANUAL FALLBACK FOR STANDARD CAPTCHAS
    print("\n" + "=" * 60 + "\n🛑 CAPTCHA/BOT CHECK! Solve it manually.\n" + "=" * 60)
    input("   ▶ Press ENTER after listings are visible... ")
    return BeautifulSoup(driver.page_source, "lxml")


def warmup_session(driver: WebDriver) -> None:
    """Warmup flow: Google -> Home -> Search İzmir -> District Filters."""
    logger.info("🔥 Starting organic warmup flow...")
    try:
        driver.get("https://www.google.com")
        time.sleep(random.uniform(3.0, 5.0))  # 🐌 Slower

        try:
            consent_btn = driver.find_element("xpath", "//button[contains(., 'Accept') or contains(., 'Kabul')]")
            driver.execute_script("arguments[0].click();", consent_btn)
        except:
            pass

        search_q = driver.find_element("name", "q")
        search_q.send_keys("sahibinden")
        search_q.send_keys(Keys.ENTER)
        time.sleep(random.uniform(3.0, 5.0))  # 🐌 Slower

        sahibinden_link = driver.find_element("xpath", "//a[contains(@href, 'sahibinden.com')]")
        driver.execute_script("arguments[0].click();", sahibinden_link)
        time.sleep(random.uniform(5.0, 7.0))  # 🐌 Slower

        # 🚨 Check for login wall immediately after landing on the site
        _check_login_wall(driver)

        try:
            cookie_btn = driver.find_element("xpath", "//button[text()='Kabul Et' or text()='Accept']")
            driver.execute_script("arguments[0].click();", cookie_btn)
        except:
            pass

        logger.info("  → Simulating 'İzmir kiralık' search...")
        search_bar = driver.find_element("id", "searchText")
        search_bar.send_keys("İzmir kiralık")
        search_bar.send_keys(Keys.ENTER)
        time.sleep(random.uniform(5.0, 8.0))  # 🐌 Slower

        # 🚨 Check again after performing a search
        _check_login_wall(driver)

        # Override the fast scroll to be slower during warmup
        human_like_scroll(driver, target_duration=4.0)

        logger.info("  → Expanding district filters...")
        ilce_filter = driver.find_elements("xpath",
                                           "//li[contains(@class, 'filter-item')]//*[contains(text(), 'İlçe')]")
        if ilce_filter:
            driver.execute_script("arguments[0].click();", ilce_filter[0])
            time.sleep(random.uniform(3.0, 5.0))  # 🐌 Slower

        logger.info("🚀 Warmup complete!")

    except LoginRequiredException:
        # Re-raise so the main loop catches it and restarts
        raise
    except Exception as e:
        logger.warning(f"⚠️ Warmup failed: {e}. Moving to scraping.")


def load_and_bypass(driver: WebDriver, url: str) -> BeautifulSoup:
    driver.execute_script(f"window.location.href = '{url}';")
    return _wait_for_listings(driver)


def _build_page_urls(base_url: str, total_listings: int) -> list[str]:
    total_pages = min(math.ceil(total_listings / config.PAGE_SIZE), 20)
    return [f"{base_url}&pagingOffset={p * config.PAGE_SIZE}" for p in range(total_pages)]


class CategoryScanner:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def _extract_total(self, soup):
        elem = soup.select_one(".result-text")
        if elem:
            m = re.search(r"(\d+)\s*ilan", elem.get_text(strip=True).replace(".", ""), re.IGNORECASE)
            return int(m.group(1)) if m else None
        return None

    def get_district_total(self, slug):
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        soup = load_and_bypass(self.driver, url)
        return self._extract_total(soup) or 0

    def get_district_pages_no_price(self, slug, total):
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        return _build_page_urls(url, total)

    def discover_bracket(self, slug, min_p, max_p, indent=0, results=None):
        if results is None: results = []
        pad = "  " * indent
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}&price_min={min_p}&price_max={max_p}"
        logger.info(f"{pad}▶ Checking {slug} | {min_p}–{max_p} TL…")
        soup = load_and_bypass(self.driver, url)
        total = self._extract_total(soup)
        if not total: return results

        if total > config.MAX_LISTINGS_PER_QUERY and (max_p - min_p) > 0:
            mid = (min_p + max_p) // 2
            self.discover_bracket(slug, min_p, mid, indent + 1, results)
            time.sleep(random.uniform(0.3, 0.6))
            self.discover_bracket(slug, mid + 1, max_p, indent + 1, results)
        else:
            results.extend(_build_page_urls(url, total))
        return results


class DataExtractor:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def extract_from_url(self, url):
        load_and_bypass(self.driver, url)
        human_like_scroll(self.driver)

        soup = BeautifulSoup(self.driver.page_source, "lxml")
        records = []
        for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            try:
                price = row.select_one(".searchResultsPriceValue").text.strip()
                loc = " / ".join(row.select_one(".searchResultsLocationValue").stripped_strings)
                attrs = [a.text.strip() for a in row.select(".searchResultsAttributeValue")]
                rooms = attrs[1] if len(attrs) > 1 else "N/A"
                records.append({"Rooms": rooms, "Price": price})
            except:
                continue
        return records


def save_incremental(data_batch):
    if not data_batch: return 0
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)
    with open(config.CSV_OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price", "PriceInt"])
        if not file_exists: writer.writeheader()
        for r in data_batch:
            p_int = "".join(filter(str.isdigit, r["Price"]))
            writer.writerow({**r, "PriceInt": p_int})
    return len(data_batch)