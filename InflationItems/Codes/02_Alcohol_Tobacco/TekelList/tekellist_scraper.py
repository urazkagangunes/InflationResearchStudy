"""TekelList alkollu icecek fiyatlarini gunluk ortak CSV formatinda kaydet.

Kurulum: pip install requests beautifulsoup4
Calistirma: python InflationItems/Codes/02_Alcohol_Tobacco/TekelList/tekellist_scraper.py
Cikti: InflationItems/Datas/02_Alcohol_Tobacco/TekelList/tekellist_YYYY-MM-DD.csv

Kokteyl tarifleri ve bar/restoran fiyatlari alinmaz. Hacim ml cinsindedir;
ambalaj turleri can, bottle, keg olarak yazilir. Kaynakta olmayan bilgiler
bos kalir. Fiyat paket toplamidir; ayrica belirtilen depozito fiyata eklenmez.
CSV Karekod Migros ile ayni 12 sutunu icerir; hacim/ambalaj ayri alanlardir.
Ana kategori 02; eslesmeyen alt kategori 0. Her gun ayri CSV yazilir.
Sarap cesitleri ayri urunlerdir: iki cesit ve iki fiyat sirayla eslestirilir,
tek fiyat varsa her ceside ayni fiyat yazilir. Cesit/fiyat sayisi uyusmazsa
veya guncelligi belirlenemeyen fiyat celiskisi varsa price bos birakilir.
"""

import csv
import logging
import re
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://tekellist.com.tr/"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "Datas/02_Alcohol_Tobacco/TekelList"
TIMEZONE = ZoneInfo("Europe/Istanbul")
FIELDS = (
    "product_name", "price", "category_number", "sub_category_number",
    "volume_ml", "packaging_type", "package_count", "deposit_status", "category",
    "source_url", "collected_at", "price_date",
)
SUBCATEGORIES = {
    "Rakı": "0211001", "Votka": "0211002", "Viski": "0211006",
    "Şarap": "0212101", "Bira": "0213001", "Sigara": "0230101",
}
CATEGORIES = {
    "bira": "Bira", "sarap": "Şarap", "viski": "Viski", "votka": "Votka",
    "cin": "Cin", "tekila": "Tekila", "raki": "Rakı",
}
OPTIONAL_CATEGORIES = {
    "sigara": "Sigara", "rom": "Rom", "likor": "Likör", "mezcal": "Mezcal",
    "konyak": "Konyak", "vermut": "Vermut", "sampanya": "Şampanya / Köpüklü Şarap",
}
REQUIRED_SECTIONS = {
    "bira": "efes tuborg carlsberg ithal paket ucuz fici",
    "sarap": "kavaklidere doluca shiluh vinova kale turasan sofralik ekonomik premium",
    "viski": "johnnie-walker chivas jameson ballantines jack-daniels single-malt amerikan japon-kanada blend",
    "votka": "absolut smirnoff yerli wyborowa premium grey-goose diger hacim",
    "cin": "gordons gilbeys tanqueray beefeater malfy wyborowa greenalls bombay stirling premium cork",
    "tekila": "olmeca don-julio casamigos patron codigo jose-cuervo sierra reserva diger hacim",
    "raki": "yeni-raki izmir vefa efe tekirdag kulup prototip beylerbeyi beyoglu sari-zeybek saki klasik-gobek uygun",
}
BRANDS = """
Efes|Bremen|Bomonti|Tuborg|Carlsberg|Miller|Belfast|Bud|Beck's|Stella Artois|
Corona|Amsterdam|Erdinger|Hoegaarden|Leffe|Duvel|1664 Blanc|Frederik|Desperados|
Sol|Guinness|Weihenstephan|Grimbergen|Benediktiner|Schneider|Schlenkerla|Marmara|
Kavaklıdere|Doluca|Shiluh|Vinova|Kale Vineyards|Turasan|Hayyam|Biricik|
Akdeniz İncisi|Buzbağ|Sebastian|Corvus|Kayra|Martini|
Yeni Rakı|İzmir Rakısı|Vefa Rakısı|Efe|Tekirdağ Rakısı|Kulüp Rakı|Altınbaş Rakı|
Prototip Rakı|Beylerbeyi|Beyoğlu Rakı|Sarı Zeybek|Saki|Klasik Göbek Rakı|
Johnnie Walker|Chivas|Jameson|Teeling|Ballantine's|Jack Daniel's|Talisker|Lagavulin|
Singleton|Cardhu|Mortlach|The Glenlivet|Aberlour|Aberfeldy|Royal Brackla|Craigellachie|
Scapa|Benriach|Glenglassaugh|Glendronach|Jim Beam|Woodford Reserve|Knob Creek|
Maker's Mark|Basil Hayden's|Hibiki|Yamazaki|Chita|JP Wisers|Pike Creek|J&B|Bell's|
Simple|Dewar's|Auchentoshan|Bowmore|Glen Talloch|Hankey Bannister|Grant's|Long John|Passport|
Absolut|Smirnoff|İstanblue|Gilbey's|Bazooka|Wyborowa|FLIRT|Ketel One|Ciroc|Nikka|
Beluga|Grey Goose|Svayak|Keglevich|Limonce|Onegin|Russian Standard|
Gordon's|Tanqueray|Beefeater|Malfy|Greenall's|Bombay Sapphire|Stirling|Monkey 47|
Oxley|Bottega|Green Gin|Ophir|No.3|Mosaik|Sipsmith|Roku|Larios|6th SENSE|KNUT HANSEN|Cork|
Olmeca|Don Julio|Casamigos|Patrón|Código|Jose Cuervo|Sierra|1800 Reserva|
Reserva de la Familia|Astral|Butterfly Cannon|Sip & Sip|Sombrero|Reserva Del Senor|
Herencia|El Jimador|Herradura
"""
# Urun adinda marka yoksa yalniz acikca tek markaya ait bolum basligini kullan.
SECTION_BRANDS = {
    ("Şarap", "kavaklidere"): "Kavaklıdere", ("Şarap", "doluca"): "Doluca",
    ("Şarap", "turasan"): "Turasan", ("Viski", "jack-daniels"): "Jack Daniel's",
    ("Rakı", "izmir"): "İzmir Rakısı",
}
BRAND_PREFIXES = sorted((b.strip() for b in BRANDS.split("|") if b.strip()), key=len, reverse=True)
NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
PRICE_RE = re.compile(
    rf"({NUMBER})(?:\s*[-–—/]\s*({NUMBER}))?\s*TL"
    rf"(?:\s*\+\s*{NUMBER}\s*TL\s*depozito)?", re.I,
)
VOLUME_RE = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*(ml|cl|lt|l)\b", re.I)
PACK_RE = re.compile(r"\b(\d+)\s*(?:['’]\s*l[ıiuü]|adet(?:li)?|l[ıiuü])\b", re.I)
SERVICE_RE = re.compile(r"\b(?:bar|pub|restoran|restaurant|kokteyl)\b", re.I)
SUMMARY_RE = re.compile(r"^\d+(?:,\d+)?['’]l[ıiuü]k\s+", re.I)
WINE_KIND = (
    r"(?:Cabernet Sauvignon|Cabernet Franc|Sauvignon Blanc|Chardonnay|Blend No\.4|"
    r"Öküzgözü|Boğazkere|Narince|Emir|Syrah|Merlot|Malbec|Kırmızı|Beyaz|Roze|Blush|Klasik)"
)
WINE_VARIANTS_RE = re.compile(rf"\b{WINE_KIND}(?:\s*/\s*{WINE_KIND})+\b", re.I)
MONTHS = dict(zip(
    "ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split(),
    range(1, 13),
))
LOGGER = logging.getLogger("tekellist")


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def key(text):
    return normalize(text).replace("’", "'").replace("İ", "i").casefold()


