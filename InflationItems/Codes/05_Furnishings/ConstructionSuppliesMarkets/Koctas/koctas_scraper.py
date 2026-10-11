"""
Koçtaş power-tools scraper.

koctas.com.tr sits behind Akamai's behavioural challenge (plain HTTP clients
get 403 / sec-cpt page), so this scraper keeps ONE headless
undetected-chromedriver for the whole run and reads the GTM dataLayer
"product-impressions" push that every category page renders.

Low-RAM settings: images/CSS disabled, third-party trackers blocked via CDP,
single renderer process, Chrome recycled every PAGES_PER_BROWSER pages (and
on a crash, with one retry of the page), page-load timeout, temp profile
removed, driver.quit() in ``finally``. One long-lived browser peaked at
~3.4 GB RSS; one per 27-page category still at ~1 GB USS.

Category IDs were re-verified on 2026-09-28: Koçtaş routes by the numeric
``/c/<id>`` and ignores the slug, and several old IDs now point to other
categories (106001 = Jeneratörler, 106003 = Tezgah Tipi Testereler,
106004 = Testereler, 106006 = Zımpara ve Polisaj). Each page's dataLayer
``list`` name is checked against the expected name and written to the CSV
(``site_category``) so a future remap is visible in the data.

Output: InflationItems/Datas/05_Furnishings/ConstructionSuppliesMarkets/Koctas/koctas_YYYY-MM-DD.csv
"""

import csv
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "05_Furnishings" / "ConstructionSuppliesMarkets" / "Koctas"

# (label, url, expected dataLayer list name, tuik code, max pages)
CATEGORIES = [
    ("Akülü Vidalamalar",      "https://www.koctas.com.tr/elektrikli-el-aletleri/akulu-vidalamalar/c/106007",                    "Akülü Vidalamalar",                "05", 40),
    ("Matkaplar",              "https://www.koctas.com.tr/elektrikli-el-aletleri/matkaplar/c/106005",                            "Matkaplar",                        "05", 40),
    ("Kırıcılar ve Deliciler", "https://www.koctas.com.tr/elektrikli-el-aletleri/kiricilar-ve-deliciler/c/106010",               "Kırıcılar ve Deliciler",           "05", 40),
    ("Taşlamalar",             "https://www.koctas.com.tr/elektrikli-el-aletleri/taslamalar/c/106009",                           "Taşlamalar",                       "05", 40),
    ("Testereler",             "https://www.koctas.com.tr/elektrikli-el-aletleri/testereler/c/106004",                           "Testereler",                       "05", 40),
    ("Zımpara ve Polisaj",     "https://www.koctas.com.tr/elektrikli-el-aletleri/zimpara-ve-polisaj/c/106006",                   "Zımpara ve Polisaj",               "05", 40),
    ("Boya Tabancaları",       "https://www.koctas.com.tr/elektrikli-el-aletleri/boya-tabancasi-ve-karistiricilar/c/106012",     "Boya Tabancası ve Karıştırıcılar", "05", 40),
    ("Kaynak Makineleri",      "https://www.koctas.com.tr/kaynak-makineleri/inverter-kaynak-makineleri/c/106015008",             "İnverter Kaynak Makineleri",       "05", 40),
]

PAGES_PER_BROWSER = 6

BLOCKED_URLS = [
    "*personaclick.com*", "*gengage.ai*", "*efilli.com*", "*unpkg.com*", "*hicloud.com*",
    "*go2sdk.com*", "*quinengine.com*", "*googlesyndication.com*", "*google-analytics.com*",
    "*googletagmanager.com*", "*sgtm.koctas.com.tr*", "*doubleclick.net*", "*facebook.net*",
    "*.jpg*", "*.jpeg*", "*.png*", "*.webp*", "*.gif*", "*.woff*", "*.woff2*", "*.mp4*",
]

FIELDS = ["product_id", "product_name", "price", "brand", "category", "site_category"]

