"""
Beymen technology scraper.

Beymen's listing API (/api/product/list) is behind Akamai. On most runs a
Chrome-TLS client (curl_cffi) gets through without any cookies, so no
browser is started. Only when the API answers 403 do we open ONE headless
undetected-chromedriver, collect the Akamai cookies, cache them on disk
(Akamai's _abck is long-lived) and continue with curl_cffi. The browser is
always closed before the bulk requests start.

Output: InflationItems/Datas/08_Communication/Beymen/beymen_YYYY-MM-DD.csv
"""

import csv
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from curl_cffi import requests as cffi_requests

BASE_API_URL = "https://www.beymen.com/api/product/list"
TARGET_WEB_URL = "https://www.beymen.com/tr/teknoloji-95935"
CATEGORY_ID = "95935"
# The API reports totalPageCount (223 pages / 10657 products on 2026-09-28; the
# old fixed limit of 200 pages silently dropped ~1000 products). This is only a
# safety cap; lower it via env for a bounded test run.
MAX_PAGES = int(os.getenv("BEYMEN_MAX_PAGES", "2000"))
REQUEST_TIMEOUT = 30

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "InflationItems" / "Datas" / "08_Communication" / "Beymen"
COOKIE_CACHE = Path(__file__).resolve().parent / ".beymen_cookies.json"

log = logging.getLogger("beymen")


class Blocked(Exception):
    pass


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


def get_stealth_cookies(target_url):
    """Open one headless Chrome, let Akamai set its cookies, close it."""
    import undetected_chromedriver as uc

    log.info("Collecting Akamai cookies with headless Chrome: %s", target_url)
    profile_dir = tempfile.mkdtemp(prefix="beymen_chrome_")
    version = chrome_major_version()
    opts = uc.ChromeOptions()
    # Headless Chrome's default UA contains "HeadlessChrome", which Akamai
    # rejects outright; the OS part must match navigator.platform.
    os_part = "Windows NT 10.0; Win64; x64" if sys.platform == "win32" else "X11; Linux x86_64"
    opts.add_argument(
        f"--user-agent=Mozilla/5.0 ({os_part}) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{version or 140}.0.0.0 Safari/537.36"
    )
    for arg in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
        "--window-size=1280,800", "--blink-settings=imagesEnabled=false",
        "--disable-extensions", "--renderer-process-limit=1",
        f"--user-data-dir={profile_dir}",
    ):
        opts.add_argument(arg)
    driver = uc.Chrome(options=opts, use_subprocess=True, version_main=version)
    try:
        driver.set_page_load_timeout(60)
        driver.get(target_url)
        time.sleep(8)  # let Akamai's sensor script produce its tokens
        driver.execute_script("window.scrollBy(0, 300)")
        time.sleep(2)
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    finally:
        driver.quit()
        shutil.rmtree(profile_dir, ignore_errors=True)
    log.info("Got %d cookies.", len(cookies))
    try:
        COOKIE_CACHE.write_text(json.dumps(cookies), encoding="utf-8")
    except OSError as e:
        log.warning("Could not cache cookies: %s", e)
    return cookies


def load_cached_cookies():
    try:
        return json.loads(COOKIE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fetch_page(session, page):
    params = {"languageCode": "tr", "sayfa": page, "categoryId": CATEGORY_ID, "includeDocuments": "true"}
    for attempt in range(1, 4):
        try:
            r = session.get(BASE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            log.warning("Page %d attempt %d failed: %s", page, attempt, e)
            time.sleep(5 * attempt)
            continue
        if r.status_code == 403:
            raise Blocked()
        if r.status_code >= 400:
            log.warning("Page %d HTTP %d (attempt %d)", page, r.status_code, attempt)
            time.sleep(5 * attempt)
            continue
        data = r.json().get("data") or {}
        return data.get("productList") or data.get("products") or [], data.get("totalPageCount")
    raise RuntimeError(f"page {page} failed after retries")


def make_session(cookies):
    s = cffi_requests.Session(impersonate="chrome")
    s.headers.update({"Accept": "application/json, text/plain, */*", "Referer": TARGET_WEB_URL})
    if cookies:
        s.cookies.update(cookies)
    return s


def scrape_beymen():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"beymen_{date_str}.csv"
    tmp_file = out_file.with_suffix(".csv.part")

    session = make_session(load_cached_cookies())
    used_browser = False
    total = 0
    seen = set()

    with tmp_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Tarih", "UrunID", "UrunAdi", "FiyatFloat"])
        page = 1
        total_pages = None
        while page <= min(total_pages or MAX_PAGES, MAX_PAGES):
            try:
                products, reported = fetch_page(session, page)
                if total_pages is None and reported:
                    total_pages = int(reported)
                    log.info("API reports %d pages", total_pages)
            except Blocked:
                if used_browser:
                    log.error("403 on page %d even with fresh browser cookies; stopping.", page)
                    break
                log.warning("403 on page %d; refreshing cookies with browser.", page)
                used_browser = True
                try:
                    session = make_session(get_stealth_cookies(TARGET_WEB_URL))
                except Exception as e:
                    log.error("Browser cookie collection failed: %s", e)
                    break
                continue
            except Exception as e:
                log.error("Page %d: %s", page, e)
                break

            if not products:
                log.info("No products on page %d; done (%d pages).", page, page - 1)
                break
            for item in products:
                pid = item.get("productId")
                if pid in seen:  # listing order can shift between pages during a run
                    continue
                seen.add(pid)
                writer.writerow([date_str, pid, item.get("displayName"), item.get("actualPrice")])
                total += 1
            f.flush()
            log.info("Page %d saved (%d products, total %d)", page, len(products), total)
            page += 1
            time.sleep(random.uniform(1.5, 3.5))

    if total == 0:
        tmp_file.unlink(missing_ok=True)
        log.error("No data collected.")
        sys.exit(1)
    os.replace(tmp_file, out_file)
    log.info("Saved %d rows to %s", total, out_file)


if __name__ == "__main__":
    scrape_beymen()
