import asyncio
import os
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


BASE_URL = "https://kozmetik.avon.com.tr"
MARKET_NAME = "avon"
OUTPUT_ROOT = "data"

# Hız ayarları
MAX_PAGES = 140
CONCURRENT_PAGES = 5
WAIT_AFTER_OPEN_MS = 1000
SCROLL_COUNT = 4
SCROLL_WAIT_MS = 350

# En önemli hız ayarı:
# Ürün detay sayfalarına girerse aşırı duplicate ve yavaşlık oluyor.
VISIT_PRODUCT_PAGES = False

START_URLS = [
    "https://kozmetik.avon.com.tr/",
    "https://kozmetik.avon.com.tr/1214-1215/yeni-gelenler/yeni-gelenler",
    "https://kozmetik.avon.com.tr/1236/online-ozel",
    "https://kozmetik.avon.com.tr/1553/149tl-ve-altindaki-urunler",
    "https://kozmetik.avon.com.tr/301/parfum",
    "https://kozmetik.avon.com.tr/301-307/parfum/kadin-parfum",
    "https://kozmetik.avon.com.tr/301-308/parfum/erkek-parfum",
    "https://kozmetik.avon.com.tr/302/makyaj",
    "https://kozmetik.avon.com.tr/302-310/makyaj/yuz-makyaji",
    "https://kozmetik.avon.com.tr/302-311/makyaj/goz-makyaji",
    "https://kozmetik.avon.com.tr/302-312/makyaj/dudak-makyaji",
    "https://kozmetik.avon.com.tr/303/cilt-bakimi",
    "https://kozmetik.avon.com.tr/304/kisisel-bakim",
    "https://kozmetik.avon.com.tr/304-383/kisisel-bakim/erkek-bakim-urunleri",
    "https://kozmetik.avon.com.tr/304-469/kisisel-bakim/avon-care",
    "https://kozmetik.avon.com.tr/1204-1205/erkek/erkek",
]

PRICE_REGEX = re.compile(
    r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*TL",
    re.IGNORECASE
)

TOBACCO_KEYWORDS = [
    "sigara", "tütün", "tutun", "puro", "cigar", "cigarette",
    "nargile", "snus", "rolling tobacco"
]

# Dikkat:
# "alcohol" kelimesini tek başına koymadım.
# Çünkü kozmetikte "Alcohol Denat" gibi içerik olarak geçebilir.
# Hocanın istemediği şey alcoholic beverages: bira, şarap, rakı vs.
ALCOHOLIC_BEVERAGE_KEYWORDS = [
    "bira", "şarap", "sarap", "rakı", "raki", "votka", "vodka",
    "viski", "whisky", "whiskey", "cin", "gin", "rom",
    "tekila", "tequila", "likör", "likor",
    "şampanya", "sampanya",
    "alkollü içecek", "alkollu icecek",
    "alcoholic beverage", "alcoholic beverages"
]

BAD_NAME_LINES = {
    "sepete ekle",
    "şimdi dene",
    "simdi dene",
    "renk seçeneklerini gör",
    "renk seceneklerini gor",
    "tümünü görüntüle",
    "tumunu goruntule",
    "sayfa sayfa görüntüle",
    "sayfa sayfa goruntule",
    "önceki sayfa",
    "onceki sayfa",
    "sonraki sayfa",
    "kategoriler",
    "markalar",
    "en yeniler",
    "en sevilenler",
    "çok satanlar",
    "cok satanlar",
    "fiyat",
    "sırala",
    "sirala",
    "avon",
    "birini seç",
    "birini sec",
    "filtrele",
    "göster",
    "goster",
}


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def normalize_price(price_text):
    price = price_text.lower()
    price = price.replace("tl", "")
    price = price.replace("₺", "")
    price = price.replace("*", "")
    price = price.strip()
    price = price.replace(".", "")
    return price


def safe_filename(text):
    text = text.lower()
    table = str.maketrans("ığüşöçİĞÜŞÖÇ", "igusocIGUSOC")
    text = text.translate(table)
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    text = text.strip("_").lower()
    return text[:90] if text else "page"


def should_visit_url(url):
    parsed = urlparse(url)

    if parsed.netloc and parsed.netloc != "kozmetik.avon.com.tr":
        return False

    lower_url = url.lower()
    path = parsed.path.lower()

    blocked_parts = [
        "/cart",
        "/basket",
        "/checkout",
        "/login",
        "/register",
        "/account",
        "/hesabim",
        "/sepet",
        "/odeme",
        "/uye",
        "/customer",
        "/temsilci",
        "/search",
        "javascript:",
        "mailto:",
        "tel:",
    ]

    if any(part in lower_url for part in blocked_parts):
        return False

    # Ürün detay sayfalarını gezme.
    # Bunlar çok yavaşlatıyor ve aynı ürünleri tekrar tekrar getiriyor.
    if not VISIT_PRODUCT_PAGES:
        if path.startswith("/urun/") or path.startswith("/product/"):
            return False

    if url.rstrip("/") == BASE_URL:
        return True

    # Avon kategori/kampanya URL'lerinde genelde sayı var.
    return bool(re.search(r"/\d+", path))


