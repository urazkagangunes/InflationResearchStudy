"""Karekod'un alkol-fiyatlari sayfasindaki Turkiye fiyatlarini gunluk kaydet.

python InflationItems/Codes/02_Alcohol_Tobacco/KarekodMigros/karekod_migros_scraper.py
Yalniz verilen sayfa okunur; Metro ve baglantili sayfalar taranmaz.
CSV dort temel sutun ve ayri urun/kaynak ozelliklerini icerir.
Her gun ayri CSV yazilir; rapor veya yedek uretilmez.
"""

import argparse
import csv
import logging
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = "https://www.karekod.org/blog/alkol-fiyatlari/"
ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = ROOT / "InflationItems/Datas/02_Alcohol_Tobacco/KarekodMigros"
FIELDS = (
    "product_name", "price", "category_number", "sub_category_number",
    "volume_ml", "packaging_type", "package_count", "deposit_status", "category",
    "source_url", "collected_at", "price_date",
)
SUBCATEGORIES = {
    "Rakı": "0211001", "Votka": "0211002", "Viski": "0211006",
    "Şarap": "0212101", "Bira": "0213001", "Sigara": "0230101",
}
TIMEZONE = ZoneInfo("Europe/Istanbul")
LOGGER = logging.getLogger("karekod_migros")
NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
PRICE_RE = re.compile(rf"(?:TL|₺)?\s*({NUMBER})\s*(?:TL|₺)?", re.I)
VOLUME_RE = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*(ml|cl|lt|litre|l)\b", re.I)
LIK_RE = re.compile(r"(?<!\w)(\d+(?:[,.]\d+)?)\s*['’]\s*l[ıiuü][kğ]\b", re.I)
PACK_RE = re.compile(r"\b(\d+)\s*(?:['’]\s*l[ıiuü]|adet(?:li)?|l[ıiuü])\b", re.I)
MONTHS = dict(zip("ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık".split(), range(1, 13)))
DATE_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b")
EXCLUDED_RE = re.compile(r"arşiv|avrupa|kıbrıs|free\s*shop|duty\s*free|litre\s*fiyat|rusya|metro", re.I)
WINE_KINDS = (
    r"Cabernet Sauvignon|Cabernet Franc|Sauvignon Blanc|Chardonnay|Öküzgözü|"
    r"Boğazkere|Narince|Emir|Syrah|Merlot|Malbec|Kırmızı|Beyaz|Roze|Blush"
)
WINE_VARIANTS = re.compile(rf"\b(?:{WINE_KINDS})(?:\s*/\s*(?:{WINE_KINDS}))+\b", re.I)
BRAND_CATEGORIES = {
    "Rakı": "Yeni Rakı|Tekirdağ|Beylerbeyi|Efe|Sarı Zeybek|Kulüp|Altınbaş|Prototip|Kılıç Rakı",
    "Votka": "Smirnoff|İstanblue|İstanbul Vodka|Gilbey's Vodka|Gilbey's Votka|Bazooka|Ketel One|Cîroc|Ciroc|Absolut|Wyborowa|Flirt|Grey Goose|Binboa",
    "Viski": "Johnnie Walker|Jack Daniel's|Chivas|Royal Salute|Ballantine's|Jameson|The Glenlivet|Aberlour|JP Wiser's|JP Wisers|Pike Creek|Scapa|J&B|Bell's|Dimple|Bulleit|The Singleton|Singleton|Cardhu|Talisker|Lagavulin|Mortlach|Clynelish|Caol Ila|Glenkinchie|Woodford Reserve|Benriach|Glendronach|Glenglassaugh|Tullibardine|Scarabus|The Gladstone Axe|Black Ram|Highland Queen|Glen Talloch|Hyde|Aberfeldy|Royal Brackla|Craigellachie|Teeling|Dewar's",
    "Bira": "Efes|Bremen|Bomonti|Miller|Belfast|Bud|Beck's|Stella|Corona|Amsterdam|Erdinger|Hoegaarden|Leffe|Duvel|Tuborg|Carlsberg|1664 Blanc|Desperados|Sol|Guinness|Weihenstephan|Grimbergen|Jupiler",
    "Cin": "Gordon's|Gilbey's Gin|Tanqueray|Beefeater|Malfy|Wyborowa Gin|Monkey 47|Fords|Gin Mare|6th Sense|Knut Hansen|Oxley|Bombay|Stirling|Sipsmith|Roku",
    "Tekila": "Astral|Don Julio|Casamigos|Olmeca|Código|Butterfly Cannon|Sip & Sip|Sombrero|Reserva Del Senor|Herencia|El Jimador|Herradura|Patrón|Jose Cuervo|1800 Reserva",
    "Likör": "Baileys|Smirnoff North|Hazen|Kahlua|Malibu|Garrone Rosso|Garrone Dry|Garrone Bianco|Lillet|Chambord|Shanky's|St-Germain|Jagermeister|Jägermeister|Patrón XO Cafe",
    "Rom": "Captain Morgan|Zacapa|Havana Club|Bumbu|Diplomatico|Takamaka|Capitan Huk|Bacardi",
    "Mezcal": "Del Maguey|Ojo de Tigre|Mitre|Casamigos Mezcal",
    "Konyak": "Martell|Sorau|Cemiyet|Camus|Hennessy",
    "Vermut": "Martini Bitter|Martini Fiero|Martini Bianco|Martini Extra Dry|Martini Rosso|Garrone",
    "Şampanya / Köpüklü Şarap": "Mumm|Luc Belaire|Cafe de Paris|Garrone Prosecco|Moët|Veuve|Ruinart|Armand de Brignac|Dom Pérignon|Martini Rosé|Martini Asti|Martini Prosecco|Martini Brut",
    "Şarap": "Peribacası|Turasan|Libra|Seneler|Hayyam|Ancyra|Vin Art|VİN ART|Kavaklıdere|Shiluh|Kızılcaterzi|Cumartesi|Buzbağ|Leona|Bianca|Cielo|Terra|Ruffino|Vintage|Versus|Chateau Bel Air|Terre Allegre",
    "Hazır Alkollü İçecek": "Volim|Holidays",
}


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).replace("’", "'").replace("‘", "'").split())


