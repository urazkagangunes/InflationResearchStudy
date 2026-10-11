"""
Home internet price scraper (TÜİK 0833001 "İnternet ücreti").

Providers and where the data lives (recon 2026-10-08, docs/site-analysis/telecom/NOTES.md):
  superonline  sitemap-campaigns.xml -> one page per campaign; __NEXT_DATA__ GetCampaignDetail.offers[]
  vodafone     /net/* pages, server-rendered .card-tariff-2 cards
  kablonet     turksatkablo.com.tr/internet-Tarifeler, two static tables (list prices).
               The server omits its intermediate certificate; it is fetched from the AIA URL.
  milleni      milleni.com.tr campaign cards ([data-campaign-card] data-* attributes)
  turknet      /tarifelerimiz "Abone alımına açık tarifeler" table. Cloudflare: curl_cffi 0.15
               is answered 403, so one headless Chrome visit supplies cookies + UA, then curl_cffi.
  turktelekom  sitemap evde-internet/* detail pages (same SharePoint layout as mobile)

Output: InflationItems/Datas/08_Communication/<Provider>/<provider>_internet_YYYY-MM-DD.csv
Usage:  python internet.py [--operator superonline|vodafone|kablonet|milleni|turknet|turktelekom|all] [--limit N]
"""

import json
import os
import re
import ssl
import subprocess
import tempfile
import time
from pathlib import Path

import certifi
from bs4 import BeautifulSoup
from curl_cffi import requests

from scraper import (OUT_ROOT, TODAY, Blocked, Fetcher, log, norm_period, row, run, tl,
                     tr_lower, tt_details)

FIELDS = ["date", "operator", "group", "product_id", "product_name", "price", "list_price", "period",
          "speed_mbps", "upload_mbps", "infrastructure", "commitment_months", "url"]


def irow(operator, **kw):
    return row(operator, fields=FIELDS, **kw)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", tr_lower(text).translate(str.maketrans("çğıöşü", "cgiosu"))).strip("-")


def months(text):
    """'12 ay sabit fiyat' -> 12."""
    m = re.search(r"(\d+)\s*ay\b", tr_lower(text))
    return int(m.group(1)) if m else ""


def mbps(text):
    m = re.search(r"(\d+)\s*(?:mbps|mb\b)", tr_lower(text))
    return int(m.group(1)) if m else ""


# ---------------------------------------------------------------- superonline

SUPERONLINE = "https://www.superonline.net"


def superonline(limit):
    f = Fetcher(SUPERONLINE)
    sitemap = f.get(SUPERONLINE + "/sitemap-campaigns.xml", min_len=500)
    # /ev-interneti/<category>/<campaign>/<speed>: one page per campaign carries every speed offer
    campaigns = {}
    for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap):
        m = re.match(r"(https://www\.superonline\.net/ev-interneti/[^/?]+/[^/?]+)/[^/?]+$", u)
        if m:
            campaigns.setdefault(m.group(1), u)
    log.info("superonline: %d campaigns in sitemap", len(campaigns))
    rows = []
    for base, url in campaigns.items():
        if limit and len(rows) >= limit:
            break
        html = f.get(url)
        if html is None:
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise Blocked(f"superonline {url}: no __NEXT_DATA__")
        for q in json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]["queries"]:
            if q["queryKey"][0] != "GetCampaignDetail":
                continue
            c = ((q["state"].get("data") or {}).get("data") or {}).get("campaign") or {}
            if (c.get("validityDate") or "9999")[:10] < TODAY:  # expired campaign still in the sitemap
                continue
            for o in c.get("offers") or []:
                if o.get("passive") or not o.get("price"):
                    continue
                speed = o.get("download") if str(o.get("download") or "0") != "0" else ""
                # Superbox (4.5G/5G home internet) offers have a GB quota instead of a speed
                quota = f"{o.get('limit')} {o.get('limitType')}" if str(o.get("limit") or "0") != "0" else ""
                rows.append(irow(
                    "superonline", group=base.rsplit("/", 2)[-2],
                    product_id=f"{c.get('id')}-{o['id']}",
                    product_name=" ".join(filter(None, [c.get("title", "").strip(), speed and str(speed),
                                                        speed and (o.get("downloadType") or ""), quota])),
                    price=tl(o["price"]), period="1_ay",
                    speed_mbps=speed, upload_mbps=o.get("upload"),
                    infrastructure=(c.get("networkType") or {}).get("lookupValue"),
                    commitment_months=int(o["period"]) if str(o.get("period") or "0") != "0" else "",
                    url=f"{base}/{o.get('urlPostFix')}",
                ))
    return rows


# ---------------------------------------------------------------- vodafone

VODAFONE = "https://www.vodafone.com.tr"
VODAFONE_PAGES = ["/net/ev-internet-paketi-fiyatlari", "/net/fiber-internet", "/net/fiber-internet-12-aylik",
                  "/net/redbox"]


