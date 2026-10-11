"""
Mobile operator tariff scraper (TÜİK 0832001 "Cep telefonu görüşme ücreti").

Operators and where the data lives (recon 2026-10-08, docs/site-analysis/telecom/NOTES.md):
  turkcell     Next.js pages; package list in __NEXT_DATA__ dehydratedState
  vodafone     tariffs: Next.js RSC payload (self.__next_f) objects with "id"+"price";
               add-ons: server-rendered .addon--item cards per tab
  turktelekom  listing pages only render 12 cards (the paging XHR lives under the
               robots-disallowed /_layouts/), so tariff/package URLs come from
               sitemap.xml and each detail page's JSON-LD Product + pricing table
  netgsm       one static page, .paket-card blocks (no package names / ids)

All four answer a Chrome-TLS curl_cffi client; no browser is used.

Output: InflationItems/Datas/08_Communication/<Operator>/<operator>_YYYY-MM-DD.csv
Usage:  python scraper.py [--operator turkcell|vodafone|turktelekom|netgsm|all] [--limit N]
"""

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_ROOT = REPO_ROOT / "InflationItems" / "Datas" / "08_Communication"
LOG_DIR = REPO_ROOT / "logs"
TODAY = date.today().isoformat()

FIELDS = ["date", "operator", "segment", "group", "product_id", "product_name", "price",
          "list_price", "period", "data_gb", "minutes", "sms", "commitment_months", "url"]

log = logging.getLogger("telecom")


class Blocked(Exception):
    pass


# ---------------------------------------------------------------- helpers

def tr_lower(s):
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


def tl(s):
    """'1.309 ₺' -> 1309.0, '74,99' -> 74.99, 'Ücretsiz' -> 0.0, '' -> None."""
    if s is None:
        return None
    s = str(s)
    if "ücretsiz" in tr_lower(s):
        return 0.0
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s)


def norm_period(text):
    """'Aylık' -> 1_ay, '28 Günlük' -> 28_gun, '/3 ay' -> 3_ay, 'haftalık 3 GB' -> 1_hafta."""
    m = re.search(r"(?:(\d+)\s*)?\b(gün|hafta|ay|yıl)(?:lık|lik|luk|lük)?\b", tr_lower(text))
    if not m:
        return ""
    unit = {"gün": "gun", "hafta": "hafta", "ay": "ay", "yıl": "yil"}[m.group(2)]
    return f"{m.group(1) or 1}_{unit}"


def quota(text, unit):
    """First '<n> GB|DK|SMS' in text; 'SINIRSIZ <unit>' -> 'sinirsiz'."""
    t = tr_lower(text)
    words = {"gb": r"gb", "dk": r"(?:dk|dakika)", "sms": r"sms"}[unit]
    if re.search(r"(sınırsız|limitsiz)\s*" + words, t):
        return "sinirsiz"
    m = re.search(r"(\d[\d.,]*)\s*" + words + r"\b", t)
    if m:
        return m.group(1).replace(".", "").replace(",", ".")
    if unit == "gb":
        m = re.search(r"(\d+)\s*mb\b", t)
        if m:
            return round(int(m.group(1)) / 1024, 3)
    return ""


def commitment(text):
    m = re.search(r"(\d+)\s*(?:ay boyunca|ay taahhüt|fatura dönemi)", tr_lower(text))
    return int(m.group(1)) if m else ""


def row(operator, fields=FIELDS, **kw):
    r = dict.fromkeys(fields, "")
    r.update(date=TODAY, operator=operator, **{k: ("" if v is None else v) for k, v in kw.items()})
    return r


