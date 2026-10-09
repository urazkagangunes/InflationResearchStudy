# Restaurant meal prices, venue hall rental fees scraper
# CSV format: isim,fiyat
# CSV filename: source_name_YYYY-MM-DD.csv

import csv
import re
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup


# ============================================================
# SETTINGS
# ============================================================

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

TODAY = date.today().isoformat()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

REQUEST_TIMEOUT = 8

MAX_WORKERS = 6
MAX_CRAWL_PAGES_PER_SOURCE = 25
MAX_URLS_PER_SOURCE = 160

PRINT_GET_LOGS = False
PRINT_PROGRESS = True

ONLY_FIRST_SOURCE = False

# Restaurant meal category için alkol satırlarını dışarıda bırakır.
EXCLUDE_ALCOHOLIC_DRINKS = True


# ============================================================
# SOURCES
# ============================================================

SOURCES = [
    {
        "name": "menufiyatlistesi",
        "category": "restaurant",
        "start_urls": [
            "https://menufiyatlistesi.com/",
            "https://menufiyatlistesi.com/istanbul/",
            "https://menufiyatlistesi.com/blog/",
        ],
    },
    {
        "name": "menufiyati_tr",
        "category": "restaurant",
        "start_urls": [
            "https://menufiyati.tr/",
            "https://menufiyati.tr/page/2/",
            "https://menufiyati.tr/page/3/",
            "https://menufiyati.tr/page/4/",
        ],
    },
    {
        "name": "menufiyati_com_tr",
        "category": "restaurant",
        "start_urls": [
            "https://menufiyati.com.tr/",
            "https://menufiyati.com.tr/menuler/",
        ],
    },
    {
        "name": "menufiyatlar",
        "category": "restaurant",
        "start_urls": [
            "https://menufiyatlar.com/",
        ],
    },

    {
        "name": "duguncom_dugun_mekanlari_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugun.com/dugun-mekanlari/istanbul",
        ],
    },
    {
        "name": "duguncom_dugun_salonlari_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugun.com/dugun-salonlari/istanbul",
        ],
    },
    {
        "name": "duguncom_kir_dugunu_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugun.com/kir-dugunu/istanbul",
        ],
    },
    {
        "name": "duguncom_soz_nisan_mekanlari_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugun.com/soz-nisan-mekanlari/istanbul",
        ],
    },
    {
        "name": "dugunbuketi_dugun_mekanlari_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugunbuketi.com/c/dugun-mekanlari/istanbul",
        ],
    },
    {
        "name": "dugunbuketi_dugun_salonlari_istanbul",
        "category": "venue",
        "start_urls": [
            "https://dugunbuketi.com/p/dugun-salonlari/istanbul",
        ],
    },
]


# ============================================================
# REGEX / KEYWORDS
# ============================================================

RESTAURANT_KEYWORDS = [
    "menu", "menü", "fiyat", "fiyatları", "yemek", "restoran",
    "restaurant", "lokanta", "burger", "pizza", "kahvaltı",
    "tavuk", "et", "köfte", "dürüm", "döner", "çorba",
    "kebap", "lahmacun", "pide", "makarna", "tatlı", "kahve",
    "icecek", "içecek", "fast-food", "fast food", "cafe", "kafe",
    "isletme", "işletme"
]

VENUE_KEYWORDS = [
    "dugun", "düğün", "salon", "davet", "mekan", "mekân",
    "organizasyon", "kiralama", "kira", "fiyat", "fiyatları",
    "venue", "hall", "rental", "wedding", "banquet",
    "soz", "söz", "nisan", "nişan", "kina", "kına",
    "kokteyl", "toplanti", "toplantı", "konferans"
]

ALCOHOL_WORDS = [
    "rakı", "raki", "şarap", "sarap", "wine", "beer", "bira",
    "vodka", "viski", "whisky", "gin", "tekila", "tequila",
    "likör", "likor", "efes", "bomonti", "becks", "heineken",
    "corona", "miller", "leffe", "kadeh", "şişe", "sise",
    "beylerbeyi", "tekirdağ", "tekirdag", "yeni rakı", "yeni raki"
]