def key(text):
    return normalize(text).replace("İ", "i").casefold()


# Uzun ve ozel marka/urun eslesmesi genel marka eslesmesinden once gelir.
BRANDS = sorted(((key(b), c) for c, names in BRAND_CATEGORIES.items() for b in names.split("|")),
                key=lambda item: len(item[0]), reverse=True)


def parse_price(text):
    """Tek kesin TL fiyatini oku; araliklari ortalama, depozitoyu toplama."""
    text = normalize(text)
    if any(currency in text.casefold() for currency in ("€", "$", "eur", "usd")):
        return ""
    base, _, extra = text.partition("+")
    if extra and "depozito" not in key(extra):
        return ""
    base = re.sub(r"\s*([.,])\s*", r"\1", base).strip()
    match = PRICE_RE.fullmatch(base)
    if not match:
        return ""
    value = Decimal(match[1].replace(".", "").replace(",", "."))
    return f"{value:.2f}" if value > 0 else ""


def extract_dates(text):
    dates = set()
    for day, month, year in DATE_RE.findall(key(text)):
        try:
            dates.add(datetime(int(year), MONTHS[month], int(day)).date().isoformat())
        except ValueError:
            pass
    for day, month, year in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text):
        try:
            dates.add(datetime(int(year), int(month), int(day)).date().isoformat())
        except ValueError:
            pass
    return dates


def extract_volume(text):
    matches = [(m, Decimal(m[1].replace(",", ".")) *
                {"ml": 1, "cl": 10, "lt": 1000, "litre": 1000, "l": 1000}[m[2].lower()])
               for m in VOLUME_RE.finditer(text)]
    matches += [(m, Decimal(m[1].replace(",", ".")) * 10) for m in LIK_RE.finditer(text)]
    values = {value for _, value in matches}
    if len(values) > 1 or any(value <= 0 for value in values):
        raise ValueError(f"Urun icin belirsiz/gecersiz hacim: {text}")
    if not values:
        return normalize(text), ""
    clean = text
    for match, _ in sorted(matches, key=lambda item: item[0].start(), reverse=True):
        clean = clean[:match.start()] + clean[match.end():]
    clean = re.sub(r"\(\s*\)", "", clean)
    return normalize(clean).strip(" :,-"), format(next(iter(values)).normalize(), "f")


def product_attributes(name, raw_price=""):
    """Yalniz kaynakta belirtilen ambalaj, paket ve depozito bilgileri."""
    folded = key(name)
    packaging = ""
    if re.search(r"\bfıçı\b", folded):
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
    return {"packaging_type": packaging, "package_count": count, "deposit_status": deposit}


