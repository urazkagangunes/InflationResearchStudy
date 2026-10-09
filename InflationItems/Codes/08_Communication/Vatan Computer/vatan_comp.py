import csv
import html
import math
import random
import re
import time

from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class VatanScraper:
    BASE_URL = "https://www.vatanbilgisayar.com"
    OUTPUT_FILE = f"vatan_computer - {date.today().isoformat()}.csv"

    PRODUCTS_PER_PAGE = 24
    MAX_DEPTH = 3
    MAX_SUBCATEGORIES_PER_PAGE = 80

    CATEGORY_URLS = [
        "https://www.vatanbilgisayar.com/cep-telefonu-modelleri/",
        "https://www.vatanbilgisayar.com/bilgisayar/",
        "https://www.vatanbilgisayar.com/televizyon",
        "https://www.vatanbilgisayar.com/bilgisayar-bilesenleri/",
        "https://www.vatanbilgisayar.com/ev-mutfak/",
        "https://www.vatanbilgisayar.com/kisisel-bakim-urunleri/",
        "https://www.vatanbilgisayar.com/fotograf-makinesi-video-kamera",
        "https://www.vatanbilgisayar.com/ofis-malzemeleri/",
        "https://www.vatanbilgisayar.com/aksesuarlar/",
        "https://www.vatanbilgisayar.com/oyun-hobi",
        "https://www.vatanbilgisayar.com/iklimlendirme/",
        "https://www.vatanbilgisayar.com/outlet",
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    PRICE_RE = re.compile(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)(?:\s*)TL\b",
        re.IGNORECASE
    )

    COUNT_RE = re.compile(
        r"(\d[\d\.]*)\s+adet\s+ürün\s+bulundu",
        re.IGNORECASE
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        self.seen_product_urls = set()
        self.visited_category_urls = set()
        self.total_written = 0

    @staticmethod
    def clean_text(text):
        text = html.unescape(text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def normalize_url(self, url):
        parsed = urlparse(url)
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean.rstrip("/").lower()

    def is_rate_limited(self, status_code, text):
        text_lower = (text or "").lower()

        return (
            status_code in (403, 429)
            or "error 1015" in text_lower
            or "rate limited" in text_lower
            or "you are being rate limited" in text_lower
        )

    def fetch_html(self, url):
        for attempt in range(1, 4):
            try:
                response = self.session.get(url, timeout=30)
                text = response.text or ""

                if self.is_rate_limited(response.status_code, text):
                    wait_time = 120 * attempt
                    print(f"Rate limit/403 geldi. {wait_time} saniye bekleniyor...")
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 400:
                    print(f"HTTP hata {response.status_code}: {url}")
                    return None

                return text

            except Exception as e:
                wait_time = 15 * attempt
                print(f"İstek hatası: {e} | {wait_time} saniye bekleniyor...")
                time.sleep(wait_time)

        return None

    def get_total_product_count(self, soup):
        page_text = self.clean_text(soup.get_text(" "))
        match = self.COUNT_RE.search(page_text)

        if not match:
            return None

        raw_count = match.group(1).replace(".", "")

        try:
            return int(raw_count)
        except ValueError:
            return None

    def extract_price(self, text):
        matches = list(self.PRICE_RE.finditer(text or ""))

        if not matches:
            return None

        # Vatan listing sayfalarında güncel fiyat genelde ilk TL fiyatı oluyor.
        return self.clean_text(matches[0].group(0))

    def extract_name(self, text):
        text = self.clean_text(text)

        price_match = self.PRICE_RE.search(text)

        if price_match:
            text = text[:price_match.start()]

        junk_words = [
            "FIRSAT ÜRÜNÜ",
            "Web'e Özel Fiyat",
            "Web'e Özel",
            "Son 10 Günün En Düşük Fiyatı!",
            "Paraf ile Peşin Fiyatına 12 Taksit",
            "Paraf ile Peşin Fiyatına 9 Taksit",
            "Paraf ile Peşin Fiyatına 6 Taksit",
            "Peşin Fiyatına 12 Taksit",
            "Peşin Fiyatına 9 Taksit",
            "Peşin Fiyatına 6 Taksit",
            "Sepete Ekle",
            "Favorilere Ekle",
            "Karşılaştır",
        ]

        for word in junk_words:
            text = text.replace(word, " ")

        # Baştaki puanı temizler: 4,8 / 5,0 / 0,0 gibi.
        text = re.sub(r"^\d,\d\s+", " ", text)

        text = self.clean_text(text)

        # Baştaki ürün kodunu temizlemeye çalışır.
        # Örn: MD3Y4TU/A iPad A16... -> iPad A16...
        parts = text.split()

        if len(parts) >= 4:
            first_token = parts[0]

            looks_like_code = (
                bool(re.search(r"\d", first_token))
                and bool(re.match(r"^[A-Z0-9ÇĞİÖŞÜ./+\-_]+$", first_token))
            )

            if looks_like_code:
                text = " ".join(parts[1:])

        return self.clean_text(text)

    def parse_products_from_page(self, html_text):
        soup = BeautifulSoup(html_text, "lxml")
        products = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            product_url = urljoin(self.BASE_URL, href)
            product_url_clean = self.normalize_url(product_url)

            if not product_url_clean.endswith(".html"):
                continue

            text = self.clean_text(a.get_text(" "))

            if "TL" not in text:
                continue

            price = self.extract_price(text)
            name = self.extract_name(text)

            if not name or not price:
                continue

            if len(name) < 4:
                continue

            products.append((name, price, product_url_clean))

        return products, soup

    def is_probable_category_url(self, url):
        clean_url = self.normalize_url(url)

        if not clean_url.startswith(self.BASE_URL):
            return False

        if clean_url.endswith(".html"):
            return False

        parsed = urlparse(clean_url)
        path = parsed.path.strip("/")

        if not path:
            return False

        blocked_parts = [
            "login",
            "uye",
            "sepet",
            "siparis",
            "favori",
            "magaza",
            "iletisim",
            "servis",
            "sitemap",
            "iade",
            "karsilastir",
            "urun_kiyaslama",
            "account",
            "users",
            "arama",
            "search",
            "kampanya",
            "markalar",
            "blog",
            "yardim",
            "kvkk",
            "gizlilik",
        ]

        if any(part in clean_url for part in blocked_parts):
            return False

        return True

    def extract_subcategory_links(self, soup, current_url):
        subcategory_links = []
        seen = set()

        blocked_text_parts = [
            "giriş yap",
            "üye ol",
            "sepet",
            "sipariş",
            "favori",
            "mağaza",
            "bize ulaşın",
            "hakkımızda",
            "gizlilik",
            "kvkk",
            "servis",
            "site haritası",
            "iade",
            "çıkış",
            "profil",
            "mesaj",
            "hesabım",
            "karşılaştır",
        ]

        current_clean = self.normalize_url(current_url)

        for a in soup.find_all("a", href=True):
            text = self.clean_text(a.get_text(" "))

            if not text:
                continue

            text_lower = text.lower()

            if any(part in text_lower for part in blocked_text_parts):
                continue

            if len(text) < 3 or len(text) > 90:
                continue

            href = a.get("href", "")
            full_url = urljoin(self.BASE_URL, href)
            clean_url = self.normalize_url(full_url)

            if clean_url == current_clean:
                continue

            if not self.is_probable_category_url(clean_url):
                continue

            if clean_url in self.visited_category_urls:
                continue

            if clean_url in seen:
                continue

            seen.add(clean_url)
            subcategory_links.append(clean_url + "/")

            if len(subcategory_links) >= self.MAX_SUBCATEGORIES_PER_PAGE:
                break

        return subcategory_links

    def build_page_url(self, category_url, page_no):
        if page_no == 1:
            return category_url

        separator = "&" if "?" in category_url else "?"
        return f"{category_url}{separator}page={page_no}"

    def scrape_category(self, category_url, writer, csv_file, depth=0):
        clean_category_url = self.normalize_url(category_url)

        if clean_category_url in self.visited_category_urls:
            return

        self.visited_category_urls.add(clean_category_url)

        indent = "  " * depth
        print(f"\n{indent}Kategori başladı: {category_url}")

        first_html = self.fetch_html(category_url)

        if not first_html:
            print(f"{indent}İlk sayfa okunamadı, kategori geçiliyor.")
            return

        first_products, first_soup = self.parse_products_from_page(first_html)
        total_count = self.get_total_product_count(first_soup)

        # Ürün çıkmadıysa ve ürün sayısı da yazmıyorsa bu sayfa büyük ihtimalle alt kategori vitrini.
        if total_count is None and len(first_products) == 0:
            subcategory_links = self.extract_subcategory_links(first_soup, category_url)

            if subcategory_links and depth < self.MAX_DEPTH:
                print(f"{indent}Ürün listesi değil. {len(subcategory_links)} alt kategori bulundu.")

                for sub_url in subcategory_links:
                    self.scrape_category(sub_url, writer, csv_file, depth=depth + 1)
                    time.sleep(random.uniform(0.8, 1.8))

                return

            print(f"{indent}Ürün de alt kategori de bulunamadı, geçiliyor.")
            return

        if total_count:
            max_pages = math.ceil(total_count / self.PRODUCTS_PER_PAGE) + 3
        else:
            max_pages = 60

        print(f"{indent}Tahmini ürün sayısı: {total_count if total_count else 'bilinmiyor'}")
        print(f"{indent}Tahmini sayfa sayısı: {max_pages}")

        empty_page_streak = 0

        for page_no in range(1, max_pages + 1):
            if page_no == 1:
                html_text = first_html
            else:
                page_url = self.build_page_url(category_url, page_no)
                html_text = self.fetch_html(page_url)

            if not html_text:
                empty_page_streak += 1

                if empty_page_streak >= 2:
                    print(f"{indent}2 sayfa üst üste okunamadı, kategori bitiriliyor.")
                    break

                continue

            products, _ = self.parse_products_from_page(html_text)

            new_count = 0

            for name, price, product_url in products:
                if product_url in self.seen_product_urls:
                    continue

                self.seen_product_urls.add(product_url)

                # CSV formatı: isim;fiyat
                # Header yok.
                writer.writerow([name, price])

                self.total_written += 1
                new_count += 1

            csv_file.flush()

            print(
                f"{indent}Sayfa {page_no}/{max_pages} | "
                f"yeni ürün: {new_count} | "
                f"toplam: {self.total_written}"
            )

            if page_no > 2 and new_count == 0:
                empty_page_streak += 1
            else:
                empty_page_streak = 0

            if empty_page_streak >= 2:
                print(f"{indent}2 sayfa üst üste yeni ürün yok, kategori bitiriliyor.")
                break

            time.sleep(random.uniform(0.5, 1.1))

            if page_no % 80 == 0:
                break_time = random.uniform(20, 45)
                print(f"{indent}Mini mola: {int(break_time)} saniye")
                time.sleep(break_time)

    def run(self):
        with open(self.OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";")

            for category_url in self.CATEGORY_URLS:
                self.scrape_category(category_url, writer, csv_file)

                category_break = random.uniform(2, 6)
                print(f"Kategori arası mola: {int(category_break)} saniye")
                time.sleep(category_break)

        print("\nBitti.")
        print(f"Dosya: {self.OUTPUT_FILE}")
        print(f"Toplam yazılan ürün: {self.total_written}")


if __name__ == "__main__":
    scraper = VatanScraper()
    scraper.run()
