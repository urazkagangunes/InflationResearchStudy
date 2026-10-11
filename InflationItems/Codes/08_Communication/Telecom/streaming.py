"""
Streaming / digital content subscription prices (TÜİK "Dijital içerik / streaming platform aboneliği").

One public page per service, plain HTTP (recon 2026-10-09, docs/site-analysis/telecom/NOTES.md):
  netflix     help.netflix.com/tr/node/24926 "Planlar ve fiyatlandırma" text
  disney      disneyplus.com/tr-tr plan cards (monthly + yearly)
  hbomax      hbomax.com/tr/tr plan cards
  prime       amazon.com.tr/prime ("Prime sadece 69,90₺/ay", includes Prime Video)
  appletv     apple.com/tr/apple-tv-plus footnote ("aylık 89,99 TL üyelik ücreti")
  youtube     youtube.com/premium ytInitialData optionItemRenderer entries
  spotify     spotify.com/tr-tr/premium plan texts
  mubi        mubi.com/tr/tr __NEXT_DATA__ subscriptionPlans
  tvplus      tvplus.com.tr/paketler RSC payload (stickyBarData + Turkcell x HBO Max packages)
  tivibu      tivibu.com.tr/paketler .item-container / .priceSelect cards
  tod         todtv.com.tr/satinal .package-card cards
  gain        destek.gain.tv/sss.html FAQ ("Aylık abonelik 149 TL, yıllık abonelik ise 1.490 TL")
  tabii       tabii.com/tr rendered plan cards via one headless Chrome visit (price is filled client-side)
Not collected: Exxen and Hepsiburada Premium (price only after sign-up / login), Paramount+ (not sold
in Türkiye).

Output: InflationItems/Datas/08_Communication/<Service>/<service>_YYYY-MM-DD.csv
Usage:  python streaming.py [--operator netflix|...|all] [--limit N]
"""

import json
import re

from bs4 import BeautifulSoup

from scraper import OUT_ROOT, Blocked, Fetcher, row, run, tl, tr_lower

FIELDS = ["date", "operator", "group", "product_id", "product_name", "price", "list_price", "period", "url"]


def srow(operator, name, price, period, url, group="", list_price=None, pid=None):
    return row(operator, fields=FIELDS, group=group, product_id=pid or slug(name), product_name=name,
               price=tl(price) if isinstance(price, str) else price,
               list_price=tl(list_price) if isinstance(list_price, str) else list_price,
               period=period, url=url)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", tr_lower(text).translate(str.maketrans("çğıöşü", "cgiosu"))).strip("-")