def enrich_observation(row):
    """Onceki cekimin ham gozlemlerinden de yeni sutunlari olusturabilir."""
    attributes = product_attributes(row["product_name"], row.get("raw_price", ""))
    _, volume_ml = extract_volume(row["product_name"])
    return {**row, "category_number": "02",
            "sub_category_number": SUBCATEGORIES.get(row["category"], "0"),
            "volume_ml": row.get("volume_ml", volume_ml), **attributes}


def classify(name, headings):
    folded = key(name)
    # Urun kimligi, karmasik tablolarin en yakin basligindan daha belirleyicidir.
    if "köpüklü şarap" in folded or "şampanya" in folded or "prosecco" in folded or "prosseco" in folded:
        return "Şampanya / Köpüklü Şarap"
    for brand, category in BRANDS:
        if folded == brand or folded.startswith(brand + " "):
            return category
    for text in [name, *reversed(headings)]:
        folded = key(text)
        for pattern, category in (
            (r"viski likör|likör|aperitif|düziko", "Likör"),
            (r"şampanya|köpüklü", "Şampanya / Köpüklü Şarap"),
            (r"vermut", "Vermut"), (r"mezcal", "Mezcal"),
            (r"konyak|brendi|brandy", "Konyak"), (r"\brom\b", "Rom"),
            (r"tekila|tequila", "Tekila"), (r"\bcin\b|\bgin\b|tanqueray", "Cin"),
            (r"votka|vodka", "Votka"), (r"rakı", "Rakı"),
            (r"viski|whisk[ey]+", "Viski"), (r"şarap", "Şarap"),
            (r"bira", "Bira"), (r"volim|holidays", "Hazır Alkollü İçecek"),
        ):
            if re.search(pattern, folded):
                return category
    return "Diğer"


def complete_name(name, heading):
    """Yalniz acikca tek markaya ait basliktan eksik marka adini tamamla."""
    for prefix in ("Johnnie Walker", "Tanqueray", "Don Julio", "Casamigos"):
        if key(prefix) in key(heading) and not key(name).startswith(key(prefix)):
            name = f"{prefix} {name}"
    name = re.sub(r"\s+[–—]\s+", " ", name)
    name = re.sub(r"\s+fiyat[ıi]$", "", name, flags=re.I)
    name = re.sub(r"^Chivas\s+(?=\d)", "Chivas Regal ", name, flags=re.I)
    name = re.sub(r"^The Singleton of Dufftown\b", "Singleton", name, flags=re.I)
    name = re.sub(r"^C[îi]roc\b", "Ciroc", name, flags=re.I)
    if re.fullmatch(r"(?:Smirnoff|İstanblue|Gilbey's|Bazooka|Absolut Blue|Binboa)\s+(?:Vodka|Votka)", name, re.I):
        name = name.rsplit(" ", 1)[0]
    if re.fullmatch(r"Beefeater Gin", name, re.I):
        name = "Beefeater"
    if key(name).startswith("cin gordon's"):
        name = "Gordon's" + name[len("Cin Gordon's"):]
    name = re.sub(r"^Tanqueray No[:.]?\s*Ten$", "Tanqueray No. Ten", name, flags=re.I)
    name = re.sub(r"^Tanqueray London Dry$", "Tanqueray London Dry Gin", name, flags=re.I)
    name = re.sub(r"^JP Wisers$", "JP Wiser's", name, flags=re.I)
    name = {"yeni seri": "Yeni Rakı Yeni Seri", "ala": "Yeni Rakı Ala",
            "altınbaş": "Altınbaş Rakı"}.get(key(name), name)
    return normalize(name)


def split_variants(name, category):
    if category == "Şarap":
        match = WINE_VARIANTS.search(name)
        if not match or re.search(r"\bblend\b", name, re.I):
            return [name]
        kinds = [normalize(part) for part in match[0].split("/")]
        if {key(part) for part in kinds} <= {"roze", "blush"}:
            return [name]
        return [normalize(name[:match.start()] + part + name[match.end():]) for part in kinds]
    for prefix in ("Absolut", "Garrone"):
        if key(name).startswith(key(prefix) + " ") and "/" in name:
            variants = name[len(prefix):].split("/")
            return [normalize(f"{prefix} {part}") for part in variants]
    return [name]