class Fetcher:
    """One session per operator: homepage first, then serial requests with jitter."""

    def __init__(self, home, verify=True, headers=None):
        self.s = requests.Session(impersonate="chrome124", verify=verify)
        self.s.headers.update(headers or {})
        self.n = 0
        self.get(home)

    def get(self, url, min_len=5000):
        for attempt in range(4):
            if self.n:
                time.sleep(random.uniform(1.5, 3.5))
            self.n += 1
            try:
                r = self.s.get(url, timeout=40)
            except Exception as e:  # network error -> retry
                log.warning("GET %s failed: %s", url, e)
                time.sleep(10 * 2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                wait = int(r.headers.get("Retry-After") or 10 * 2 ** attempt)
                log.warning("GET %s -> %s, retry in %ss", url, r.status_code, wait)
                time.sleep(min(wait, 300))
                continue
            if r.status_code == 404:
                return None
            body = r.text
            if r.status_code == 403 or len(body) < min_len or re.search(
                    r"cf-chl-|px-captcha|_Incapsula_Resource|<title>Access Denied", body[:20000], re.I):
                raise Blocked(f"{url} -> {r.status_code}, {len(body)} bytes")
            return body
        raise Blocked(f"{url}: retries exhausted")


# ---------------------------------------------------------------- turkcell

TURKCELL = "https://www.turkcell.com.tr"
TURKCELL_PAGES = [  # (path, segment for paymentType BOTH)
    ("/paket-ve-tarifeler/faturali-hat", "faturali"),
    ("/paket-ve-tarifeler/hazir-kart", "faturasiz"),
    ("/paket-ve-tarifeler/yurt-disinda-kullanim", "faturali"),
    ("/paket-ve-tarifeler/yurt-disini-arama", "faturali"),
]


def turkcell(limit):
    f = Fetcher(TURKCELL)
    rows = []
    for path, both in TURKCELL_PAGES:
        html = f.get(TURKCELL + path)
        if html is None:
            log.warning("turkcell: %s is 404", path)
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise Blocked(f"turkcell {path}: no __NEXT_DATA__")
        queries = json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]["queries"]
        for q in queries:
            data = q["state"].get("data")
            if not isinstance(data, dict):
                continue
            for p in data.get("packages") or []:
                pr = p.get("price") or {}
                if pr.get("amount") in (None, ""):
                    continue
                ben = {b.get("type"): f"{b.get('value')} {b.get('unitValue')}" for b in p.get("benefits") or []}
                disc = pr.get("discountPriceDouble") or 0
                price, lst = (disc, pr.get("amountDouble")) if disc else (tl(pr["amount"]), None)
                raw_unit = pr.get("priceTimeUnit") or ""  # also per-unit prices: DAKİKA, KB, SMS, GB
                unit = {"AY": "ay", "HAFTA": "hafta", "GÜN": "gun", "YIL": "yil"}.get(raw_unit, tr_lower(raw_unit))
                rows.append(row(
                    "turkcell",
                    segment={"POSTPAID": "faturali", "PREPAID": "faturasiz"}.get(p.get("paymentType"), both),
                    group=p.get("endpoint", "").rsplit("/", 2)[-2],
                    product_id=p["id"],
                    product_name=p.get("title", "").strip(),
                    price=price, list_price=lst,
                    period=f"{pr.get('priceTime') or 1}_{unit}" if unit else "",
                    data_gb=quota(ben.get("INTERNET", ""), "gb"),
                    minutes=quota(ben.get("VOICE", ""), "dk"),
                    sms=quota(ben.get("SMS", ""), "sms"),
                    commitment_months=pr.get("initialPeriodMonths"),
                    url=p.get("fullUrl"),
                ))
        if limit and len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------- vodafone

VODAFONE = "https://www.vodafone.com.tr"
VODAFONE_TARIFF_PAGES = [
    ("/numara-tasima-yeni-hat/tarifeler/NEW/postpaid/ALL", "faturali"),
    ("/numara-tasima-yeni-hat/tarifeler/NEW/prepaid/ALL", "faturasiz"),
]
VODAFONE_ADDON_TABS = ["internet", "konusma", "mesaj", "sinirsiz", "yurt-disi", "durma-ozelligi",
                       "ucretsiz", "butce-dostu-paketler", "populer-paketler"]


