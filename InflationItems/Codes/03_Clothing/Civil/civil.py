import requests
import csv
import time
import json
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime
from xml.etree import ElementTree as ET

BASE_URL = "https://www.civilim.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)

# Sadece kıyafetle alakalı collection handle'ları
ALLOWED_COLLECTION_HANDLES = {
    # Bebek
    "sweatshirt",
    "esofman-alt",
    "takimlar",
    "citcitli-badi",
    "hirka-ve-yelek",
    "kazak-sueter",
    "uyku-tulumu",
    "mont-kaban-ve-yagmurluk",
    "tulum-salopet",
    "elbise",
    "pantolon",
    "jean",
    "gomlek",
    "tayt",
    "hastane-cikisi-zibinlar",
    "tisort",
    "kapri-sort",
    "ic-giyim",
    "pijama",
    "corap",

    # Kız çocuk
    "kiz-cocuk-sweatshirt",
    "kiz-cocuk-esofman",
    "kiz-cocuk-takim",
    "hirka-yelek-ve-bolero",
    "kiz-cocuk-kazak-ve-sueter",
    "kiz-cocuk-uyku-tulumu",
    "kiz-cocuk-mont-kaban-ve-yagmurluk",
    "elbise-ve-jile",
    "kiz-cocuk-pantolon",
    "etek",
    "kiz-cocuk-jean",
    "kiz-cocuk-gomlek",
    "kiz-cocuk-tayt",
    "kiz-cocuk-tulum-salopet",
    "kiz-cocuk-kapri-sort",
    "kiz-cocuk-tisort",
    "plaj-giyim",
    "kiz-cocuk-ic-giyim",
    "pijama-takimi",
    "coraplar",

    # Erkek çocuk
    "erkek-cocuk-sweatshirt",
    "erkek-cocuk-esofman",
    "erkek-cocuk-takimlar",
    "erkek-cocuk-hirka-yelek",
    "erkek-cocuk-kazak-ve-suveter",
    "erkek-cocuk-uyku-tulumu",
    "erkek-cocuk-mont-kaban-ve-yagmurluk",
    "erkek-cocuk-pantolon",
    "erkek-cocuk-gomlek",
    "erkek-cocuk-tulum-salopet",
    "erkek-cocuk-jean",
    "erkek-cocuk-tisort",
    "erkek-cocuk-sort",
    "erkek-cocuk-kapri",
    "erkek-cocuk-plaj-giyim",
    "erkek-cocuk-pijama-takimi",
    "erkek-cocuk-ic-giyim",
    "erkek-cocuk-corap",

    # Anne & Hamile -> sadece giyim olanlar
    "hamile-pijama-takimi",
    "hamile-ic-giyim",
}

ALLOWED_URL_KEYWORDS = {
    "sweatshirt",
    "esofman",
    "takim",
    "badi",
    "hirka",
    "yelek",
    "kazak",
    "sueter",
    "suveter",
    "uyku-tulumu",
    "mont",
    "kaban",
    "yagmurluk",
    "tulum",
    "salopet",
    "elbise",
    "pantolon",
    "jean",
    "gomlek",
    "tayt",
    "zibin",
    "tisort",
    "sort",
    "kapri",
    "ic-giyim",
    "pijama",
    "corap",
    "plaj-giyim",
    "etek",
    "bolero",
    "hamile-pijama",
    "hamile-ic-giyim",
}