def parse_prices(text):
    """Turkce sayi bicimini coz; depozitoyu fiyatin disinda tut."""
    match = PRICE_RE.fullmatch(normalize(text))
    if not match:
        return []
    prices = [Decimal(value.replace(".", "").replace(",", "."))
              for value in match.groups() if value is not None]
    if any(price <= 0 for price in prices) or prices != sorted(prices):
        raise ValueError(f"Gecersiz fiyat: {text}")
    return [f"{price:.2f}" for price in prices]


def product_attributes(name, category, raw_price=""):
    volumes = {Decimal(m[1].replace(",", ".")) * {"ml": 1, "cl": 10, "lt": 1000, "l": 1000}[m[2].lower()]
               for m in VOLUME_RE.finditer(name)}
    volume = format(next(iter(volumes)).normalize(), "f") if len(volumes) == 1 else ""
    if volume and Decimal(volume) <= 0:
        raise ValueError(f"Gecersiz hacim: {name}")
    folded = key(name)
    packaging = ""
    if category == "Bira" and re.search(r"\bfıçı\b", folded):
        packaging = "keg"
    elif re.search(r"\bkutu\b", folded):
        packaging = "can"
    elif re.search(r"\bşişe\b", folded):
        packaging = "bottle"
    elif re.search(r"\btek yön\b", folded):
        packaging = "one_way"
    pack = PACK_RE.search(folded)
    count = int(pack[1]) if pack else ""
    if count != "" and count <= 0:
        raise ValueError(f"Gecersiz paket adedi: {name}")
    deposit = ""
    if re.search(r"\bdepozitosuz\b|\btek yön\b", folded):
        deposit = "non_returnable"
    elif re.search(r"\bdepozitolu\b", folded) or "depozito" in key(raw_price):
        deposit = "returnable"
    return {"volume_ml": volume, "packaging_type": packaging, "package_count": count,
            "deposit_status": deposit}