def vodafone(limit):
    f = Fetcher(VODAFONE)
    dec = json.JSONDecoder()
    rows = []
    for path, segment in VODAFONE_TARIFF_PAGES:
        html = f.get(VODAFONE + path)
        rsc = "".join(json.loads('"' + c + '"') for c in
                      re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S))
        seen = set()
        for m in re.finditer(r'\{"id":(\d+),', rsc):
            try:
                o, _ = dec.raw_decode(rsc, m.start())
            except ValueError:
                continue
            pr = o.get("price")
            if not isinstance(pr, dict) or not isinstance(pr.get("value"), dict) or o["id"] in seen:
                continue
            seen.add(o["id"])
            v = pr["value"]
            base = tl(v.get("base"))
            price = tl(v.get("discounted"))
            price = base if price is None else price
            d = o.get("data") or {}
            gb = d.get("value", "")
            if isinstance(d.get("extra"), dict):  # FreeZone "5 GB + 5 GB HEDİYE"
                gb = f"{float(gb) + float(quota(d['extra'].get('value', ''), 'gb') or 0):g}"
            rows.append(row(
                "vodafone", segment=segment, group=o.get("type"),
                product_id=o["id"], product_name=o.get("name", "").strip(),
                price=price, list_price=base if base and base != price else None,
                period=norm_period(pr.get("period", "")),
                data_gb=quota(f"{gb} GB", "gb"),
                minutes=quota(f"{(o.get('voice') or {}).get('value', '')} DK", "dk"),
                sms=quota(f"{(o.get('sms') or {}).get('value', '')} SMS", "sms"),
                commitment_months=commitment(f"{pr.get('commitmentText')} {pr.get('summaryPriceInfo')}"),
                url=f"{VODAFONE}/numara-tasima-yeni-hat/iletisimyenigelen/tariffId/{o['id']}",
            ))
        if not seen:
            raise Blocked(f"vodafone {path}: no tariff objects in RSC payload")
    for segment, query in (("faturali", ""), ("faturasiz", "?type=faturasiz")):
        for tab in VODAFONE_ADDON_TABS:
            if limit and len(rows) >= limit:
                return rows
            html = f.get(f"{VODAFONE}/tarifeler/ek-paketler/{tab}{query}")
            if html is None:
                continue
            for it in BeautifulSoup(html, "html.parser").select(".addon--item"):
                name = it.select_one(".addon--item__name").get_text(" ", strip=True)
                link = it.select_one(".addon--item__footer a[href]")
                bullets = it.select_one(".addon--item__bullets")
                text = name + " " + (bullets.get_text(" ", strip=True) if bullets else "")
                rows.append(row(
                    "vodafone", segment=segment, group=f"ek-paket/{tab}",
                    product_id=link["href"].rstrip("/").rsplit("/", 1)[-1] if link else name,
                    product_name=name,
                    price=tl(it.select_one(".addon--item__price").get_text(" ", strip=True)),
                    period=norm_period(name),
                    data_gb=quota(name, "gb"), minutes=quota(text, "dk"), sms=quota(text, "sms"),
                    url=VODAFONE + link["href"] if link else "",
                ))
    return rows


# ---------------------------------------------------------------- türk telekom

TT = "https://bireysel.turktelekom.com.tr"
TT_SKIP = ("kampanya", "musteri-alimina-kapatilan", "-secimi", "basvuru")


def tt_segment(group):
    if "faturasizdan" in group:
        return "faturali"
    if "faturasiz" in group:
        return "faturasiz"
    return "faturali" if "faturali" in group else ""


def tt_details(section, limit, skip=TT_SKIP, depth=1):
    """Yield parsed Türk Telekom detail pages listed in sitemap.xml (>= `depth` slashes after /<section>/).

    Listing pages render only 12 cards and page through the robots-disallowed
    /_layouts/ XHR, so every tariff/package page is read on its own instead."""
    f = Fetcher(TT)
    sitemap = f.get(TT + "/sitemap.xml", min_len=1000)
    marker = f"/{section}/"
    urls = sorted({u for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap)
                   if marker in u and not any(s in u for s in skip)
                   and u.split(marker, 1)[1].count("/") >= depth})
    log.info("turktelekom/%s: %d candidate detail URLs from sitemap", section, len(urls))
    n = 0
    for i, url in enumerate(urls, 1):
        if limit and n >= limit:
            break
        if i % 50 == 0:
            log.info("turktelekom/%s: %d/%d pages, %d products", section, i, len(urls), n)
        html = f.get(url)
        if html is None:
            continue
        product = None
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                o = json.loads(blob)
            except ValueError:
                continue
            if isinstance(o, dict) and o.get("@type") == "Product" and o.get("offers"):
                product = o
        if not product:  # info page, not a tariff/package
            continue
        if "müşteri alımına kapatılmıştır" in html:  # old campaign page still listed in the sitemap
            continue
        soup = BeautifulSoup(html, "html.parser")
        note = soup.select_one('[id$="_divPrice"] .note')
        term = soup.select_one('[id$="_nonPricingTableDiv"] > p')
        lst = None
        content = ""
        for tr in soup.select("table.properties-table tr"):
            th, td = tr.find("th"), tr.find("td")
            if not (th and td):
                continue
            head = tr_lower(th.get_text(" ", strip=True))
            if "taahhütsüz" in head and "fiyat" in head:
                lst = tl(td.get_text(" ", strip=True))
            elif "içeriği" in head:
                content = td.get_text(" ", strip=True)
        path = url.split(marker, 1)[1]
        price = tl(product["offers"].get("price"))
        n += 1
        yield dict(
            url=url, path=path, group=path.rsplit("/", 1)[0], name=product.get("name", "").strip(),
            price=price, list_price=lst if lst and lst != price else None, content=content, soup=soup,
            period=norm_period(note.get_text(" ", strip=True) if note else ""),
            commitment_months=commitment(term.get_text(" ", strip=True) if term else ""),
        )