def vodafone(limit):
    f = Fetcher(VODAFONE)
    rows = []
    for path in VODAFONE_PAGES:
        html = f.get(VODAFONE + path)
        if html is None:
            continue
        for card in BeautifulSoup(html, "html.parser").select(".card-tariff-2"):
            name = card.select_one(".card-name")
            price = card.select_one(".card-price-value")
            if not (name and price):
                continue
            link = card.select_one("a[href*=tarifeId]")
            tid = re.search(r"tarifeId=(\d+)", link["href"]).group(1) if link else None
            tag = card.select_one(".card-rightTag")
            details = " ".join(li.get_text(" ", strip=True) for li in card.select(".card-modal-detailItem"))
            camp = re.search(r"Kampanya adı:\s*(.+?\))", details)
            rows.append(irow(
                "vodafone", group=path.rsplit("/", 1)[-1],
                product_id=tid or f"{name.get_text(strip=True)}-{tag.get_text(strip=True) if tag else ''}",
                product_name=" ".join(filter(None, [name.get_text(" ", strip=True),
                                                    tag.get_text(" ", strip=True) if tag else "",
                                                    f"({camp.group(1)})" if camp else ""])),
                price=tl(price.get_text(" ", strip=True)),
                period=norm_period((card.select_one(".card-price-period") or price).get_text(strip=True)),
                speed_mbps=mbps((card.select_one(".card-benefit1") or name).get_text(" ", strip=True)),
                infrastructure=(card.select_one(".card-subDescription1") or name).get_text(" ", strip=True),
                commitment_months=months((card.select_one(".card-description2") or name).get_text(" ", strip=True)),
                url=VODAFONE + path,
            ))
        if limit and len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------- kablonet

KABLONET = "https://www.turksatkablo.com.tr"
# ponytail: hard-coded AIA URL of the intermediate the server fails to send; update when GlobalSign rotates it
KABLONET_INTERMEDIATE = "http://secure.globalsign.com/cacert/gsgccr46alphasslca2025.crt"


def aia_bundle(url):
    """certifi roots + the missing intermediate (DER from the AIA URL) -> temp PEM bundle path.

    Browsers complete the chain the same way; verification stays on (the intermediate is
    itself checked against the certifi root)."""
    der = requests.get(url, timeout=30).content
    out = Path(tempfile.gettempdir()) / "telecom_ca_bundle.pem"
    out.write_text(Path(certifi.where()).read_text() + "\n" + ssl.DER_cert_to_PEM_cert(der))
    return str(out)


def kablonet(limit):
    f = Fetcher(KABLONET, verify=aia_bundle(KABLONET_INTERMEDIATE))
    html = f.get(KABLONET + "/internet-Tarifeler")
    rows = []
    for ti, table in enumerate(BeautifulSoup(html, "html.parser").select("table")):
        trs = table.select("tr")
        if not trs:
            continue
        head = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]
        if not head or "İndirme" not in head[0] or "Fiyat" not in head[-1]:
            continue
        # columns 1..n-2 are "Yükleme Hızı <infra>"; one row per infrastructure that offers the speed
        infras = [re.sub(r"^Yükleme Hızı\s*", "", h) for h in head[1:-1]]
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) != len(head):
                continue
            speed = mbps(cells[0])
            for infra, up in zip(infras, cells[1:-1]):
                if up in ("-", ""):
                    continue
                rows.append(irow(
                    "kablonet", group=f"tablo-{ti + 1}",
                    product_id=f"{speed}-{slug(infra)}",
                    product_name=f"{re.sub(r'[(].*?[)]', '', cells[0]).strip()} {infra}",
                    price=tl(cells[-1]), period=norm_period(cells[-1]),
                    speed_mbps=speed, upload_mbps=mbps(up), infrastructure=infra,
                    url=KABLONET + "/internet-Tarifeler",
                ))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- milleni (Millenicom)

MILLENI = "https://www.milleni.com.tr"


def milleni(limit):
    f = Fetcher(MILLENI)
    soup = BeautifulSoup(f.get(MILLENI + "/eviniz-icin/kampanyalar/internet"), "html.parser")
    old = {}  # strike-through list prices only appear on the spotlight cards
    for art in soup.select("article[data-pkg-id]"):
        s = art.select_one("[class*=price-old]")
        if s:
            old[art["data-pkg-id"]] = tl(s.get_text(" ", strip=True))
    rows = []
    for c in soup.select("[data-campaign-card][data-pkg-id]"):
        pid = c["data-pkg-id"]
        price = tl(c.get("data-price"))
        cta = c.select_one("a[href*='/basvuru/']")
        rows.append(irow(
            "milleni", group=c.get("data-type"), product_id=pid,
            product_name=f"{c.get('data-pkg-name')} {c.get('data-speed')} Mbps ({c.get('data-provider')})",
            price=price, list_price=old.get(pid) if old.get(pid) != price else None, period="1_ay",
            speed_mbps=c.get("data-speed"), infrastructure=c.get("data-infra"),
            commitment_months=12 if c.get("data-commitment") == "true" else "",
            url=MILLENI + cta["href"] if cta else MILLENI + "/eviniz-icin/kampanyalar/internet",
        ))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- turknet