def classify_product(name, page_title="", url=""):
    combined = f"{name} {page_title} {url}".lower()

    if any(keyword in combined for keyword in TOBACCO_KEYWORDS):
        return "tobacco"

    if any(keyword in combined for keyword in ALCOHOLIC_BEVERAGE_KEYWORDS):
        return "alcohol"

    return "normal"


async def accept_cookies_if_visible(page):
    possible_texts = [
        "Kabul Et",
        "Tümünü Kabul Et",
        "Tamam",
        "Accept",
        "Accept All",
    ]

    for text in possible_texts:
        try:
            locator = page.get_by_text(text, exact=False)
            if await locator.count() > 0:
                await locator.first.click(timeout=1000)
                await page.wait_for_timeout(300)
                return
        except Exception:
            pass


async def fast_scroll(page):
    previous_height = 0

    for _ in range(SCROLL_COUNT):
        current_height = await page.evaluate("document.body.scrollHeight")

        if current_height == previous_height:
            break

        previous_height = current_height
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(SCROLL_WAIT_MS)


def extract_links_from_html(html, current_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        if not href:
            continue

        full_url = urljoin(current_url, href)
        full_url = full_url.split("#")[0].split("?")[0]

        if should_visit_url(full_url):
            links.add(full_url)

    return links


def extract_products_from_text(text):
    lines = [normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    products = []

    for i, line in enumerate(lines):
        price_matches = PRICE_REGEX.findall(line)

        if not price_matches:
            continue

        # Aynı satırda eski/yeni fiyat varsa son fiyatı al.
        price = normalize_price(price_matches[-1])
        product_name = None

        # Fiyatın üstünden ürün adını arıyoruz.
        for j in range(i - 1, max(-1, i - 12), -1):
            candidate = normalize_text(lines[j])
            lower = candidate.lower()

            if lower in BAD_NAME_LINES:
                continue

            if PRICE_REGEX.search(candidate):
                continue

            if len(candidate) < 4:
                continue

            if "yıldız" in lower or "yildiz" in lower:
                continue

            if "yorum" in lower:
                continue

            if lower.startswith("{{") or lower.endswith("}}"):
                continue

            if "[view|" in lower:
                continue

            product_name = candidate
            break

        if product_name:
            products.append((product_name, price))

    return deduplicate_products(products)


def deduplicate_products(products):
    seen = set()
    result = []

    for name, price in products:
        name = normalize_text(name)
        price = normalize_text(price)

        if not name or not price:
            continue

        key = (name.lower(), price)

        if key in seen:
            continue

        seen.add(key)
        result.append((name, price))

    return result


def save_page_products(url, title, products):
    today = datetime.now().strftime("%Y-%m-%d")

    parsed = urlparse(url)
    page_name = parsed.path.strip("/").split("/")[-1] or "homepage"
    page_name = safe_filename(page_name)

    folders = {
        "normal": os.path.join(OUTPUT_ROOT, MARKET_NAME, "market_data", today),
        "tobacco": os.path.join(OUTPUT_ROOT, MARKET_NAME, "restricted_products", "tobacco", today),
        "alcohol": os.path.join(OUTPUT_ROOT, MARKET_NAME, "restricted_products", "alcoholic_beverages", today),
    }

    for folder in folders.values():
        os.makedirs(folder, exist_ok=True)

    rows = {
        "normal": [],
        "tobacco": [],
        "alcohol": [],
    }

    for name, price in products:
        product_type = classify_product(name, title, url)
        rows[product_type].append(f"{name};{price}")

    for product_type, product_rows in rows.items():
        if not product_rows:
            continue

        output_path = os.path.join(folders[product_type], f"{page_name}.csv")

        with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
            file.write("name;price\n")
            file.write("\n".join(product_rows))

    print(
        f"[SAVED] {page_name} | "
        f"normal={len(rows['normal'])}, "
        f"tobacco={len(rows['tobacco'])}, "
        f"alcohol={len(rows['alcohol'])}"
    )


def save_global_unique(all_products):
    today = datetime.now().strftime("%Y-%m-%d")

    normal_folder = os.path.join(OUTPUT_ROOT, MARKET_NAME, "all_unique", today)
    tobacco_folder = os.path.join(OUTPUT_ROOT, MARKET_NAME, "restricted_products", "tobacco", today)
    alcohol_folder = os.path.join(OUTPUT_ROOT, MARKET_NAME, "restricted_products", "alcoholic_beverages", today)

    os.makedirs(normal_folder, exist_ok=True)
    os.makedirs(tobacco_folder, exist_ok=True)
    os.makedirs(alcohol_folder, exist_ok=True)

    normal_rows = []
    tobacco_rows = []
    alcohol_rows = []

    for name, price in sorted(all_products.values(), key=lambda item: item[0].lower()):
        product_type = classify_product(name)
        row = f"{name};{price}"

        if product_type == "tobacco":
            tobacco_rows.append(row)
        elif product_type == "alcohol":
            alcohol_rows.append(row)
        else:
            normal_rows.append(row)

    normal_path = os.path.join(normal_folder, "all_products.csv")

    with open(normal_path, "w", encoding="utf-8-sig", newline="") as file:
        file.write("name;price\n")
        file.write("\n".join(normal_rows))

    if tobacco_rows:
        tobacco_path = os.path.join(tobacco_folder, "all_tobacco_products.csv")
        with open(tobacco_path, "w", encoding="utf-8-sig", newline="") as file:
            file.write("name;price\n")
            file.write("\n".join(tobacco_rows))

    if alcohol_rows:
        alcohol_path = os.path.join(alcohol_folder, "all_alcoholic_beverages.csv")
        with open(alcohol_path, "w", encoding="utf-8-sig", newline="") as file:
            file.write("name;price\n")
            file.write("\n".join(alcohol_rows))

    # --- Standart tek dosya çıktısı: InflationItems/Datas/Cosmetics/Avon/avon_YYYY-MM-DD.csv ---
    try:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(this_dir, "..", "..", "..", ".."))
        datas_avon_dir = os.path.join(project_root, "InflationItems", "Datas", "Cosmetics", "Avon")
        os.makedirs(datas_avon_dir, exist_ok=True)
        consolidated_csv = os.path.join(datas_avon_dir, f"avon_{today}.csv")
        with open(consolidated_csv, "w", encoding="utf-8-sig", newline="") as file:
            file.write("product_name,price\n")
            for name, price in sorted(all_products.values(), key=lambda item: item[0].lower()):
                file.write(f'"{name}",{price}\n')
        print(f"[CONSOLIDATED FILE] {consolidated_csv}")
    except Exception as e:
        print(f"[CONSOLIDATED ERROR] {e}")

    print(f"[GLOBAL SAVED] normal rows={len(normal_rows)}")
    print(f"[GLOBAL SAVED] tobacco rows={len(tobacco_rows)}")
    print(f"[GLOBAL SAVED] alcohol rows={len(alcohol_rows)}")
    print(f"[GLOBAL FILE] {normal_path}")


async def scrape_page(context, url):
    page = await context.new_page()

    try:
        # domcontentloaded networkidle'dan çok daha hızlı.
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45000
        )

        status = response.status if response else "NO_RESPONSE"

        await page.wait_for_timeout(WAIT_AFTER_OPEN_MS)
        await accept_cookies_if_visible(page)
        await fast_scroll(page)

        html = await page.content()
        text = await page.locator("body").inner_text(timeout=8000)
        title = await page.title()

        links = extract_links_from_html(html, url)
        products = extract_products_from_text(text)

        if products:
            save_page_products(url, title, products)

        print(
            f"[OK] {url} | status={status} | "
            f"products={len(products)} | links={len(links)}"
        )

        if len(products) == 0:
            os.makedirs("debug_html", exist_ok=True)
            debug_name = safe_filename(urlparse(url).path.strip("/") or "homepage")
            debug_path = os.path.join("debug_html", f"{debug_name}.html")

            with open(debug_path, "w", encoding="utf-8") as file:
                file.write(html)

        return links, products

    except Exception as error:
        print(f"[ERROR] {url} -> {error}")
        return set(), []

    finally:
        await page.close()