def turktelekom(limit):
    rows = []
    for d in tt_details("mobil", limit, depth=2):  # /mobil/<a>/<b>/<slug>; shallower are hub pages
        text = f"{d['name']} {d['content']}"
        rows.append(row(
            "turktelekom", segment=tt_segment(d["group"]), group=d["group"], product_id=d["path"],
            product_name=d["name"], price=d["price"], list_price=d["list_price"], period=d["period"],
            data_gb=quota(text, "gb"), minutes=quota(text, "dk"), sms=quota(text, "sms"),
            commitment_months=d["commitment_months"], url=d["url"],
        ))
    return rows


# ---------------------------------------------------------------- netgsm

NETGSM = "https://www.netgsm.com.tr"


def netgsm(limit):
    f = Fetcher(NETGSM)
    html = f.get(NETGSM + "/fiyatlar/mobil-hat")
    rows = []
    for card in BeautifulSoup(html, "html.parser").select(".paket-card"):
        gb = card.select_one("h4").get_text(" ", strip=True)
        extra = card.select_one("small").get_text(" ", strip=True)
        h2 = card.select_one("h2")
        per = h2.select_one("span")
        per_text = per.get_text(strip=True) if per else ""
        if per:
            per.extract()
        name = " ".join(f"{gb} {extra}".split())
        rows.append(row(
            "netgsm", segment="faturali", group="mobil-hat",
            product_id=re.sub(r"[^a-z0-9]+", "-", tr_lower(name)).strip("-"),
            product_name=name, price=tl(h2.get_text(" ", strip=True)),
            period=norm_period(per_text),
            data_gb=quota(name, "gb"), minutes=quota(name, "dk"), sms=quota(name, "sms"),
            url=NETGSM + "/fiyatlar/mobil-hat",
        ))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- main

OPERATORS = {"turkcell": turkcell, "vodafone": vodafone, "turktelekom": turktelekom, "netgsm": netgsm}
DIR_NAMES = {"turkcell": "Turkcell", "vodafone": "Vodafone", "turktelekom": "TurkTelekom", "netgsm": "NetGSM"}


def write(out, rows, fields):
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".csv.part")
    with open(part, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(part, out)
    return out


def run(operators, dir_names, out_root, fields, log_name, doc, kind=""):
    """Shared CLI: --operator X|all, --limit N; one CSV per operator; exit 1 if any operator failed.

    kind ("_internet", "_repair") goes into the file name: these share retailer folders with other
    08_Communication scrapers (Vodafone mobile, Huawei products), so the date alone would collide."""
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--operator", choices=[*operators, "all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="stop after ~N rows per operator (bounded test run)")
    args = ap.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(LOG_DIR / f"{log_name}_{TODAY}.log", encoding="utf-8")])

    failed = []
    for name in (operators if args.operator == "all" else [args.operator]):
        try:
            rows = operators[name](args.limit)
        except Exception as e:  # one operator failing must not stop the others
            log.error("%s FAILED: %s: %s", name, type(e).__name__, e)
            failed.append(name)
            continue
        unique = {}
        for r in rows:
            unique.setdefault((r.get("segment", ""), str(r["product_id"])), r)
        rows = [r for r in unique.values() if r["price"] != ""]
        if args.limit:
            rows = rows[:args.limit]
        if not rows:  # keep the last good snapshot instead of an empty CSV
            log.error("%s FAILED: 0 rows parsed", name)
            failed.append(name)
            continue
        # a bounded test run must never overwrite the day's full snapshot
        suffix = "_limit" if args.limit else ""
        out = write(out_root / dir_names[name] / f"{name}{kind}_{TODAY}{suffix}.csv", rows, fields)
        log.info("%s: %d rows -> %s", name, len(rows), out.relative_to(REPO_ROOT))
    if failed:
        log.error("failed operators: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    run(OPERATORS, DIR_NAMES, OUT_ROOT, FIELDS, "telecom", __doc__)