def find_brand(name, category, section_id):
    folded = key(name)
    if folded.startswith("sarı tuborg "):
        return "Tuborg"
    for brand in BRAND_PREFIXES:
        prefix = key(brand)
        if folded == prefix or folded.startswith(prefix + " "):
            return brand
    return SECTION_BRANDS.get((category, section_id), "")


def wine_variants(name):
    match = WINE_VARIANTS_RE.search(name)
    if not match:
        return [name]
    variants = [normalize(v) for v in match[0].split("/")]
    # Roze ve Blush ayni cesidin adlaridir; Blend ise uzum karisimidir.
    if {key(v) for v in variants} <= {"roze", "blush"} or re.match(r"\s+Blend\b", name[match.end():], re.I):
        return [name]
    return [normalize(name[:match.start()] + variant + name[match.end():]) for variant in variants]


def expand_product(name, raw_price, category):
    names = wine_variants(name) if category == "Şarap" else [name]
    prices = parse_prices(raw_price)
    if len(prices) == 1:
        prices *= len(names)
    elif category != "Şarap" or len(prices) != len(names):
        prices = [""] * len(names)
    if not prices:
        prices = [""] * len(names)
    if not all(prices):
        LOGGER.warning("Kesin fiyat atanamadi: %s - %s", name, raw_price)
    return list(zip(names, prices))


def updated_date(note):
    """Yalniz tek ve acik gun/ay/yil tarihi varsa guncellik kiyaslamasi yap."""
    folded = key(note)
    months = "|".join(MONTHS)
    if len(re.findall(rf"\b(?:{months})\b", folded)) != 1:
        return ""
    match = re.search(rf"\b(\d{{1,2}})\s+({months})\s+(20\d{{2}})\b", folded)
    if not match:
        return ""
    return datetime(int(match[3]), MONTHS[match[2]], int(match[1])).date().isoformat()


def discover_categories(html):
    pages = {}
    for link in BeautifulSoup(html, "html.parser").select("nav .nav-links a[href]"):
        url = urljoin(BASE_URL, link["href"])
        parsed = urlsplit(url)
        slug = parsed.path.strip("/").removesuffix(".html")
        if parsed.netloc != urlsplit(BASE_URL).netloc or not slug or "/" in slug:
            continue
        if slug in {"kokteyl", "index"} or SERVICE_RE.search(link.get_text(" ", strip=True)):
            continue
        category = CATEGORIES.get(slug, OPTIONAL_CATEGORIES.get(slug, normalize(link.get_text(" ", strip=True))))
        pages[slug] = (category, url)
    if missing := CATEGORIES.keys() - pages.keys():
        raise ValueError(f"Ana menude beklenen kategoriler eksik: {sorted(missing)}")
    return pages


def parse_page(html, slug, category, url, collected_at):
    article = BeautifulSoup(html, "html.parser").select_one("article.post")
    if article is None:
        raise ValueError(f"{slug}: fiyat sayfasi yapisi degismis")
    sections = article.select("section.post-section[id]")
    required = set(REQUIRED_SECTIONS.get(slug, "").split())
    if missing := required - {section["id"] for section in sections}:
        raise ValueError(f"{slug}: urun bolumleri eksik: {sorted(missing)}")
    total_prices = len(article.select("span.price"))
    rows, accounted, excluded = [], 0, 0
    for section in sections:
        section_id = section["id"]
        heading = section.find(["h2", "h3"])
        title = heading.get_text(" ", strip=True) if heading else ""
        if SERVICE_RE.search(f"{section_id} {title}"):
            count = len(section.select("span.price"))
            accounted += count
            excluded += count
            continue
        items = section.select("ul.beer-list > li")
        if section_id in required and not items:
            raise ValueError(f"{slug}#{section_id}: beklenen urun listesi bos")
        note = " ".join(p.get_text(" ", strip=True) for p in section.find_all("p", recursive=False))
        for item in items:
            spans = item.select("span.price")
            if len(spans) != 1:
                raise ValueError(f"{slug}#{section_id}: urunun tek fiyat alani olmali")
            span = spans[0]
            detail, separator, raw_price = normalize(span.get_text(" ", strip=True)).partition(":")
            if not separator:
                raise ValueError(f"{slug}#{section_id}: hacim/fiyat ayraci eksik")
            span.extract()
            name = normalize(item.get_text(" ", strip=True))
            if not name:
                raise ValueError(f"{slug}#{section_id}: urun adi bos")
            if section_id == "hacim":
                name = SUMMARY_RE.sub("", name)
            accounted += 1
            if SERVICE_RE.search(name):
                excluded += 1
                continue
            for variant, price in expand_product(name, raw_price, category):
                full_name = normalize(f"{variant} {detail}")
                rows.append({
                    "product_name": full_name, "price": price,
                    "brand": find_brand(variant, category, section_id), "category": category,
                    **product_attributes(full_name, category, raw_price), "source_site": "TekelList",
                    "source_url": f"{url.split('#')[0]}#{section_id}", "collected_at": collected_at,
                    "_updated_at": updated_date(note), "_raw_price": normalize(raw_price),
                })
    if accounted != total_prices:
        raise ValueError(f"{slug}: islenmeyen fiyat alanlari var ({total_prices - accounted})")
    if not rows:
        raise ValueError(f"{slug}: urun bulunamadi")
    LOGGER.info("%s: %d urun, %d servis fiyati disarida", category, len(rows), excluded)
    return rows