PRICE_WITH_CURRENCY_REGEX = re.compile(
    r"""
    (?:
        ₺\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?
        |
        \d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?\s*(?:TL|tl|₺)
        |
        \d+(?:,\d{1,2})?\s*(?:TL|tl|₺)
    )
    """,
    re.VERBOSE
)

PURE_PRICE_LINE_REGEX = re.compile(
    r"^(?:₺\s*)?\d{2,7}(?:[.,]\d{1,2})?(?:\s*(?:TL|tl|₺))?$"
)

NAME_ENDS_WITH_PRICE_REGEX = re.compile(
    r"^(.{2,160}?)\s+(?:₺\s*)?(\d{2,7}(?:[.,]\d{1,2})?)(?:\s*(?:TL|tl|₺))?$"
)


@dataclass
class PriceItem:
    name: str
    price: str


_thread_local = threading.local()


# ============================================================
# SESSION / FETCH
# ============================================================

def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        })
        _thread_local.session = session

    return _thread_local.session


def mojibake_score(text: str) -> int:
    bad_markers = ["Ã", "Ä", "Å", "Â", "�", "¤", "±", "§", "¶"]
    return sum(str(text).count(marker) for marker in bad_markers)


def decode_response(response: requests.Response) -> str:
    raw = response.content

    possible_encodings = [
        "utf-8",
        response.encoding,
        response.apparent_encoding,
        "windows-1254",
        "iso-8859-9",
    ]

    candidates = []
    seen = set()

    for enc in possible_encodings:
        if not enc:
            continue

        enc = enc.lower()

        if enc in seen:
            continue

        seen.add(enc)

        try:
            candidates.append(raw.decode(enc, errors="replace"))
        except Exception:
            pass

    if not candidates:
        return response.text

    return min(candidates, key=mojibake_score)


def normalize_url(url: str) -> str:
    url = urldefrag(url)[0]
    return url.rstrip("/")


def fetch(url: str) -> str | None:
    url = normalize_url(url)

    if PRINT_GET_LOGS:
        print(f"GET: {url}", flush=True)

    try:
        session = get_session()
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        if (
            "text/html" not in content_type
            and "xml" not in content_type
            and "text/plain" not in content_type
            and content_type != ""
        ):
            return None

        return decode_response(response)

    except Exception as e:
        if PRINT_GET_LOGS:
            print(f"FETCH ERROR: {url} | {e}", flush=True)
        return None


# ============================================================
# CLEANING / NORMALIZATION
# ============================================================

