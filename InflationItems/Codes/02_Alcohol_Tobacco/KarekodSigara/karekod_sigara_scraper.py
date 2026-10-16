"""Karekod'un sigara ve sarmalik tutun tablolarini gunluk CSV'ye yaz.

python InflationItems/Codes/02_Alcohol_Tobacco/KarekodSigara/karekod_sigara_scraper.py
Ilk dort sutun ortak fiyat formatidir. Her gun ayri dosya yazilir.
Ayrintili listeler esas alinir; genel ozet ve fiyat araliklari alinmaz.
HD renk/boy satiri kullanici karariyla alti urune ayrilir. Rapor/yedek uretilmez.
"""

import argparse
import csv
import logging
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = "https://www.karekod.org/blog/sigara-fiyatlari-2026/"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "Datas/02_Alcohol_Tobacco/KarekodSigara"
TIMEZONE = ZoneInfo("Europe/Istanbul")
FIELDS = (
    "product_name", "price", "category_number", "sub_category_number",
    "volume_ml", "packaging_type", "package_count", "deposit_status", "category",
    "source_url", "collected_at", "price_date", "weight_g", "brand", "producer_group",
)
LOGGER = logging.getLogger("karekod_sigara")
NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
PRICE_RE = re.compile(rf"(?:₺\s*({NUMBER})|({NUMBER})\s*(?:TL|₺))", re.I)
WEIGHT_RE = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*(?:\(\s*)?(?:gram|gr|g)\b(?:\s*\))?", re.I)
MONTHS = dict(zip("ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split(), range(1, 13)))
DATE_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b")
GROUP_PATTERNS = (
    (r"\bjti\b", "JTI"), (r"\bbat\b", "BAT"),
    (r"imperial", "Imperial Tobacco"), (r"philip morris", "Philip Morris"),
    (r"captain black", "Captain Black"), (r"t\s*&\s*t", "T&T"),
    (r"vtn", "VTN Tobacco"), (r"kt\s*&\s*g|esse", "KT&G"),
    (r"instark", "Instark / JXB"),
)
REQUIRED_GROUPS = {"JTI", "BAT", "Imperial Tobacco", "Philip Morris", "Captain Black",
                   "T&T", "VTN Tobacco", "KT&G", "Instark / JXB"}
BRAND_GROUPS = {
    "Winston": "JTI", "Camel": "JTI", "LD": "JTI", "Monte Carlo": "JTI",
    "Kent": "BAT", "Rothmans": "BAT", "Tekel 2000": "BAT", "Tekel 2001": "BAT",
    "Viceroy": "BAT", "Pall Mall": "BAT", "Maltepe": "BAT", "Samsun": "BAT",
    "Davidoff": "Imperial Tobacco", "Bianca": "Imperial Tobacco", "Polo": "Imperial Tobacco", "West": "Imperial Tobacco",
    "Parliament": "Philip Morris", "Marlboro": "Philip Morris", "Muratti": "Philip Morris",
    "Lark": "Philip Morris", "Chesterfield": "Philip Morris", "L&M": "Philip Morris",
    "Captain Black": "Captain Black",
    "Violet": "T&T", "Winner": "T&T", "HD": "T&T", "President": "T&T", "Vigor": "T&T",
    "Point": "T&T", "Medley": "T&T", "MMC": "T&T", "Hazar": "T&T", "Toros 2005": "T&T",
    "Borton": "VTN Tobacco", "Wentor": "VTN Tobacco", "Sitey": "VTN Tobacco", "Calbor": "VTN Tobacco",
    "Esse": "KT&G", "Raison": "KT&G", "Instark": "Instark / JXB", "JXB": "Instark / JXB",
}
BRANDS = sorted(BRAND_GROUPS, key=len, reverse=True)
COLORS = {"blue", "gray", "grey", "white", "black", "ivory", "burgundy", "navy", "sky",
          "red", "brown", "yellow", "dark blue", "deep blue"}
VARIANT_ENDINGS = COLORS | {"dore", "rouge", "tf", "long"}


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).replace("’", "'").split())


def key(text):
    return normalize(text).replace("İ", "i").casefold()


def parse_price(text):
    match = PRICE_RE.fullmatch(normalize(text))
    if not match:
        return ""
    value = Decimal((match[1] or match[2]).replace(".", "").replace(",", "."))
    return f"{value:.2f}" if value > 0 else ""


def price_date(heading):
    dates = set()
    for day, month, year in DATE_RE.findall(key(heading)):
        try:
            dates.add(datetime(int(year), MONTHS[month], int(day)).date().isoformat())
        except ValueError:
            raise ValueError(f"Gecersiz liste tarihi: {heading}")
    return next(iter(dates)) if len(dates) == 1 else ""


def find_brand(name):
    folded = key(name)
    for brand in BRANDS:
        if folded == key(brand) or folded.startswith(key(brand) + " "):
            return brand
    return ""