def text_of(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.select("script,style,svg,noscript"):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def page(home, url, **kw):
    # Turkish locale: several services localise prices/plan names by Accept-Language
    html = Fetcher(home, headers={"Accept-Language": "tr-TR,tr;q=0.9"}).get(url, **kw)
    if html is None:
        raise Blocked(f"{url}: 404")
    return html


def need(rows, what):
    if not rows:
        raise Blocked(f"{what}: price pattern not found (page layout changed?)")
    return rows


# ---------------------------------------------------------------- services

def netflix(limit):
    url = "https://help.netflix.com/tr/node/24926"
    t = text_of(page("https://help.netflix.com/tr", url))
    return need([srow("netflix", f"{m.group(1)} plan", m.group(2), "1_ay", url)
                 for m in re.finditer(r"((?:Reklamlı )?(?:Temel|Standart|Premium)) plan[^:]{0,30}: Ayda ([\d.,]+) TL", t)],
                "netflix")


def disney(limit):
    url = "https://www.disneyplus.com/tr-tr"
    t = text_of(page(url, url))
    names = re.findall(r"DISNEY\+ (REKLAMLI|REKLAMSIZ)", t)[:2]
    monthly = re.findall(r"([\d.,]+) TL / ay", t)[:2]
    yearly = re.findall(r"([\d.,]+) TL / yıl", t)[:2]
    label = {"REKLAMLI": "Reklamlı", "REKLAMSIZ": "Reklamsız"}
    rows = [srow("disney", f"Disney+ {label[n]} aylık", p, "1_ay", url) for n, p in zip(names, monthly)]
    rows += [srow("disney", f"Disney+ {label[n]} yıllık", p, "1_yil", url) for n, p in zip(names, yearly)]
    return need(rows, "disney")


def hbomax(limit):
    url = "https://www.hbomax.com/tr/tr"
    t = text_of(page(url, url))
    seen, rows = set(), []
    for name, price, per in re.findall(r"(Temel|Standart|Özel|Premium|Reklamlı)\s*₺([\d.,]+)\s*/\s*(ay|yıl)", t):
        if (name, per) not in seen:
            seen.add((name, per))
            rows.append(srow("hbomax", f"HBO Max {name} {'aylık' if per == 'ay' else 'yıllık'}", price,
                             "1_ay" if per == "ay" else "1_yil", url))
    return need(rows, "hbomax")


def prime(limit):
    url = "https://www.amazon.com.tr/prime"
    t = text_of(page(url, url))  # the amazon.com.tr homepage answers a 202 bot interstitial
    m = re.search(r"Prime sadece ([\d.,]+)\s*₺\s*/\s*ay", t)
    return need([srow("prime", "Amazon Prime (Prime Video dahil) aylık", m.group(1), "1_ay", url)] if m else [], "prime")


def appletv(limit):
    url = "https://www.apple.com/tr/apple-tv-plus/"
    t = text_of(page("https://www.apple.com/tr/", url))
    m = re.search(r"aylık ([\d.,]+) TL üyelik ücreti", t)
    return need([srow("appletv", "Apple TV+ aylık", m.group(1), "1_ay", url)] if m else [], "appletv")


def youtube(limit):
    url = "https://www.youtube.com/premium"
    html = page("https://www.youtube.com/", url)
    rows, section = {}, ""
    # ytInitialData: optionSectionRenderer (Premium Lite / Premium / Aylık planlar / Yıllık planlar)
    # followed by optionItemRenderer entries (plan title + subtitle runs with the price)
    for m in re.finditer(r'"optionSectionRenderer":\{"title":\{"runs":\[\{"text":"([^"]+)"'
                         r'|"optionItemRenderer":\{"title":\{"runs":\[\{"text":"([^"]+)"\}\]\},"subtitle":\{"runs":(\[.*?\])\}',
                         html):
        if m.group(1):
            section = m.group(1)
            continue
        runs = "".join(r.get("text", "") for r in json.loads(m.group(3)))
        price = re.search(r"₺([\d.,]+)\D*$", runs.replace("⁠", ""))  # word joiners around "/ay"
        if not price:
            continue
        yearly = "12 ay" in runs
        tier = "Premium Lite" if "Lite" in section else "Premium"
        # the page repeats plans under several sections ("Aile" / "Aile planı", "Yıllık" / "1 yıllık bireysel")
        plan = "Bireysel" if yearly else m.group(2).replace(" planı", "")
        name = f"YouTube {tier} {plan}" + (" yıllık" if yearly else "")
        rows.setdefault(name, srow("youtube", name, price.group(1), "1_yil" if yearly else "1_ay", url))
    return need(list(rows.values()), "youtube")


def spotify(limit):
    url = "https://www.spotify.com/tr-tr/premium/"
    t = text_of(page("https://www.spotify.com/tr-tr/", url))
    rows = {}
    for plan in ("Bireysel", "Öğrenci", "Duo", "Aile"):
        # skip the "İlk 1 ay ₺0" trial: take "Sonra ayda ₺X" or "₺X / ay"
        m = re.search(rf"Premium {plan}\b.{{0,120}}?(?:Sonra ayda ₺\s?([\d.,]+)|₺\s?([\d.,]+)\s*/\s*ay)", t)
        if m:
            rows[plan] = srow("spotify", f"Spotify Premium {plan}", m.group(1) or m.group(2), "1_ay", url)
    return need(list(rows.values()), "spotify")


def mubi(limit):
    url = "https://mubi.com/tr/tr"
    html = page(url, url)
    plans = json.JSONDecoder().raw_decode(html, html.index('"subscriptionPlans":') + len('"subscriptionPlans":'))[0]
    rows = [srow("mubi", f"MUBI {p.get('display_name') or key} ({key})", p["price_in_cents"] / 100,
                 "1_yil" if key == "year" else "1_ay", url, pid=key)
            for key, p in plans.items() if isinstance(p, dict) and p.get("price_in_cents")]
    return need(rows, "mubi")


def tvplus(limit):
    url = "https://tvplus.com.tr/paketler"
    html = page("https://tvplus.com.tr/", url)
    rsc = "".join(json.loads('"' + c + '"') for c in
                  re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S))
    rows = []
    m = re.search(r'"priceMonthly":"([\d.,]+)","priceYearly":"([\d.,]+)"', rsc)
    if m:
        rows.append(srow("tvplus", "TV+ aylık plan", m.group(1), "1_ay", url))
        rows.append(srow("tvplus", "TV+ yıllık plan (aylık karşılığı)", m.group(2), "1_ay", url, pid="tv-yillik-plan"))
    for p in re.finditer(r'\{"package_id":"(\d+)","name":"([^"]+)".*?"campaignText":"([^"]*)"', rsc):
        after = re.search(r"sonrasında ([\d.,]+)₺", p.group(3))
        first = re.search(r"ilk \d+ ay ([\d.,]+)₺", p.group(3))
        if after:
            rows.append(srow("tvplus", p.group(2), after.group(1), "1_ay", url, group="turkcell-hbo-max",
                             pid=p.group(1)))
            if first:
                rows[-1]["product_name"] += f" (kampanya: ilk ay(lar) {first.group(1)} TL)"
    return need(rows, "tvplus")