READ_DATALAYER_JS = """
var dl = window.dataLayer || [];
var imp = [], list = null;
dl.forEach(function(d) {
    if (d.event === 'product-impressions' && d.ecommerce && d.ecommerce.impressions) {
        imp = imp.concat(d.ecommerce.impressions);
        if (d.ecommerce.actionField) list = d.ecommerce.actionField.list;
    }
});
return {items: imp, list: list};
"""

log = logging.getLogger("koctas")


def chrome_major_version():
    """Installed Chrome's major version (uc otherwise fetches the newest driver,
    which fails with SessionNotCreated when Chrome lags behind)."""
    if os.getenv("CHROME_VERSION_MAIN"):
        return int(os.environ["CHROME_VERSION_MAIN"])
    for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        try:
            out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        m = re.search(r"(\d+)\.\d+\.\d+", out)
        if m:
            return int(m.group(1))
    for base in (os.getenv("PROGRAMFILES", ""), os.getenv("PROGRAMFILES(X86)", ""), os.getenv("LOCALAPPDATA", "")):
        app = Path(base) / "Google" / "Chrome" / "Application"
        if app.is_dir():
            versions = [int(p.name.split(".")[0]) for p in app.iterdir() if re.match(r"\d+\.", p.name)]
            if versions:
                return max(versions)
    return None


def make_driver(profile_dir):
    import undetected_chromedriver as uc

    version = chrome_major_version()
    opts = uc.ChromeOptions()
    # Headless Chrome announces "HeadlessChrome/..." in its UA and Akamai answers
    # "Access Denied" immediately (seen 2026-09-28); present a normal desktop UA.
    # OS part must match navigator.platform or the UA itself looks spoofed.
    os_part = "Windows NT 10.0; Win64; x64" if sys.platform == "win32" else "X11; Linux x86_64"
    opts.add_argument(
        f"--user-agent=Mozilla/5.0 ({os_part}) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{version or 140}.0.0.0 Safari/537.36"
    )
    for arg in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
        "--window-size=1280,800", "--blink-settings=imagesEnabled=false",
        "--disable-extensions", "--disable-background-networking",
        "--renderer-process-limit=1", "--log-level=3",
        # Do NOT add --disable-site-isolation-trials / --disable-features=site-per-process /
        # --js-flags heap caps here: Akamai answered "Access Denied" with them (2026-09-28).
        f"--user-data-dir={profile_dir}",
    ):
        opts.add_argument(arg)
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    })
    # Upstream pinned version_main=151; detect the installed Chrome instead so an
    # apt upgrade on the server does not break the run.
    driver = uc.Chrome(options=opts, use_subprocess=True, version_main=version)
    driver.set_page_load_timeout(60)
    # Third-party trackers/recommenders are most of the page's JS heap; the
    # product data is an inline first-party dataLayer push, and Akamai's own
    # scripts (first-party path, mpulse/akstat) are left alone.
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URLS})
    except Exception as e:
        log.warning("Could not set URL blocklist: %s", e)
    return driver


def get_total_pages(driver):
    from selenium.webdriver.common.by import By
    try:
        pages = driver.find_elements(By.CSS_SELECTOR, ".pagination a, [class*='pagination'] a")
        nums = [int(p.text.strip()) for p in pages if p.text.strip().isdigit()]
        return max(nums) if nums else 1
    except Exception:
        return 1


def read_page(driver, url, timeout=15):
    try:
        driver.get(url)
    except Exception as e:
        log.warning("Load timeout/error for %s: %s", url, e)
    end = time.time() + timeout
    data = {"items": [], "list": None}
    while time.time() < end:
        try:
            data = driver.execute_script(READ_DATALAYER_JS) or data
            if data.get("items"):
                break
        except Exception:
            pass
        time.sleep(0.5)
    time.sleep(random.uniform(0.3, 0.8))

    products = []
    for it in data.get("items") or []:
        name = (it.get("name") or "").strip()
        try:
            price = round(float(str(it.get("price")).replace(",", ".")), 2)
        except (TypeError, ValueError):
            price = None
        if name and price is not None:
            products.append({"product_id": str(it.get("id") or ""), "product_name": name,
                             "price": price, "brand": it.get("brand") or ""})
    return products, data.get("list")