EXCLUDED_URL_KEYWORDS = {
    "ayakkabi",
    "terlik",
    "sandalet",
    "bot",
    "cizme",
    "babet",
    "panduf",
    "patik",
    "deniz-ayakkabisi",
    "spor-ayakkabi",
    "klasik-ayakkabi",
    "ilk-adim-ayakkabisi",

    "aksesuar",
    "taki",
    "sac-aksesuari",
    "sapka",
    "kemer",
    "aski",
    "gozluk",
    "saat",

    "battaniye",
    "kundak",
    "mobilya",
    "bebek-odasi",
    "guvenlik",
    "kamera",
    "telsiz",
    "yatak",
    "tekstil",
    "mama",
    "bakim",
    "temizlik",
    "gida",
    "emzirme-urunleri",
    "emzirme-ve-destek-minderi",
    "bebek-bakim-cantasi",
    "hamile-bakim-urunleri",
    "sut-arttirici-gidalar",
    "emzirme-ortusu",
    "lisansli-koleksiyonlar",
    "kostum-ve-aksesuar",
    "pierre-cardin",
}

PRODUCT_EXCLUDE_KEYWORDS = {
    "mama sandalyesi",
    "mama-sandalyesi",
    "minderli mama sandalyesi",
    "ana kucagi",
    "ana-kucagi",
    "oto koltugu",
    "oto-koltugu",
    "bebek arabasi",
    "bebek-arabasi",
    "park yatak",
    "park-yatak",
    "besik",
    "oyuncak",

    "islak mendil",
    "islak-mendil",
    "mendil",
    "bebek bezi",
    "bebek-bezi",
    "premium maxi",
    "molfix",
    "uni baby",
    "hassas dokunus",

    "devam sutu",
    "devam sütü",
    "optipro",
    "probiyotik",
    "probiotic",
    "sma",
    "gida",
    "vitamin",
    "takviye",
    "supplement",

    "bakim",
    "sampuan",
    "krem",
    "losyon",
    "sabun",
    "temizlik",
    "pamuk",
    "ped",
    "gogus pedi",

    "aksesuar",
    "taki",
    "sapka",
    "gozluk",
    "saat",
    "kemer",
    "canta",
    "toka",

    "ayakkabi",
    "terlik",
    "sandalet",
    "bot",
    "cizme",
    "babet",
    "panduf",
    "patik",
    "sneaker",

    "battaniye",
    "kundak",
    "nevresim",
    "carsaf",
    "yastik",
    "yorgan",
    "ortu",
    "emzirme",
    "destek minderi",
    "bakim cantasi",
    "sut arttirici",
    "pierre cardin",
}


def get_xml(url: str) -> ET.Element:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return ET.fromstring(r.content)


