"""
ICT equipment repair prices (TÜİK "Bilgi ve iletişim ekipmanı bakım / onarım ücreti").

Everything each source publishes is collected (the basket is not decided yet).
Recon 2026-10-09, docs/site-analysis/telecom/NOTES.md:
  apple        support.apple.com/ols/api/pricing/... JSON (out-of-warranty estimate per model + service),
               one parent tag per device family (iPhone, iPad, Apple Watch, AirPods; no Mac estimate in TR)
  samsung      samsung.com/tr/support/ekran-degisimi-fiyat-bilgisi/ tables (recommended repair fees)
  huawei       ccpce-de.consumer.huawei.com product tree (lv2..lv6) + cspm/queryMaterialPrice per SKU
  egemek       egemek.com.tr/iphone-servis-ucretleri table (Apple authorised service provider)
  gsmiletisim  gsmiletisim.com urun-kategori pages (independent repair shop, all brands)

Output: InflationItems/Datas/08_Communication/<Source>/<source>_repair_YYYY-MM-DD.csv
Usage:  python repair.py [--operator apple|samsung|huawei|egemek|gsmiletisim|all] [--limit N]
"""

import json
import random
import re
import time

from bs4 import BeautifulSoup

from scraper import OUT_ROOT, Blocked, Fetcher, log, row, run, tl, tr_lower

FIELDS = ["date", "operator", "group", "product_id", "product_name", "service", "price", "list_price", "url"]


def rrow(operator, model, service, price, url, group="", pid=None, list_price=None):
    return row(operator, fields=FIELDS, group=group, product_id=pid or slug(f"{model}-{service}"),
               product_name=model, service=service, price=price, list_price=list_price, url=url)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", tr_lower(text).translate(str.maketrans("çğıöşü", "cgiosu"))).strip("-")


# ---------------------------------------------------------------- apple

APPLE_API = "https://support.apple.com/ols/api/pricing/products/services/pricing-estimate"
# ponytail: parent tags captured from the /tr-tr/<device>/repair pages (set by JS, not in the HTML);
# if one returns no products, re-capture it from the browser network tab
APPLE_TAGS = {"iphone": "TAG_1754518739895", "ipad": "TAG_1750382034263",
              "watch": "TAG_1755238435489", "airpods": "TAG_1749056323568"}


def apple(limit):
    f = Fetcher("https://support.apple.com/tr-tr/repair")
    rows = []

    def walk(products, device):
        for p in products:
            for s in p.get("services") or []:
                rows.append(rrow("apple", p.get("product_loc_title", "").strip(), s.get("serviceLabel", "").strip(),
                                 tl(s.get("price")), f"https://support.apple.com/tr-tr/{device}/repair", group=device,
                                 pid=f"{p.get('product_tag_id')}-{slug(s.get('serviceLabel', ''))}"))
            walk(p.get("childrenProducts") or [], device)

    for device, tag in APPLE_TAGS.items():
        # the API answers 400 "Provide valid header's: Referer and Host" without the page's Referer (since 2026-10-09)
        f.s.headers["Referer"] = f"https://support.apple.com/tr-tr/{device}/repair"
        body = f.get(f"{APPLE_API}?locale=tr-tr&pricing_type=OOW&parent_tag_id={tag}", min_len=100)
        if body is None:
            log.warning("apple: %s tag %s is gone", device, tag)
            continue
        before = len(rows)
        walk(json.loads(body).get("products") or [], device)
        log.info("apple: %s -> %d prices", device, len(rows) - before)
        if limit and len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------- samsung

SAMSUNG = "https://www.samsung.com/tr/support/ekran-degisimi-fiyat-bilgisi/"


def samsung(limit):
    soup = BeautifulSoup(Fetcher("https://www.samsung.com/tr/").get(SAMSUNG), "html.parser")
    rows = []
    for ti, table in enumerate(soup.select("table")):
        trs = table.select("tr")
        if not trs:
            continue
        head = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) != len(head):  # the battery table carries a malformed duplicate row
                continue
            if head[:2] == ["Model Kodu", "Model Adı"]:
                code, model = re.sub(r"\s+", " ", cells[0]), cells[1]
                for service, value in zip(head[2:], cells[2:]):
                    price = tl(value) if value not in ("-", "") else None
                    if price:
                        rows.append(rrow("samsung", model, service, price, SAMSUNG, group=f"tablo-{ti + 1}",
                                         pid=f"{code.split()[0]}-{slug(service)}"))
            elif head == ["Seri", "Ücret"]:  # battery replacement per series
                rows.append(rrow("samsung", cells[0], "Batarya Değişimi", tl(cells[1]), SAMSUNG,
                                 group="batarya"))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- huawei

HUAWEI_API = "https://ccpce-de.consumer.huawei.com/ccpcmd/services/dispatch/secured/CCPC/EN"
HUAWEI_Q = "&sparePartFlag=Y&channelCode=WEBSITE&countryCode=TR&langCode=tr&country=TR&language=tr&siteCode=tr_TR"
HUAWEI_PAGE = "https://consumer.huawei.com/tr/support/sparepart-price/"