class Browser:
    """One headless Chrome that is recycled every PAGES_PER_BROWSER pages.

    The renderer keeps growing with every ~3 MB category page (one browser for a
    27-page category peaked at ~1 GB USS), and a crashed Chrome
    ("invalid session id") must not cost the rest of a category.
    """

    def __init__(self):
        self.driver = None
        self.profile_dir = None
        self.pages = 0

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
        if self.profile_dir:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        self.driver, self.profile_dir, self.pages = None, None, 0

    def get(self):
        if self.driver is not None and self.pages >= PAGES_PER_BROWSER:
            self.close()
        if self.driver is None:
            self.profile_dir = tempfile.mkdtemp(prefix="koctas_chrome_")
            self.driver = make_driver(self.profile_dir)
        self.pages += 1
        return self.driver

    def read(self, url):
        """read_page with one retry on a fresh browser when nothing came back."""
        for attempt in (1, 2):
            try:
                driver = self.get()
                prods, site_list = read_page(driver, url)
                if prods:
                    return prods, site_list, driver
            except Exception as e:
                log.warning("Browser error on %s: %s", url, e)
            if attempt == 1:
                self.close()
                time.sleep(random.uniform(5, 10))
        return [], None, None


def scrape_category(browser, label, base_url, expected_list, max_pages):
    rows = []
    prods, site_list, driver = browser.read(base_url)
    if not prods:
        log.warning("[%s] page 1 returned no products (blocked?), skipping category", label)
        return rows
    if site_list and site_list != expected_list:
        log.warning("[%s] site category is '%s', expected '%s' — Koçtaş remapped this ID, check CATEGORIES",
                    label, site_list, expected_list)
    max_pages = min(max_pages, int(os.getenv("KOCTAS_MAX_PAGES", max_pages)))  # bounded test runs
    total_pages = min(get_total_pages(driver), max_pages)
    log.info("[%s] %d pages (max %d); page 1: %d products", label, total_pages, max_pages, len(prods))
    rows.extend({**p, "category": label, "site_category": site_list or ""} for p in prods)

    for page in range(2, total_pages + 1):
        time.sleep(random.uniform(1.0, 2.0))
        prods, page_list, _ = browser.read(f"{base_url}?page={page}")
        if not prods:
            log.warning("[%s] page %d/%d: 0 products after retry (blocked?), skipping rest of category",
                        label, page, total_pages)
            break
        rows.extend({**p, "category": label, "site_category": page_list or site_list or ""} for p in prods)
        log.info("[%s] page %d/%d: %d products", label, page, total_pages, len(prods))
    return rows


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    out_file = OUT_DIR / f"koctas_{date.today():%Y-%m-%d}.csv"
    if out_file.exists():
        log.info("Already scraped today, skipping: %s", out_file)
        return

    all_rows = []
    browser = Browser()
    try:
        for label, url, expected, _tuik, max_pages in CATEGORIES:
            try:
                data = scrape_category(browser, label, url, expected, max_pages)
            except Exception as e:
                log.error("[%s] failed: %s", label, e)
                data = []
            all_rows.extend(data)
            log.info("[%s] done: %d products", label, len(data))
            time.sleep(random.uniform(2.5, 4.0))
    finally:
        browser.close()

    seen, deduped = set(), []
    for row in all_rows:
        key = row["product_id"] or row["product_name"]
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    if not deduped:
        log.error("No data collected.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(deduped)
    log.info("Saved %d products to %s", len(deduped), out_file)


if __name__ == "__main__":
    main()