def clean_price(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Shopify js bazen kuruş olarak dönebiliyor
        if value > 1000:
            return round(float(value) / 100, 2)
        return round(float(value), 2)

    text = str(value).strip()
    text = text.replace("TL", "").replace("₺", "").replace("\xa0", " ")
    text = text.replace(".", "").replace(",", ".")
    text = re.sub(r"[^\d.]", "", text)

    if not text:
        return None

    try:
        return round(float(text), 2)
    except ValueError:
        return None


def normalize_text(text: str) -> str:
    if text is None:
        return ""

    text = str(text).strip().lower()
    replacements = {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "&": "-",
        " ": "-",
        "/": "-",
        ",": "",
        ".": "",
        "'": "",
        '"': "",
        "(": "",
        ")": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def normalize_loose(text: str) -> str:
    if text is None:
        return ""

    text = str(text).lower()
    replacements = {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "-": " ",
        "_": " ",
        "/": " ",
        "&": " ",
        ",": " ",
        ".": " ",
        "(": " ",
        ")": " ",
        "'": " ",
        '"': " ",
        "\n": " ",
        "\t": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    return re.sub(r"\s+", " ", text).strip()


def extract_collection_handle(url: str):
    m = re.search(r"/collections/([^/?#]+)", url.lower())
    return m.group(1) if m else None


def is_allowed_collection(url: str) -> bool:
    url_lower = url.lower()

    if any(x in url_lower for x in EXCLUDED_URL_KEYWORDS):
        return False

    handle = extract_collection_handle(url)
    if handle:
        normalized_handle = normalize_text(handle)
        if normalized_handle in ALLOWED_COLLECTION_HANDLES:
            return True

    return any(x in url_lower for x in ALLOWED_URL_KEYWORDS)


def discover_collection_sitemaps():
    sitemap_index_url = f"{BASE_URL}/sitemap.xml"
    root = get_xml(sitemap_index_url)

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = []

    for loc in root.findall(".//sm:loc", ns):
        url = (loc.text or "").strip()
        if "sitemap_collections_" in url:
            sitemap_urls.append(url)

    return sitemap_urls


def get_collection_urls_from_sitemap(sitemap_url):
    root = get_xml(sitemap_url)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls = []
    for loc in root.findall(".//sm:loc", ns):
        url = (loc.text or "").strip()
        if "/collections/" in url:
            urls.append(url)

    return urls


def discover_allowed_collections():
    sitemap_urls = discover_collection_sitemaps()
    print(f"{len(sitemap_urls)} adet collection sitemap bulundu.")

    collection_urls = []
    for sitemap_url in sitemap_urls:
        try:
            collection_urls.extend(get_collection_urls_from_sitemap(sitemap_url))
        except Exception as e:
            print(f"Sitemap okunamadı: {sitemap_url} -> {e}")

    collection_urls = list(dict.fromkeys(collection_urls))
    allowed = [url for url in collection_urls if is_allowed_collection(url)]

    print(f"{len(allowed)} adet izinli kıyafet collection bulundu.")
    return allowed


def get_product_urls_from_collection(collection_url, delay=0.2, max_pages=100):
    found = set()

    for page in range(1, max_pages + 1):
        url = f"{collection_url}?page={page}"

        try:
            r = session.get(url, timeout=30)
        except Exception as e:
            print(f"Sayfa isteği başarısız: {url} -> {e}")
            break

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        page_found = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "/products/" in href:
                full_url = href if href.startswith("http") else BASE_URL + href
                full_url = full_url.split("?")[0].rstrip("/")
                page_found.add(full_url)

        new_items = page_found - found

        if not page_found:
            break

        if not new_items:
            break

        found.update(new_items)
        print(f"{collection_url} | sayfa {page} -> {len(new_items)} yeni ürün")
        time.sleep(delay)

    return list(found)


def parse_product_js(product_url):
    js_url = product_url.rstrip("/") + ".js"

    try:
        r = session.get(js_url, timeout=30)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    try:
        data = r.json()
    except json.JSONDecodeError:
        return None

    variants = data.get("variants", [])
    first_variant = variants[0] if variants else {}

    price = clean_price(first_variant.get("price"))
    compare_at_price = clean_price(first_variant.get("compare_at_price"))

    available = None
    if variants:
        available = any(v.get("available", False) for v in variants)

    total_inventory = 0
    inventory_known = False
    for v in variants:
        inv = v.get("inventory_quantity")
        if inv is not None:
            inventory_known = True
            total_inventory += inv

    image_url = None
    images = data.get("images") or []
    if images:
        image_url = images[0]

    tags = data.get("tags")
    if isinstance(tags, list):
        tags = ", ".join(tags)
    elif tags is None:
        tags = None
    else:
        tags = str(tags)

    title = data.get("title")
    handle = data.get("handle")

    return {
        "product_url": product_url,
        "handle": handle,
        "title": title,
        "vendor": data.get("vendor"),
        "product_type": data.get("type"),
        "tags": tags,
        "price_try": price,
        "compare_at_price_try": compare_at_price,
        "discount_rate": (
            round((compare_at_price - price) / compare_at_price * 100, 2)
            if price is not None and compare_at_price is not None and compare_at_price > price
            else None
        ),
        "available": available,
        "inventory_quantity": total_inventory if inventory_known else None,
        "variant_count": len(variants),
        "image_url": image_url,
    }


def parse_product_html(product_url):
    r = session.get(product_url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True)

    text = soup.get_text("\n", strip=True)

    prices = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL", text, re.IGNORECASE)
    price_try = clean_price(prices[0]) if prices else None
    compare_at_price_try = clean_price(prices[1]) if len(prices) > 1 else None

    available = None
    text_lower = text.lower()
    if "stoğa gelince haber ver" in text_lower and "sepete ekle" not in text_lower:
        available = False
    elif "sepete ekle" in text_lower:
        available = True

    image_url = None
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        image_url = og_image["content"]

    vendor = None
    vendor_meta = soup.find("meta", attrs={"property": "og:site_name"})
    if vendor_meta and vendor_meta.get("content"):
        vendor = vendor_meta["content"]

    handle = product_url.rstrip("/").split("/")[-1]

    return {
        "product_url": product_url,
        "handle": handle,
        "title": title,
        "vendor": vendor,
        "product_type": None,
        "tags": None,
        "price_try": price_try,
        "compare_at_price_try": compare_at_price_try,
        "discount_rate": (
            round((compare_at_price_try - price_try) / compare_at_price_try * 100, 2)
            if price_try is not None and compare_at_price_try is not None and compare_at_price_try > price_try
            else None
        ),
        "available": available,
        "inventory_quantity": None,
        "variant_count": None,
        "image_url": image_url,
    }


def is_invalid_title(title) -> bool:
    t = normalize_loose(title)

    if not t:
        return True

    bad_patterns = {
        "civilim com",
        "civilcim com",
        "civil com",
        "www civilim com",
    }

    return t in bad_patterns


def is_excluded_product(product: dict) -> bool:
    combined = " ".join([
        str(product.get("title") or ""),
        str(product.get("handle") or ""),
        str(product.get("product_type") or ""),
        str(product.get("tags") or ""),
    ])

    t = normalize_loose(combined)
    return any(keyword in t for keyword in PRODUCT_EXCLUDE_KEYWORDS)


def scrape_clothing_products(delay=0.2):
    scrape_date = datetime.now().strftime("%Y-%m-%d")
    scrape_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    allowed_collections = discover_allowed_collections()

    product_urls = []
    for collection_url in allowed_collections:
        try:
            urls = get_product_urls_from_collection(collection_url, delay=delay)
            product_urls.extend(urls)
        except Exception as e:
            print(f"Collection hatası: {collection_url} -> {e}")

    product_urls = list(dict.fromkeys(product_urls))
    print(f"Toplam {len(product_urls)} benzersiz ürün URL'si bulundu.")

    rows = []
    filtered_out = 0
    errors = 0

    for i, product_url in enumerate(product_urls, start=1):
        try:
            data = parse_product_js(product_url)
            if data is None:
                data = parse_product_html(product_url)

            if data is None:
                filtered_out += 1
                continue

            if is_invalid_title(data.get("title")):
                filtered_out += 1
                continue

            if is_excluded_product(data):
                filtered_out += 1
                continue

            data["scrape_date"] = scrape_date
            data["scrape_timestamp"] = scrape_timestamp
            rows.append(data)

            if i % 50 == 0:
                print(f"{i}/{len(product_urls)} işlendi... | kayıt: {len(rows)} | elenen: {filtered_out}")

        except Exception as e:
            errors += 1
            print(f"Hata: {product_url} -> {e}")

        time.sleep(delay)

    print(f"Elenen kayıt: {filtered_out}")
    print(f"Hatalı kayıt: {errors}")
    return rows


def save_to_csv(rows):
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"civil_clothing_products_{today}.csv"

    fieldnames = [
        "scrape_date",
        "scrape_timestamp",
        "title",
        "handle",
        "vendor",
        "product_type",
        "tags",
        "price_try",
        "compare_at_price_try",
        "discount_rate",
        "available",
        "inventory_quantity",
        "variant_count",
        "product_url",
        "image_url",
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV kaydedildi: {filename}")
    print("Tam yol:", os.path.abspath(filename))


if __name__ == "__main__":
    rows = scrape_clothing_products(delay=0.2)
    save_to_csv(rows)
    print(f"Toplam kayıt: {len(rows)}")