def clean_filename(name: str) -> str:
    name = str(name).lower().strip()
    name = re.sub(r"[^a-zA-Z0-9ğüşöçıİĞÜŞÖÇ_-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def normalize_text(text: str) -> str:
    text = str(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", " ")
    text = text.replace("\ufeff", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def repair_mojibake_if_needed(text: str) -> str:
    text = str(text)

    if mojibake_score(text) == 0:
        return text

    attempts = []

    try:
        attempts.append(text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore"))
    except Exception:
        pass

    try:
        attempts.append(text.encode("windows-1252", errors="ignore").decode("utf-8", errors="ignore"))
    except Exception:
        pass

    attempts.append(text)

    return min(attempts, key=mojibake_score)


def sanitize_csv_name(name: str) -> str:
    name = repair_mojibake_if_needed(str(name))
    name = normalize_text(name)

    # CSV delimiter virgül olduğu için isim içinde virgül bırakmıyoruz.
    name = name.replace(",", " - ")

    # Satır kaydırabilecek karakterleri temizle.
    name = name.replace(";", " ")
    name = name.replace("\t", " ")
    name = name.replace("\n", " ")
    name = name.replace("\r", " ")

    # Excel formula injection önlemi.
    if name.startswith(("=", "+", "-", "@")):
        name = name.lstrip("=+-@").strip()

    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"\s+-\s+", " - ", name)

    return name.strip(" -:|•.,;")


def normalize_price(raw_price: str) -> str | None:
    price = str(raw_price).lower()
    price = price.replace("tl", "")
    price = price.replace("₺", "")
    price = price.replace(" ", "")
    price = price.strip()

    price = re.sub(r"[^0-9,\.]", "", price)

    if not price:
        return None

    has_dot = "." in price
    has_comma = "," in price

    if has_dot and has_comma:
        price = price.replace(".", "")
        price = price.replace(",", ".")

    elif has_comma:
        parts = price.split(",")

        if len(parts[-1]) <= 2:
            price = price.replace(",", ".")
        else:
            price = price.replace(",", "")

    elif has_dot:
        parts = price.split(".")

        if len(parts[-1]) == 3:
            price = price.replace(".", "")

    try:
        value = float(price)
    except ValueError:
        return None

    if value <= 0:
        return None

    if value > 10_000_000:
        return None

    if value.is_integer():
        return str(int(value))

    return f"{value:.2f}"


def get_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").lower()


def same_domain(url: str, allowed_domains: set[str]) -> bool:
    return get_domain(url) in allowed_domains


# ============================================================
# URL RELEVANCE
# ============================================================

def is_relevant_url(url: str, category: str) -> bool:
    lower_url = url.lower()

    if category == "restaurant":
        keywords = RESTAURANT_KEYWORDS
    elif category == "venue":
        keywords = VENUE_KEYWORDS
    else:
        return False

    return any(keyword.lower() in lower_url for keyword in keywords)


def score_url(url: str, category: str) -> int:
    lower = url.lower()
    score = 0

    if category == "restaurant":
        high_value = [
            "isletme", "işletme", "menu", "menü", "fiyat",
            "restaurant", "restoran", "kebap", "doner", "döner",
            "pide", "lahmacun"
        ]
    else:
        high_value = [
            "dugun", "düğün", "salon", "mekan", "mekân",
            "kiralama", "fiyat", "soz", "söz", "nisan", "nişan"
        ]

    for keyword in high_value:
        if keyword in lower:
            score += 10

    if lower.endswith(".xml"):
        score -= 100

    if "/page/" in lower:
        score -= 3

    return score


# ============================================================
# NAME FILTERS
# ============================================================

def contains_alcohol(name: str) -> bool:
    lower = name.lower()
    return any(word in lower for word in ALCOHOL_WORDS)


def looks_like_bad_name(name: str, category: str = "restaurant") -> bool:
    name = sanitize_csv_name(name)
    lower = name.lower()

    if not name:
        return True

    if mojibake_score(name) > 0:
        return True

    if len(name) > 170:
        return True

    word_count = len(name.split())

    if category == "restaurant" and word_count > 35:
        return True

    if category == "venue" and word_count > 45:
        return True

    if name.count("/") >= 9:
        return True

    if name.count(" - ") >= 12:
        return True

    bad_phrases = [
        "sonuç bulunamadı",
        "sonuc bulunamadi",
        "aramanız için",
        "aramaniz icin",
        "detaylı bilgi",
        "detayli bilgi",
        "hemen incele",
        "devamını oku",
        "devamini oku",
        "çerez politikası",
        "cerez politikasi",
        "gizlilik politikası",
        "gizlilik politikasi",
        "kullanım şartları",
        "kullanim sartlari",
        "whatsapp",
        "telefon",
        "rezervasyon",
        "iletişim",
        "iletisim",
    ]

    if any(phrase in lower for phrase in bad_phrases):
        return True

    if EXCLUDE_ALCOHOLIC_DRINKS and category == "restaurant" and contains_alcohol(name):
        return True

    return False


def trim_name(name: str) -> str:
    name = normalize_text(name)

    separators = [
        " Açıklama:",
        " Aciklama:",
        " İçindekiler:",
        " Icindekiler:",
        " Detay:",
        " Seçmeli:",
        " Secmeli:",
        " Ana Yemek:",
        " Başlangıç:",
        " Baslangic:",
        " Yan Lezzetler:",
        " İçecek:",
        " Icecek:",
        " Dahil:",
        " Hariç:",
        " Haric:",
    ]

    lower = name.lower()

    for sep in separators:
        idx = lower.find(sep.lower())

        if idx != -1:
            name = name[:idx].strip()
            lower = name.lower()

    if len(name) > 100 and "." in name:
        name = name.split(".")[0].strip()

    return name.strip(" -:|•.,;")


# ============================================================
# PRICE EXTRACTION
# ============================================================

def valid_value_for_category(price: str, category: str) -> bool:
    try:
        value = float(price)
    except ValueError:
        return False

    if category == "restaurant":
        return 10 <= value <= 30_000

    if category == "venue":
        return 50 <= value <= 10_000_000

    return False


def add_item(items: list[PriceItem], name: str, price: str, category: str, page_title: str = "") -> None:
    name = sanitize_csv_name(name)
    price = normalize_price(price)

    if not name or price is None:
        return

    name = PRICE_WITH_CURRENCY_REGEX.sub(" ", name)
    name = sanitize_csv_name(name)
    name = trim_name(name)
    name = sanitize_csv_name(name)

    if category == "venue":
        clean_title = re.sub(r"\s*-\s*.*$", "", page_title).strip()
        clean_title = sanitize_csv_name(clean_title)

        if clean_title and name and clean_title.lower() not in name.lower():
            name = f"{clean_title} - {name}"

        name = sanitize_csv_name(name)

    if not name or len(name) < 2:
        return

    if not valid_value_for_category(price, category):
        return

    if looks_like_bad_name(name, category):
        return

    items.append(PriceItem(name=name, price=price))


def extract_items_from_text(text: str, category: str, page_title: str = "") -> list[PriceItem]:
    text = repair_mojibake_if_needed(str(text))
    text = normalize_text(text)

    items: list[PriceItem] = []

    if not text:
        return items

    # 1) Para birimli fiyatlar: Kıymalı Pide 260 TL
    matches = list(PRICE_WITH_CURRENCY_REGEX.finditer(text))
    previous_price_end = 0

    for match in matches:
        raw_price = match.group(0)
        price = normalize_price(raw_price)

        if price is None:
            previous_price_end = match.end()
            continue

        before_segment = text[previous_price_end:match.start()]
        before_segment = normalize_text(before_segment)

        if len(before_segment) > 150:
            before_segment = before_segment[-150:]

        name = before_segment

        if len(name) < 2:
            name = text[max(0, match.start() - 100):match.start()]
            name = normalize_text(name)

        if len(name) < 2:
            name = text[match.end():match.end() + 100]
            name = normalize_text(name)

        add_item(items, name, price, category, page_title)
        previous_price_end = match.end()

    # 2) Para birimsiz ama satır sonunda fiyat: Kıymalı Pide 260
    if not items:
        m = NAME_ENDS_WITH_PRICE_REGEX.match(text)

        if m:
            name = m.group(1)
            price = m.group(2)
            add_item(items, name, price, category, page_title)

    return items


def extract_prices_line_based(soup: BeautifulSoup, category: str, page_title: str = "") -> list[PriceItem]:
    text = soup.get_text("\n", strip=True)
    text = repair_mojibake_if_needed(text)

    raw_lines = text.splitlines()
    lines = []

    for line in raw_lines:
        line = sanitize_csv_name(line)

        if not line:
            continue

        if len(line) > 240:
            continue

        lines.append(line)

    items: list[PriceItem] = []

    last_clean_name = ""

    for i, line in enumerate(lines):
        line_has_price = False

        # A) Aynı satırda TL/₺ var.
        matches = list(PRICE_WITH_CURRENCY_REGEX.finditer(line))

        if matches:
            line_has_price = True
            previous_price_end = 0

            for match in matches:
                price = normalize_price(match.group(0))

                if price is None:
                    previous_price_end = match.end()
                    continue

                name = line[previous_price_end:match.start()]
                name = sanitize_csv_name(name)

                if len(name) < 2:
                    name = last_clean_name

                if len(name) < 2 and i > 0:
                    name = lines[i - 1]

                if len(name) < 2:
                    name = line[match.end():]

                add_item(items, name, price, category, page_title)
                previous_price_end = match.end()

        # B) Satır sadece fiyat: önceki satırı isim al.
        elif PURE_PRICE_LINE_REGEX.match(line):
            price = normalize_price(line)

            if price is not None and last_clean_name:
                line_has_price = True
                add_item(items, last_clean_name, price, category, page_title)

        # C) Satır sonunda çıplak fiyat: Kıymalı Pide 260
        else:
            m = NAME_ENDS_WITH_PRICE_REGEX.match(line)

            if m:
                possible_name = sanitize_csv_name(m.group(1))
                possible_price = normalize_price(m.group(2))

                if possible_price is not None:
                    line_has_price = True
                    add_item(items, possible_name, possible_price, category, page_title)

        # Son temiz isim adayını güncelle.
        if not line_has_price:
            possible_name = sanitize_csv_name(line)

            if (
                possible_name
                and len(possible_name) >= 2
                and not PURE_PRICE_LINE_REGEX.match(possible_name)
                and not looks_like_bad_name(possible_name, category)
            ):
                last_clean_name = possible_name

    return items


def extract_prices_from_page(html: str, category: str) -> list[PriceItem]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    page_title = ""

    if soup.title and soup.title.string:
        page_title = normalize_text(soup.title.string)

    items: list[PriceItem] = []

    # 1) Tag-based extraction
    candidate_tags = soup.find_all([
        "h1", "h2", "h3", "h4", "h5",
        "p", "li", "span", "td", "tr", "strong", "div"
    ])

    for tag in candidate_tags:
        text = normalize_text(tag.get_text(" ", strip=True))
        text = repair_mojibake_if_needed(text)

        if not text:
            continue

        if len(text) > 900:
            continue

        if (
            not PRICE_WITH_CURRENCY_REGEX.search(text)
            and not NAME_ENDS_WITH_PRICE_REGEX.match(text)
        ):
            continue

        items.extend(extract_items_from_text(text, category, page_title))

    # 2) Line-based fallback
    items.extend(extract_prices_line_based(soup, category, page_title))

    return items


# ============================================================
# URL COLLECTION
# ============================================================

def parse_xml_locs(xml_text: str) -> list[str]:
    locs = []

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))

        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text:
                locs.append(elem.text.strip())

    except Exception:
        return []

    return locs


def get_sitemap_urls_for_domain(base_url: str, category: str) -> set[str]:
    parsed = urlparse(base_url)
    root_url = f"{parsed.scheme}://{parsed.netloc}"

    sitemap_queue = [
        f"{root_url}/sitemap.xml",
        f"{root_url}/sitemap_index.xml",
        f"{root_url}/post-sitemap.xml",
        f"{root_url}/page-sitemap.xml",
    ]

    checked_sitemaps = set()
    found_urls = set()

    while sitemap_queue and len(checked_sitemaps) < 25:
        sitemap_url = normalize_url(sitemap_queue.pop(0))

        if sitemap_url in checked_sitemaps:
            continue

        checked_sitemaps.add(sitemap_url)

        xml_text = fetch(sitemap_url)

        if not xml_text:
            continue

        locs = parse_xml_locs(xml_text)

        for loc in locs:
            loc = normalize_url(loc)
            lower = loc.lower()

            if lower.endswith(".xml") or "sitemap" in lower:
                if loc not in checked_sitemaps:
                    sitemap_queue.append(loc)
                continue

            if is_relevant_url(loc, category):
                found_urls.add(loc)

    return found_urls


def crawl_start_pages(source: dict) -> set[str]:
    category = source["category"]
    start_urls = [normalize_url(u) for u in source["start_urls"]]
    allowed_domains = {get_domain(u) for u in start_urls}

    visited = set()
    queue = list(start_urls)
    found_urls = set()

    while queue and len(visited) < MAX_CRAWL_PAGES_PER_SOURCE:
        url = normalize_url(queue.pop(0))

        if url in visited:
            continue

        visited.add(url)

        html = fetch(url)

        if not html:
            continue

        if is_relevant_url(url, category):
            found_urls.add(url)

        soup = BeautifulSoup(html, "lxml")

        for a in soup.find_all("a", href=True):
            href = normalize_url(urljoin(url, a["href"]))

            if not href.startswith("http"):
                continue

            if not same_domain(href, allowed_domains):
                continue

            if href in visited:
                continue

            if is_relevant_url(href, category):
                found_urls.add(href)

                if len(queue) < MAX_CRAWL_PAGES_PER_SOURCE:
                    queue.append(href)

    return found_urls


def collect_candidate_urls(source: dict) -> list[str]:
    category = source["category"]
    start_urls = source["start_urls"]

    candidates = set()
    checked_domains = set()

    for start_url in start_urls:
        candidates.add(normalize_url(start_url))

    for start_url in start_urls:
        domain = get_domain(start_url)

        if domain in checked_domains:
            continue

        checked_domains.add(domain)

        candidates.update(get_sitemap_urls_for_domain(start_url, category))

    candidates.update(crawl_start_pages(source))

    sorted_urls = sorted(
        candidates,
        key=lambda u: score_url(u, category),
        reverse=True
    )

    return sorted_urls[:MAX_URLS_PER_SOURCE]


# ============================================================
# SCRAPE / CSV
# ============================================================

def scrape_url(url: str, category: str) -> tuple[str, list[PriceItem]]:
    html = fetch(url)

    if not html:
        return url, []

    return url, extract_prices_from_page(html, category)


def deduplicate_items(items: list[PriceItem], category: str) -> list[PriceItem]:
    seen = set()
    unique = []

    for item in items:
        clean_name = sanitize_csv_name(item.name)
        clean_price = normalize_price(item.price)

        if not clean_name or clean_price is None:
            continue

        if looks_like_bad_name(clean_name, category):
            continue

        key = (clean_name.lower(), clean_price)

        if key in seen:
            continue

        seen.add(key)
        unique.append(PriceItem(clean_name, clean_price))

    return unique


def write_csv(source_name: str, items: list[PriceItem]) -> Path:
    safe_name = clean_filename(source_name)
    output_path = OUTPUT_DIR / f"{safe_name}_{TODAY}.csv"

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(["isim", "fiyat"])

        for item in items:
            clean_name = sanitize_csv_name(item.name)
            clean_price = item.price

            if not clean_name:
                continue

            clean_name = clean_name.replace(",", " - ")

            writer.writerow([clean_name, clean_price])

    return output_path


def scrape_source(source: dict) -> None:
    source_name = source["name"]
    category = source["category"]

    print("=" * 80)
    print(f"SOURCE: {source_name}")
    print(f"CATEGORY: {category}")
    print("=" * 80)

    urls = collect_candidate_urls(source)

    print(f"Candidate URL count: {len(urls)}")

    all_items: list[PriceItem] = []

    if not urls:
        output_path = write_csv(source_name, [])
        print(f"No candidate URLs. Empty CSV saved: {output_path}")
        print()
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(scrape_url, url, category): url
            for url in urls
        }

        completed = 0

        for future in as_completed(future_to_url):
            completed += 1
            url = future_to_url[future]

            try:
                _, items = future.result()
                all_items.extend(items)

                if PRINT_PROGRESS:
                    print(
                        f"[{completed}/{len(urls)}] {source_name} | "
                        f"items: {len(items)} | {url}",
                        flush=True
                    )

            except Exception as e:
                print(f"ERROR scraping {url}: {e}", flush=True)

    all_items = deduplicate_items(all_items, category)
    output_path = write_csv(source_name, all_items)

    print(f"Saved: {output_path}")
    print(f"Row count: {len(all_items)}")
    print()


def main():
    sources = SOURCES[:1] if ONLY_FIRST_SOURCE else SOURCES

    for source in sources:
        scrape_source(source)


if __name__ == "__main__":
    main()