def parse_page(html, collected_at):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.content.c-text")
    if content is None:
        raise ValueError("Karekod icerik alani bulunamadi; CSV yazilmadi")
    tables = content.find_all("table")
    if not tables:
        raise ValueError("Fiyat tablolari bulunamadi; CSV yazilmadi")
    observations, exclusions = [], []
    headings = {}
    section_dates = {}
    table_count = 0
    handled_tables = set()

    def context():
        return [headings[level] for level in sorted(headings)]

    def observed_date():
        # "Asagidaki tablo guncellendi" alt basliklardaki diger markalari kapsamaz.
        dates = section_dates.get(max(headings), set()) if headings else set()
        return next(iter(dates)) if len(dates) == 1 else ""

    def add(name, volume, raw_price, section, table_number, date, raw_cells):
        combined = normalize(f"{name} {volume}")
        clean, volume_ml = extract_volume(combined)
        original_category = classify(clean, section)
        clean = complete_name(clean, section[-1] if section else "")
        category = classify(clean, section)
        if category == "Diğer":
            category = original_category
        for variant in split_variants(clean, category):
            # Ortak hacmi her ceside ekle; kaynagi olmayan hacim eklenmez.
            if volume_ml:
                cl = format((Decimal(volume_ml) / 10).normalize(), "f").replace(".", ",")
                product_name = f"{variant} {cl} cl"
            else:
                product_name = variant
            if not product_name:
                raise ValueError(f"Tablo {table_number}: urun adi bos")
            actual_category = category
            observations.append({
                "product_name": product_name, "price": parse_price(raw_price),
                "category_number": "02", "sub_category_number": SUBCATEGORIES.get(actual_category, "0"),
                "category": actual_category, "volume_ml": volume_ml,
                **product_attributes(product_name, raw_price),
                "source_url": URL, "section": section, "table_number": table_number,
                "price_date": date, "raw_price": raw_price, "raw_cells": raw_cells,
                "collected_at": collected_at,
            })

    for node in content.find_all(["h2", "h3", "h4", "p", "table"]):
        if node.name in ("h2", "h3", "h4"):
            level = int(node.name[1])
            headings = {k: v for k, v in headings.items() if k < level}
            section_dates = {k: v for k, v in section_dates.items() if k < level}
            headings[level] = normalize(node.get_text(" ", strip=True))
            section_dates[level] = set()
            continue
        section = context()
        excluded = EXCLUDED_RE.search(" / ".join(section))
        if node.name == "p":
            # Tablo hucreleri, reklam ve icindekiler metni urun paragrafi degildir.
            if node.find_parent(["table", "aside", "nav", "style"]):
                continue
            text = normalize(node.get_text(" ", strip=True))
            if headings and not excluded:
                section_dates[max(headings)].update(extract_dates(text))
            if not excluded:
                # Beylerbeyi gibi yalniz metinde verilen acik urun-hacim-fiyatlari.
                # Tarih veya tum sayfanin duzenlenmesi diger tablolara uygulanmaz.
                pattern = rf"(?<!\w)(\d+(?:[,.]\d+)?\s*(?:cl|ml|['’]l[ıiuü]k))\s+([A-ZÇĞİÖŞÜ][^,;:.!?]{{1,100}}?)\s*:?\s+({NUMBER}\s*(?:TL|₺))"
                for match in re.finditer(pattern, text):
                    product = normalize(match[2]).removesuffix(" fiyatı")
                    if product.startswith("Beylerbeyi ") or re.fullmatch(r"Patrón XO Cafe", product):
                        dates = extract_dates(text)
                        add(product, match[1], match[3], section, 0,
                            next(iter(dates)) if len(dates) == 1 else observed_date(), [text])
            continue
        table_count += 1
        handled_tables.add(id(node))
        trs = node.find_all("tr")
        if len(trs) < 2:
            raise ValueError(f"Tablo {table_count}: fiyat tablosu bos")
        header = [normalize(c.get_text(" ", strip=True)) for c in trs[0].find_all(["th", "td"])]
        if excluded:
            exclusions.append({"table_number": table_count, "section": section,
                               "reason": excluded[0], "rows": len(trs) - 1})
            continue
        price_cols = [i for i, h in enumerate(header) if "fiyat" in key(h)]
        volume_cols = [i for i, h in enumerate(header) if VOLUME_RE.fullmatch(h)]
        volume_i = next((i for i, h in enumerate(header) if "hacim" in key(h)), None)
        brand_i = next((i for i, h in enumerate(header) if key(h) == "marka"), None)
        name_i = next((i for i, h in enumerate(header) if key(h) == "ürün"), 0)
        if not price_cols and not volume_cols:
            raise ValueError(f"Tablo {table_count}: bilinmeyen baslik {header}")
        # Eski/yeni fiyat varsa yalniz yeni sutun bir gozlemdir.
        new_i = next((i for i in price_cols if "yeni" in key(header[i])), None)
        if new_i is not None:
            price_cols = [new_i]
        if len(price_cols) > 1:
            raise ValueError(f"Tablo {table_count}: belirsiz fiyat sutunlari {header}")
        for tr in trs[1:]:
            cells = [normalize(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
            if len(cells) != len(header):
                raise ValueError(f"Tablo {table_count}: hucre sayisi degisti: {cells}")
            name = cells[name_i]
            if brand_i is not None and brand_i != name_i:
                name = normalize(cells[brand_i] + " " + name)
            if volume_cols and not price_cols:
                for i in volume_cols:
                    # Tire, urunun o hacimde listelenmedigini ifade eder.
                    if cells[i] in ("", "—", "–", "-"):
                        continue
                    add(name, header[i], cells[i], section, table_count, observed_date(), cells)
            else:
                add(name, cells[volume_i] if volume_i is not None else "", cells[price_cols[0]],
                    section, table_count, observed_date(), cells)
    if len(handled_tables) != len(tables):
        raise ValueError("Islenmemis fiyat tablolari var; CSV yazilmadi")
    if not observations:
        raise ValueError("Turkiye urun fiyatlari bulunamadi; CSV yazilmadi")
    return observations, exclusions, table_count


def deduplicate(observations):
    groups = defaultdict(list)
    for row in observations:
        row = enrich_observation(row)
        groups[(key(row["product_name"]), row["sub_category_number"])].append(row)
    rows, conflicts, selected = [], [], []
    for group in groups.values():
        quotes = {(r["price"], r["raw_price"] if not r["price"] else "") for r in group}
        chosen = group[0]
        if len(quotes) > 1:
            # Tarihsiz bir fiyat digerinden eski sayilamaz; sayfa sirasi kullanilmaz.
            if all(r["price_date"] for r in group):
                newest_date = max(r["price_date"] for r in group)
                newest = [r for r in group if r["price_date"] == newest_date]
                if newest[0]["price"] and len({r["price"] for r in newest}) == 1:
                    chosen = newest[0]
                    selected.append({"product_name": chosen["product_name"], "price": chosen["price"],
                                     "price_date": newest_date, "observations": group})
                else:
                    chosen = {**chosen, "price": ""}
            else:
                chosen = {**chosen, "price": ""}
            if not chosen["price"]:
                conflicts.append({"product_name": chosen["product_name"],
                                  "reason": "Guncelligi belirlenemeyen veya ayni tarihte celisen fiyatlar",
                                  "observations": group})
        rows.append({field: chosen[field] for field in FIELDS})
    return sorted(rows, key=lambda r: (r["sub_category_number"], key(r["product_name"]))), conflicts, selected


def atomic_write(path, write):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8",
                                         newline="", dir=path.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            write(handle)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch():
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR,tr;q=0.9"})
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))))
        response = session.get(URL, timeout=(10, 40))
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Canli sayfa yerine kayitli HTML ile calis")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    now = datetime.now(TIMEZONE)
    try:
        html = args.html.read_text(encoding="utf-8") if args.html else fetch()
        observations, exclusions, table_count = parse_page(html, now.isoformat(timespec="seconds"))
        rows, conflicts, selected = deduplicate(observations)
        if not any(row["price"] for row in rows):
            raise ValueError("Hic kesin fiyat bulunamadi; CSV yazilmadi")
        date = now.strftime("%Y-%m-%d")
        path = args.output_dir / f"karekod_migros_{date}.csv"

        def write_csv(handle):
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

        atomic_write(path, write_csv)
    except (requests.RequestException, ValueError, OSError) as error:
        LOGGER.error("Veri cekimi tamamlanamadi: %s", error)
        return 1
    LOGGER.info("%d tablo, %d gozlem -> %d urun (%d fiyat bos)",
                table_count, len(observations), len(rows), sum(not r["price"] for r in rows))
    LOGGER.info("CSV: %s", path)
    LOGGER.info("Fiyat celiskisi: %d; daha yeni fiyat secilen: %d", len(conflicts), len(selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