def deduplicate(rows):
    groups = defaultdict(list)
    for row in rows:
        identity = (key(row["category"]), key(row["brand"]), key(row["product_name"]),
                    row["volume_ml"], row["packaging_type"], row["package_count"])
        groups[identity].append(row)
    output = []
    for group in groups.values():
        quotes = {(row["price"], row["_raw_price"] if not row["price"] else "") for row in group}
        if len(quotes) == 1:
            output.append(group[0])
            continue
        if all(row["_updated_at"] for row in group):
            latest = max(row["_updated_at"] for row in group)
            newest = [row for row in group if row["_updated_at"] == latest]
            if newest[0]["price"] and len({row["price"] for row in newest}) == 1:
                output.append(newest[0])
                LOGGER.info("Guncel fiyat secildi: %s (%s)", newest[0]["product_name"], latest)
                continue
        LOGGER.warning("Celiskili fiyatlar bos birakildi: %s - %s", group[0]["product_name"],
                       "; ".join(f"{row['_raw_price']} ({row['source_url']})" for row in group))
        output.extend({**row, "price": ""} for row in group)
    return sorted(output, key=lambda row: (key(row["category"]), key(row["product_name"]), row["source_url"]))


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR,tr;q=0.9"})
    retry = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch(session, url):
    response = session.get(url, timeout=(10, 40))
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def scrape(session, collected_at):
    rows = []
    for slug, (category, url) in discover_categories(fetch(session, BASE_URL)).items():
        time.sleep(1)
        rows.extend(parse_page(fetch(session, url), slug, category, url, collected_at))
    rows = deduplicate(rows)
    if not any(row["price"] for row in rows):
        raise ValueError("Hic kesin fiyat bulunamadi; CSV yazilmadi")
    return rows


def csv_row(row):
    """Dogal urun adini ve kaynak ozelliklerini ortak 12 sutuna yansit."""
    name = re.sub(r"\s+\|\s+(?:\d+(?:[.,]\d+)?\s*ml|(?:packaging_type|package_count)=).*$",
                  "", row["product_name"])
    attributes = product_attributes(name, row["category"], row.get("_raw_price", ""))
    return {
        "product_name": name, "price": row["price"],
        "category_number": "02", "sub_category_number": SUBCATEGORIES.get(row["category"], "0"),
        **{field: row.get(field, value) for field, value in attributes.items()},
        "category": row["category"], "source_url": row.get("source_url", ""),
        "collected_at": row.get("collected_at", ""),
        "price_date": row.get("price_date", row.get("_updated_at", "")),
    }


def save_csv(rows, output_dir, date):
    """Cekim tamamlandiktan sonra yaz; yazma hatasinda onceki CSV'yi koru."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"tekellist_{date}.csv"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                         dir=output_dir, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(csv_row(row) for row in rows)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    now = datetime.now(TIMEZONE)
    try:
        with make_session() as session:
            rows = scrape(session, now.isoformat(timespec="seconds"))
        path = save_csv(rows, OUTPUT_DIR, now.strftime("%Y-%m-%d"))
    except (requests.RequestException, ValueError, OSError) as error:
        LOGGER.error("Veri cekimi tamamlanamadi: %s", error)
        return 1
    LOGGER.info("%d kayit -> %s", len(rows), path)
    LOGGER.info("Kategoriler: %s", dict(Counter(row["category"] for row in rows)))
    LOGGER.info("Fiyati dolu: %d; fiyati bos: %d", sum(bool(row["price"]) for row in rows),
                sum(not row["price"] for row in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