def split_variants(name):
    """Ortak marka/seri adlarini koru; kullanicinin onayladigi HD satirini ac."""
    name = normalize(name)
    if key(name) == "hd red / blue / sky kısa-uzun":
        return [f"HD {color} {size}" for color in ("Red", "Blue", "Sky") for size in ("Kısa", "Uzun")]
    if re.search(r"tüm\s+(?:ürünler|çeşitler)", name, re.I):
        return [name]
    choices = re.split(r"\s+(?:/|&)\s+", name)
    if len(choices) == 1:
        return [name]
    # Medley / MMC / Hazar / Toros 2005 veya Muratti / Muratti Blu.
    if all(find_brand(part) for part in choices):
        return choices
    brand = find_brand(choices[0])
    if not brand:
        raise ValueError(f"Ortak markasi belirlenemeyen cesitler: {name}")
    rest = [choices[0][len(brand):].strip(), *choices[1:]]
    prefix = ""
    if key(brand) == "marlboro" and key(rest[0]) == "touch":
        prefix = "Touch"
    elif key(rest[0]) not in VARIANT_ENDINGS:
        for ending in sorted(VARIANT_ENDINGS, key=len, reverse=True):
            if key(rest[0]).endswith(" " + ending):
                prefix = rest[0][:-len(ending)].strip()
                break
    result = []
    for part in rest:
        # Touch Blue / Gray / White, Slims Ivory / White, King Size Navy / Sky.
        if prefix and key(part) in VARIANT_ENDINGS and key(part) != key(prefix):
            part = f"{prefix} {part}"
        result.append(normalize(f"{brand} {part}"))
    return result


def tobacco_attributes(name, explicit_weight=""):
    values = {Decimal(m[1].replace(",", ".")) for m in WEIGHT_RE.finditer(name + " " + explicit_weight)}
    if len(values) > 1 or any(value <= 0 for value in values):
        raise ValueError(f"Belirsiz/gecersiz gramaj: {name} {explicit_weight}")
    clean = WEIGHT_RE.sub("", name)
    clean = re.sub(r"\(?\s*Sarmalık(?:\s+Kıyılmış)?\s+Tütün\s*\)?", "", clean, flags=re.I)
    clean = re.sub(r"\(\s*\)", "", clean)
    return normalize(clean), format(next(iter(values)).normalize(), "f") if values else ""