def tivibu(limit):
    url = "https://www.tivibu.com.tr/paketler"
    soup = BeautifulSoup(page("https://www.tivibu.com.tr/", url), "html.parser")
    rows = []
    for card in soup.select(".item-container[package-id]"):
        name = card["package-id"]
        for li in card.select(".priceSelect"):
            title = li.select_one(".title").get_text(" ", strip=True)
            price = li.select_one(".price")
            old = li.select_one(".oldprice")
            if not price:
                continue
            pid = re.search(r"ProductId=(\d+)", li.get("redirecturl", "") or li.get("redirectUrl", ""))
            rows.append(srow("tivibu", f"{name} {tr_lower(title)}", price.get_text(strip=True),
                             "1_yil" if "Yıllık" in title else "1_ay", url,
                             list_price=old.get_text(strip=True) if old else None,
                             pid=pid.group(1) if pid else None))
    return need(rows, "tivibu")


def tod(limit):
    url = "https://www.todtv.com.tr/satinal"
    # the homepage redirects to a small "/mac-basliyor/" splash on match days -> open the shop page directly
    soup = BeautifulSoup(page(url, url), "html.parser")
    rows, seen = [], set()
    for card in soup.select(".package-card[data-item-name]"):
        name = card["data-item-name"]
        for pr in card.select(".subscribe-accordion-collapse-pricing"):
            price = pr.select_one(".subscribe-accordion-collapse-price")
            inst = (pr.select_one(".subscribe-accordion-collapse-installment") or pr).get_text(" ", strip=True)
            if not price:
                continue
            # "/Ayda 12 TAKSİTLE" = yearly/seasonal plan paid in instalments, "/Aylık" = cancel-anytime monthly
            kind = f"taksitli ({tr_lower(inst)})" if inst else "aylık"
            key = (name, kind)
            if key in seen:
                continue
            seen.add(key)
            price_text = price.get_text(strip=True)
            later = re.search(r"Sonraki Aylar\s*([\d.,]+)\s*₺", card.get_text(" ", strip=True))
            if not inst and later:  # "İlk Ay 9₺ Sonraki Aylar 129₺": record the regular monthly price
                kind, price_text = f"aylık (ilk ay {price_text})", later.group(1)
            rows.append(srow("tod", f"TOD {name} {kind}", price_text, "1_ay", url,
                             group=card.get("data-item-category", ""),
                             pid=f"{card.get('data-item-id')}-{'taksit' if inst else 'aylik'}"))
    return need(rows, "tod")


def gain(limit):
    url = "https://destek.gain.tv/sss.html"
    t = text_of(page("https://destek.gain.tv/", url, min_len=1000))
    m = re.search(r"Aylık abonelik ([\d.,]+) TL, yıllık abonelik ise ([\d.,]+) TL", t)
    return need([srow("gain", "GAİN aylık", m.group(1), "1_ay", url),
                 srow("gain", "GAİN yıllık", m.group(2), "1_yil", url)] if m else [], "gain")


def tabii(limit):
    # The plan cards are filled client-side: the public products API
    # (eu1.tabii.com/apigateway/subscriptions/v1/public/products/) returns only the free tier and the
    # Premium price comes from a call that could not be isolated -> read the rendered page instead.
    from internet import browser_visit

    url = "https://www.tabii.com/tr"
    _, _, text = browser_visit(url, until=r"[1-9][\d.]*,\d{2}\s*₺")
    rows = [srow("tabii", f"tabii {name.strip().title()}", price, "1_ay", url)
            for name, price in re.findall(r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ ]{2,30})\s+([\d.]+,\d{2})\s*₺\s*/\s*ay", text)
            if tl(price)]
    return need(rows, "tabii")


SERVICES = {"netflix": netflix, "disney": disney, "hbomax": hbomax, "prime": prime, "appletv": appletv,
            "youtube": youtube, "spotify": spotify, "mubi": mubi, "tvplus": tvplus, "tivibu": tivibu,
            "tod": tod, "gain": gain, "tabii": tabii}
DIR_NAMES = {"netflix": "Netflix", "disney": "DisneyPlus", "hbomax": "HBOMax", "prime": "AmazonPrime",
             "appletv": "AppleTVPlus", "youtube": "YouTubePremium", "spotify": "Spotify", "mubi": "MUBI",
             "tvplus": "TVPlus", "tivibu": "Tivibu", "tod": "TOD", "gain": "GAIN", "tabii": "Tabii"}

if __name__ == "__main__":
    run(SERVICES, DIR_NAMES, OUT_ROOT, FIELDS, "telecom_streaming", __doc__)