async def main():
    visited = set()
    queued = set(START_URLS)
    queue = list(START_URLS)
    all_products = {}

    async with async_playwright() as playwright:
        # Firefox, sende Chromium'dan daha stabil çalışmıştı.
        browser = await playwright.firefox.launch(
            headless=True
        )

        context = await browser.new_context(
            locale="tr-TR",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
                "Gecko/20100101 Firefox/125.0"
            )
        )

        while queue and len(visited) < MAX_PAGES:
            batch = []

            while queue and len(batch) < CONCURRENT_PAGES and len(visited) < MAX_PAGES:
                url = queue.pop(0)

                if url in visited:
                    continue

                visited.add(url)
                batch.append(url)

            if not batch:
                break

            tasks = [scrape_page(context, url) for url in batch]
            results = await asyncio.gather(*tasks)

            for links, products in results:
                for name, price in products:
                    # Aynı ürün farklı sayfada tekrar çıkarsa tek tut.
                    all_products[name.lower()] = (name, price)

                for link in links:
                    if link not in visited and link not in queued:
                        queued.add(link)
                        queue.append(link)

            print(
                f"[PROGRESS] visited={len(visited)} "
                f"queue={len(queue)} "
                f"unique_products={len(all_products)}"
            )

            # Çok kısa nefes. Siteyi gereksiz zorlamamak için.
            await asyncio.sleep(0.25)

        await browser.close()

    save_global_unique(all_products)

    print("\n[DONE]")
    print(f"Visited pages: {len(visited)}")
    print(f"Unique products: {len(all_products)}")
    print(f"Output root: {OUTPUT_ROOT}/{MARKET_NAME}")


if __name__ == "__main__":
    asyncio.run(main())