def parse_page(html, collected_at):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.content.c-text")
    if content is None:
        raise ValueError("Karekod fiyat icerigi bulunamadi; CSV yazilmadi")
    headings, dates, observations, groups = {}, {}, [], set()
    table_count = 0

    def context():
        return [headings[level] for level in sorted(headings)]

    def producer():
        for heading in reversed(context()):
            for pattern, candidate in GROUP_PATTERNS:
                if re.search(pattern, key(heading)):
                    return candidate
        return ""

    def section_date():
        known = dates.get(max(headings), set()) if headings else set()
        return next(iter(known)) if len(known) == 1 else ""

    def add(name, raw_price, group, date, tobacco=False):
        weight = ""
        if tobacco:
            name, weight = tobacco_attributes(name)
        for variant in [name] if tobacco else split_variants(name):
            brand = find_brand(variant)
            full_name = variant
            if weight and key(variant) != "marlboro roll " + weight:
                full_name = f"{variant} {weight} g"
            observations.append({
                "product_name": full_name, "price": parse_price(raw_price),
                "category_number": "02", "sub_category_number": "0" if tobacco else "0230101",
                "volume_ml": "", "packaging_type": "", "package_count": "", "deposit_status": "",
                "category": "Sarmalık Tütün" if tobacco else "Sigara", "source_url": URL,
                "collected_at": collected_at, "price_date": date, "weight_g": weight,
                "brand": brand, "producer_group": group or BRAND_GROUPS.get(brand, ""),
                "_priority": 2, "_raw_price": raw_price,
            })

    for node in content.find_all(["h2", "h3", "h4", "p", "table"]):
        if node.name.startswith("h"):
            level = int(node.name[1])
            headings = {k: v for k, v in headings.items() if k < level}
            dates = {k: v for k, v in dates.items() if k < level}
            heading = normalize(node.get_text(" ", strip=True))
            headings[level] = heading
            date = price_date(heading)
            dates[level] = {date} if date else set()
            continue
        section = context()
        if node.name == "p":
            if node.find_parent(["table", "aside", "nav", "style"]):
                continue
            text = normalize(node.get_text(" ", strip=True))
            group = producer()
            # Yayin tarihi tum urunlerin fiyat tarihi sayilmaz.
            if group and headings:
                date = price_date(text)
                if date:
                    dates[max(headings)].add(date)
            # Camel Yellow ana JTI tablosunun hemen ardinda metin olarak veriliyor.
            match = re.fullmatch(rf"(Camel Yellow\s+\d+(?:[,.]\d+)?\s*(?:gram|gr|g))\s+sarmalık\s+kıyılmış\s+tütün\s+fiyatı\s+({NUMBER}\s*(?:TL|₺))\.?", text, re.I)
            if match and group == "JTI":
                add(match[1], match[2], group, section_date(), tobacco=True)
            continue
        table_count += 1
        if not section:
            raise ValueError(f"Tablo {table_count}: baslik bulunamadi")
        heading = key(section[-1])
        if heading.startswith("hızlı özet") or heading.startswith("güncel sigara fiyatları"):
            continue
        if re.search(r"arşiv|free shop|duty free|yıllara göre", heading):
            continue
        group = producer()
        menthol = "mentollü sigara" in heading
        if not group and not menthol:
            raise ValueError(f"Tablo {table_count}: uretici grubu bilinmiyor: {section}")
        trs = node.find_all("tr")
        if len(trs) < 2:
            raise ValueError(f"Tablo {table_count}: urun satiri bulunamadi")
        header = [normalize(c.get_text(" ", strip=True)) for c in trs[0].find_all(["td", "th"])]
        dated_columns = [(i, price_date(h)) for i, h in enumerate(header) if price_date(h)]
        date = section_date()
        if any("zam öncesi" in key(h) for h in header):
            if len(dated_columns) != 1:
                raise ValueError(f"Tablo {table_count}: yeni fiyat sutunu belirsiz")
            price_i, date = dated_columns[0]
        else:
            price_cols = [i for i, h in enumerate(header) if "fiyat" in key(h)]
            if len(price_cols) != 1:
                raise ValueError(f"Tablo {table_count}: fiyat sutunu bulunamadi: {header}")
            price_i = price_cols[0]
        if group:
            groups.add(group)
        for tr in trs[1:]:
            cells = [normalize(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
            if len(cells) != len(header) or not cells[0]:
                raise ValueError(f"Tablo {table_count}: eksik hucre veya urun adi")
            name = cells[0]
            tobacco = "sarmalık" in key(name) or "tütün fiyatı" in heading
            add(name, cells[price_i], group, date, tobacco)
    if missing := REQUIRED_GROUPS - groups:
        raise ValueError(f"Beklenen gruplar eksik: {sorted(missing)}; CSV yazilmadi")
    if table_count != len(content.find_all("table")) or not observations:
        raise ValueError("Fiyat tablolari tam islenemedi; CSV yazilmadi")
    if not any(row["producer_group"] == "JTI" and row["category"] == "Sarmalık Tütün" for row in observations):
        raise ValueError("JTI sarmalik tutun metni bulunamadi; CSV yazilmadi")
    return observations, table_count


def deduplicate(observations):
    groups = defaultdict(list)
    for row in observations:
        groups[(key(row["product_name"]), row["sub_category_number"], row["weight_g"])].append(row)
    rows, conflicts = [], 0
    for group in groups.values():
        preferred = sorted(group, key=lambda row: (row["_priority"], row["price_date"]), reverse=True)[0]
        quotes = {(row["price"], row["_raw_price"] if not row["price"] else "") for row in group}
        if len(quotes) > 1:
            newest = []
            if all(row["price_date"] for row in group):
                latest = max(row["price_date"] for row in group)
                newest = [row for row in group if row["price_date"] == latest]
            if newest and newest[0]["price"] and len({row["price"] for row in newest}) == 1:
                preferred = newest[0]
            else:
                preferred = {**preferred, "price": "", "price_date": ""}
                conflicts += 1
                LOGGER.warning("Tarihi karsilastirilamayan fiyatlar bos birakildi: %s (%s)",
                               preferred["product_name"], "; ".join(sorted({row['_raw_price'] for row in group})))
        rows.append({field: preferred[field] for field in FIELDS})
    return sorted(rows, key=lambda row: (row["sub_category_number"], key(row["product_name"]))), conflicts


def fetch():
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR,tr;q=0.9"})
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))))
        response = session.get(URL, timeout=(10, 40))
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text


def save_csv(rows, output_dir, date):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"karekod_sigara_{date}.csv"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", dir=output_dir,
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Kayitli HTML ile calis")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    now = datetime.now(TIMEZONE)
    try:
        html = args.html.read_text(encoding="utf-8") if args.html else fetch()
        observations, table_count = parse_page(html, now.isoformat(timespec="seconds"))
        rows, conflicts = deduplicate(observations)
        if not any(row["price"] for row in rows):
            raise ValueError("Kesin fiyat bulunamadi; CSV yazilmadi")
        path = save_csv(rows, args.output_dir, now.strftime("%Y-%m-%d"))
    except (requests.RequestException, ValueError, OSError) as error:
        LOGGER.error("Veri cekimi tamamlanamadi: %s", error)
        return 1
    LOGGER.info("%d tablo, %d gozlem -> %d urun (%d celiskili fiyat bos)", table_count, len(observations), len(rows), conflicts)
    LOGGER.info("Turler: %s", dict(Counter(row["category"] for row in rows)))
    LOGGER.info("CSV: %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
