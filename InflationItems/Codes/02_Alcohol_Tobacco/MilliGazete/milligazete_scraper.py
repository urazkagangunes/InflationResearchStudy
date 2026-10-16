"""Milli Gazete'nin sigara ve sarmalik tutun verilerini gunluk CSV'ye yaz.

python InflationItems/Codes/02_Alcohol_Tobacco/MilliGazete/milligazete_scraper.py
Ilk dort sutun ortak fiyat formatidir. Her gun ayri dosya yazilir.
Ayrintili liste/metin esas alinir; ozet yalniz eksik urunleri tamamlar.
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


URL = "https://www.milligazete.com.tr/guncel-zamli-sigara-fiyatlari-21-eylul-2026-parliament-marlboro-camel-winston-ve-kent-ne-kadar-oldu"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "Datas/02_Alcohol_Tobacco/MilliGazete"
TIMEZONE = ZoneInfo("Europe/Istanbul")
FIELDS = (
    "product_name", "price", "category_number", "sub_category_number",
    "volume_ml", "packaging_type", "package_count", "deposit_status", "category",
    "source_url", "collected_at", "price_date", "weight_g", "brand", "producer_group",
)
LOGGER = logging.getLogger("milligazete")
NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
PRICE_RE = re.compile(rf"(?:₺\s*({NUMBER})|({NUMBER})\s*(?:TL|₺))", re.I)
WEIGHT_RE = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*(?:\(\s*)?(?:gram|gr|g)\b(?:\s*\))?", re.I)
MONTHS = dict(zip("ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split(), range(1, 13)))
DATE_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b")
REQUIRED_BRANDS = {"Parliament", "Marlboro", "Winston", "Camel", "Kent", "Davidoff",
                   "Muratti", "Chesterfield", "L&M", "Lark", "Captain Black", "HD", "President"}
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
    if key(name) in {"hd red", "hd blue", "hd sky"}:
        return [f"{name} Kısa", f"{name} Uzun"]
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
    content = soup.select_one(".article-text")
    if content is None:
        raise ValueError("Milli Gazete haber icerigi bulunamadi; CSV yazilmadi")
    observations, heading, date = [], "", ""
    table_count = 0

    def add(name, raw_price, priority=3, weight=""):
        tobacco = bool(weight)
        if tobacco:
            name, weight = tobacco_attributes(name, f"{weight} g")
        for variant in [name] if tobacco else split_variants(name):
            brand = find_brand(variant)
            if not brand:
                raise ValueError(f"Markasi belirlenemeyen urun: {variant}")
            full_name = variant
            if weight and key(variant) != "marlboro roll " + weight:
                full_name = f"{variant} {weight} g"
            observations.append({
                "product_name": full_name, "price": parse_price(raw_price),
                "category_number": "02", "sub_category_number": "0" if tobacco else "0230101",
                "volume_ml": "", "packaging_type": "", "package_count": "", "deposit_status": "",
                "category": "Sarmalık Tütün" if tobacco else "Sigara", "source_url": URL,
                "collected_at": collected_at, "price_date": date, "weight_g": weight,
                "brand": brand, "producer_group": BRAND_GROUPS[brand],
                "_priority": priority, "_raw_price": raw_price,
            })

    def named(description, number, brand):
        for part in re.split(r"\s*,\s*|\s+ve\s+", normalize(description)):
            part = part.strip(" .,:;")
            if not part:
                raise ValueError(f"Bos urun cesidi: {description}")
            add(part if find_brand(part) else f"{brand} {part}", f"{number} TL")

    def narrative(text):
        # Davidoff: iki Slims, uc renk ve C Line; fiyatlar metinden alinir.
        match = re.search(rf"^Davidoff\s+(.+?)\s+({NUMBER})\s*TL,\s*(.+?)\s+({NUMBER})\s*TL,\s*Davidoff\s+(.+?)\s+ise\s+({NUMBER})\s*TL", text, re.I)
        if match:
            named(match[1], match[2], "Davidoff")
            named(match[3], match[4], "Davidoff")
            named(match[5], match[6], "Davidoff")
        match = re.search(rf"Bianca'nın fiyatı\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("Bianca", f"{match[1]} TL")
        match = re.search(rf"grubunda bulunan\s+(Muratti.+?)\s+({NUMBER})\s*TL\s+seviyesinde", text, re.I)
        if match:
            named(match[1], match[2], "Muratti")
        match = re.search(rf"^(Chesterfield .+?)\s+ile\s+(L&M .+?)\s+ürünlerinin fiyatı\s+({NUMBER})\s*TL", text, re.I)
        if match:
            named(match[1], match[3], "Chesterfield")
            named(match[2], match[3], "L&M")
            lark = re.search(r"(Lark .+?)\s+da aynı fiyat seviyesinde", text, re.I)
            if lark:
                named(lark[1], match[3], "Lark")
        match = re.search(rf"^Captain Black\s+(.+?)\s+ürünlerinin tamamı\s+({NUMBER})\s*TL", text, re.I)
        if match:
            named(match[1], match[2], "Captain Black")
        match = re.search(rf"^HD'nin\s+(.+?)\s+çeşitleri\s+({NUMBER})\s*TL", text, re.I)
        if match:
            named(match[1], match[2], "HD")
            president = re.search(r"President'ın\s+(.+?)\s+ürünleri de aynı fiyat", text, re.I)
            if president:
                named(president[1], match[2], "President")
        match = re.search(rf"Point Blue Slims de\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("Point Blue Slims", f"{match[1]} TL")
        match = re.search(rf"Winner ve Vigor Cerulean ürünlerinde fiyat\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("Winner", f"{match[1]} TL")
            add("Vigor Cerulean", f"{match[1]} TL")
        match = re.search(rf"(West\s+.+?)\s+seçenekleri de\s+({NUMBER})\s*TL", text, re.I)
        if match:
            named(match[1], match[2], "West")
        match = re.search(rf"LD ve Monte Carlo seçenekleri de\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("LD", f"{match[1]} TL")
            add("Monte Carlo", f"{match[1]} TL")
        match = re.search(rf"Rothmans ve Tekel 2000 ürünleri de\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("Rothmans", f"{match[1]} TL")
            add("Tekel 2000", f"{match[1]} TL")
            polo = re.search(r"(Polo .+?)\s+aynı fiyatla satılıyor", text, re.I)
            if polo:
                named(polo[1], match[1], "Polo")
        match = re.search(rf"^Marlboro'nun\s+(\d+(?:[,.]\d+)?)\s+gramlık\s+Roll 50\b.*?\b({NUMBER})\s*TL", text, re.I)
        if match:
            add("Marlboro Roll 50", f"{match[2]} TL", weight=match[1])
        match = re.search(rf"Marlboro Roll 50,\s*(\d+(?:[,.]\d+)?)\s+gramlık paketinde\s+({NUMBER})\s*TL", text, re.I)
        if match:
            add("Marlboro Roll 50", f"{match[2]} TL", weight=match[1])
        match = re.search(rf"Camel Yellow\s+(\d+(?:[,.]\d+)?)\s+gram(?:lık)?\s+sarmalık\b.*?\b({NUMBER})\s*TL", text, re.I)
        if match:
            add("Camel Yellow", f"{match[2]} TL", weight=match[1])

    for node in content.find_all(["h2", "h3", "h4", "p", "li", "table"]):
        if node.name.startswith("h"):
            heading = normalize(node.get_text(" ", strip=True))
            date = price_date(heading)
            continue
        if node.name == "p":
            if node.find_parent(["table", "li", "aside"]):
                continue
            text = normalize(node.get_text(" ", strip=True))
            explicit_date = price_date(text)
            if heading and explicit_date:
                date = explicit_date
            narrative(text)
        elif node.name == "li":
            if node.find_parent(["table", "aside"]):
                continue
            text = normalize(node.get_text(" ", strip=True))
            match = re.fullmatch(rf"(.+?)\s*:\s*({NUMBER}\s*(?:TL|₺))\.?", text, re.I)
            if not match:
                raise ValueError(f"Urun liste bicimi degismis: {text}")
            add(match[1], match[2])
        elif node.name == "table":
            table_count += 1
            trs = node.find_all("tr")
            if len(trs) < 2:
                raise ValueError("Ozet fiyat tablosu bos")
            header = [normalize(c.get_text(" ", strip=True)) for c in trs[0].find_all(["th", "td"])]
            if len(header) != 2 or "fiyat" not in key(header[1]):
                raise ValueError(f"Fiyat sutunlari degismis: {header}")
            for tr in trs[1:]:
                cells = [normalize(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
                if len(cells) != 2:
                    raise ValueError("Ozet tablonun hucre sayisi degismis")
                add(cells[0], cells[1], priority=1)
    detail_brands = {row["brand"] for row in observations if row["_priority"] > 1}
    if missing := REQUIRED_BRANDS - detail_brands:
        raise ValueError(f"Ayrintili urunler eksik: {sorted(missing)}; CSV yazilmadi")
    tobacco_brands = {row["brand"] for row in observations if row["category"] == "Sarmalık Tütün"}
    if tobacco_brands != {"Marlboro", "Camel"}:
        raise ValueError("Sarmalik tutun kayitlari eksik; CSV yazilmadi")
    if table_count != len(content.find_all("table")) or not observations:
        raise ValueError("Fiyat tablolari tam islenemedi; CSV yazilmadi")
    return observations, table_count


def deduplicate(observations):
    groups = defaultdict(list)
    detailed = defaultdict(set)
    for row in observations:
        if row["_priority"] > 1:
            detailed[row["category"]].add(key(row["product_name"]))
    for row in observations:
        name = key(row["product_name"])
        specific = detailed[row["category"]]
        # Ozetin genel seri adi, ayrintili cesitlerin yanina yeni urun olarak eklenmez.
        if row["_priority"] == 1 and name not in specific and any(other.startswith(name + " ") for other in specific):
            continue
        groups[(name, row["sub_category_number"], row["weight_g"])].append(row)
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
    path = output_dir / f"milligazete_{date}.csv"
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