TURKNET = "https://www.turk.net"


def chrome_major_version():
    """Installed Chrome's major version (uc otherwise fetches the newest driver -> SessionNotCreated)."""
    if os.getenv("CHROME_VERSION_MAIN"):  # server .env override, same as Beymen
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


def browser_visit(url, until=None, wait=30):
    """One headless Chrome visit -> (cookies, user agent, rendered body text). Chrome is always closed.

    Waits for a Cloudflare interstitial to clear and, if `until` (regex) is given, for it to appear in
    the rendered text (client-side rendered prices)."""
    import undetected_chromedriver as uc

    log.info("headless Chrome: %s", url)
    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=opts, headless=True, version_main=chrome_major_version(),
                       user_data_dir=tempfile.mkdtemp(prefix="telecom_chrome_"))
    try:
        driver.set_page_load_timeout(60)
        # headless UA contains "HeadlessChrome", which bot managers flag
        ua = driver.execute_script("return navigator.userAgent").replace("HeadlessChrome", "Chrome")
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
        driver.get(url)
        text = ""
        for _ in range(wait):
            if "Just a moment" not in driver.title:
                text = driver.find_element("tag name", "body").text
                if not until or re.search(until, text):
                    break
            time.sleep(1)
        return {c["name"]: c["value"] for c in driver.get_cookies()}, ua, text
    finally:
        driver.quit()


def browser_cookies(home):
    """Cloudflare cookies + UA from one headless Chrome visit (cookie factory for curl_cffi)."""
    cookies, ua, _ = browser_visit(home)
    return cookies, ua


def turknet(limit):
    try:
        f = Fetcher(TURKNET)
        html = f.get(TURKNET + "/tarifelerimiz")
    except Blocked:
        cookies, ua = browser_cookies(TURKNET + "/")
        f = Fetcher.__new__(Fetcher)  # skip the homepage GET: the browser already did it
        f.s, f.n = requests.Session(impersonate="chrome124"), 0
        f.s.headers.update({"User-Agent": ua, "Referer": TURKNET + "/"})
        f.s.cookies.update(cookies)
        html = f.get(TURKNET + "/tarifelerimiz")
    soup = BeautifulSoup(html, "html.parser")
    # first table = "Abone alımına açık tarifeler"; later ones are closed / withdrawn tariffs
    table = next((t for t in soup.select("table")
                  if "Kampanya No" in t.get_text() and "Kapatılma" not in t.get_text()), None)
    if table is None:
        raise Blocked("turknet: tariff table not found")
    trs = table.select("tr")
    head = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]
    rows = []
    for tr in trs[1:]:
        cells = dict(zip(head, (c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]))))
        name = cells.get("Tarife Adı", "")
        if not name:
            continue
        rows.append(irow(
            "turknet", group=f"segment-{cells.get('Segment', '')}", product_id=cells.get("Kampanya No"),
            product_name=name, price=tl(cells.get("Aylık Fiyatı")), period="1_ay",
            speed_mbps=int(m.group(1)) if (m := re.search(r"(\d+)\s*[–-]", name)) else "",
            infrastructure=cells.get("Altyapı"),
            commitment_months="", url=TURKNET + "/tarifelerimiz",
        ))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- türk telekom

def turktelekom(limit):
    rows = []
    for d in tt_details("evde-internet", limit, skip=("musteri-alimina-kapatilan", "-secimi", "basvuru")):
        if d["path"].rsplit("/", 1)[-1].startswith("tum-"):  # "Tüm ... Kampanyaları" hub pages
            continue
        text = f"{d['name']} {d['content']} {d['path']}"
        rows.append(irow(
            "turktelekom", group=d["group"], product_id=d["path"], product_name=d["name"],
            price=d["price"], list_price=d["list_price"], period=d["period"] or "1_ay",
            speed_mbps=mbps(text.replace("-mbps", " mbps")),
            commitment_months=d["commitment_months"], url=d["url"],
        ))
    return rows


PROVIDERS = {"superonline": superonline, "vodafone": vodafone, "kablonet": kablonet, "milleni": milleni,
             "turknet": turknet, "turktelekom": turktelekom}
DIR_NAMES = {"superonline": "Superonline", "vodafone": "Vodafone", "kablonet": "Kablonet", "milleni": "Milleni",
             "turknet": "TurkNet", "turktelekom": "TurkTelekom"}

if __name__ == "__main__":
    run(PROVIDERS, DIR_NAMES, OUT_ROOT, FIELDS, "telecom_internet", __doc__, kind="_internet")