def huawei(limit):
    f = Fetcher(HUAWEI_PAGE, headers={"Referer": "https://consumer.huawei.com/",
                                      "Origin": "https://consumer.huawei.com"})

    def jsonp(text):  # responses are wrapped in "( ... )"
        return json.loads(text[text.find("{"):text.rfind("}") + 1])

    def children(level, pid):
        body = f.get(f"{HUAWEI_API}/ccpc/queryNewCommodityList/1000?productLevel={level}&productId={pid}{HUAWEI_Q}",
                     min_len=50)
        return ((jsonp(body).get("responseData") or {}).get("productList") or []) if body else []

    def price(sku):
        for _ in range(2):
            time.sleep(random.uniform(1.5, 3.5))
            f.n += 1
            r = f.s.post(f"{HUAWEI_API}/cspm/queryMaterialPrice/1000", timeout=40,
                         headers={"Content-Type": "application/json"},
                         data=json.dumps({"countryCode": "TR", "languageCode": "tr", "timeZone": "GMT+03:00",
                                          "skuCode": sku, "siteCode": "tr_TR"}))
            if r.status_code == 200:
                return jsonp(r.text).get("responseData") or {}
        raise Blocked(f"huawei price {sku}: HTTP {r.status_code}")

    rows = []
    for cat in children("lv2", "CMCG10000001"):           # Telefon, Bilgisayar, Tablet, ...
        for series in children("lv3", cat["productId"]):
            for model in children("lv4", series["productId"]):
                if model.get("hasPriceFlag") != "Y":
                    continue
                # colour/memory variants (lv5 -> lv6) share the repair price: the first SKU is enough
                node, level = model, 4
                while level < 6:
                    kids = children(f"lv{level + 1}", node["productId"])
                    if not kids:
                        break
                    node, level = kids[0], level + 1
                data = price(node["productId"])
                for cls in data.get("serviceMaClassifyList") or []:
                    for item in cls.get("itemTypeInfoList") or []:
                        for p in item.get("serviceItemPrice") or []:
                            rows.append(rrow(
                                "huawei", model["displayName"], item.get("sparePartTypeLocalDesc") or "",
                                tl(p.get("totalPrice")), HUAWEI_PAGE, group=f"{cat['displayName']}/{series['displayName']}",
                                pid=f"{model['productId']}-{p.get('itemCode')}"))
                if limit and len(rows) >= limit:
                    return rows
            log.info("huawei: %s / %s done, %d prices", cat["displayName"], series["displayName"], len(rows))
    return rows


# ---------------------------------------------------------------- egemek

EGEMEK = "https://egemek.com.tr/iphone-servis-ucretleri"


def egemek(limit):
    soup = BeautifulSoup(Fetcher("https://egemek.com.tr/").get(EGEMEK), "html.parser")
    rows = []
    for table in soup.select("table"):
        trs = table.select("tr")
        head = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])] if trs else []
        if not head or "Modeli" not in head[0]:
            continue
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            for service, value in zip(head[1:], cells[1:]):
                if tl(value):
                    rows.append(rrow("egemek", cells[0], service, tl(value), EGEMEK, group="iphone"))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- gsm iletişim

GSM = "https://www.gsmiletisim.com"


def gsmiletisim(limit):
    f = Fetcher(GSM + "/")
    cats = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", f.get(GSM + "/urun-kategori-sitemap.xml", min_len=500))
    log.info("gsmiletisim: %d categories", len(cats))
    rows, seen = [], set()
    for cat in cats:
        group = cat.rstrip("/").rsplit("/", 1)[-1]
        # a category page shows 99 cards; the rest sit on <cat>/page/N/ (infinite scroll, no "next" link)
        for n in range(1, 50):
            html = f.get(cat if n == 1 else f"{cat.rstrip('/')}/page/{n}/")
            cards = BeautifulSoup(html, "html.parser").select("li.product") if html else []
            if not cards:
                break
            for li in cards:
                a = li.select_one("h2.product-title a")
                p = li.select_one("[itemprop=price]")
                if not (a and p) or a["href"] in seen:
                    continue
                seen.add(a["href"])
                price = tl(p.get("content") or p.get_text())
                if not price:  # "fiyat sorunuz" cards carry no price
                    continue
                name = a.get_text(" ", strip=True)
                # "İPHONE 17 PRO MAX EKRAN DEĞİŞİMİ" / "Xiaomi Mi 8 SE arka kamera değişimi" -> model + service;
                # matched on the Turkish-lowercased name (tr_lower keeps the length, so indices map back);
                # the earliest keyword wins, so multi-word services ("arka kamera") are listed explicitly
                m = re.search(r"\s((?:ön cam|ön kamera|arka kamera|arka kapak|arka cam|ekran|lcd|dokunmatik|batarya|"
                              r"pil|kamera|şarj|soket|kulaklık|hoparlör|mikrofon|titreşim|sim kart|wifi|wi-fi|"
                              r"anten|tamir|onarım|anakart|kasa|tuş|güç|ses|face id|touch id|parmak izi|"
                              r"yazılım|sıvı temas|su temas|cam)\b)", tr_lower(name))
                model, service = (name[:m.start()].strip(), name[m.start():].strip()) if m else (name, "")
                rows.append(rrow("gsmiletisim", model, service, price, a["href"],
                                 group=group, pid=a["href"].rstrip("/").rsplit("/", 1)[-1]))
            if len(cards) < 99:
                break
        if limit and len(rows) >= limit:
            break
    return rows


SOURCES = {"apple": apple, "samsung": samsung, "huawei": huawei, "egemek": egemek, "gsmiletisim": gsmiletisim}
DIR_NAMES = {"apple": "Apple", "samsung": "Samsung", "huawei": "Huawei", "egemek": "Egemek",
             "gsmiletisim": "GSMIletisim"}

if __name__ == "__main__":
    run(SOURCES, DIR_NAMES, OUT_ROOT, FIELDS, "telecom_repair", __doc__, kind="_repair")
