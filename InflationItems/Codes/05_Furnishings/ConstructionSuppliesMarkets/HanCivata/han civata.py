# -*- coding: utf-8 -*-
"""
Created on Sat Mar 14 22:48:30 2026

@author: orenl
"""

# -*- coding: utf-8 -*-
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hancivata.com/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )
}
SLEEP_SECONDS = 0.4


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get_soup(session, url):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(href):
    if not href:
        return ""
    return urljoin(BASE_URL, href).rstrip("/")


def is_valid_category_url(url):
    """
    Kategori linklerini bırak, hesap/sepet vb. linkleri ele.
    """
    if not url.startswith(BASE_URL):
        return False

    banned_keywords = [
        "giris", "uye-ol", "kayit", "sepet", "kasaya-git",
        "hesabim", "siparis", "wishlist", "affiliate",
        "blog", "hakkimizda", "iletisim", "gizlilik",
        "site-haritasi", "markalar", "kampanya", "special",
        "manufacturer", "information", "contact", "checkout",
        "account", "login", "register"
    ]

    lower_url = url.lower()
    if any(x in lower_url for x in banned_keywords):
        return False

    # product/category route kullanan linkleri kabul et
    if "route=product%2fcategory" in lower_url or "route=product/category" in lower_url:
        return True

    # SEO slug yapısındaki kategori linkleri
    path = urlparse(url).path.strip("/").lower()
    if not path:
        return False

    # sayfalama linki kategori başlangıcı değil
    if re.search(r"/page-\d+$", path):
        return False

    return True


def get_categories(session):
    soup = get_soup(session, BASE_URL)

    categories = []
    seen = set()

    for a in soup.select("a[href]"):
        href = normalize_url(a.get("href"))
        name = clean_text(a.get_text(" ", strip=True))

        if not name:
            continue
        if not is_valid_category_url(href):
            continue

        # çok kısa/işlevsel olmayan isimleri ele
        if len(name) < 2:
            continue

        key = (name.lower(), href.lower())
        if key in seen:
            continue

        seen.add(key)
        categories.append({
            "kategori": name,
            "url": href
        })

    return categories


def get_total_pages(soup):
    text = clean_text(soup.get_text(" ", strip=True))
    m = re.search(r"toplam:\s*\d+\s*\((\d+)\s*Sayfa\)", text, flags=re.I)
    if m:
        return int(m.group(1))
    return 1


def get_total_products(soup):
    text = clean_text(soup.get_text(" ", strip=True))
    m = re.search(r"toplam:\s*(\d+)", text, flags=re.I)
    if m:
        return int(m.group(1))
    return None


def extract_price(text):
    prices = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}\s*TL", text, flags=re.I)
    if prices:
        # son fiyatı al
        return prices[-1].replace(" ", "")
    return ""


def extract_product_id(product_url):
    """
    URL'de numeric id varsa al.
    Yoksa boş döner.
    """
    m = re.search(r"(\d+)", product_url)
    return m.group(1) if m else ""


def parse_products(soup, kategori):
    products = []
    seen = set()

    # Ürün isimleri çoğunlukla h4/h4 altındaki linkte
    for h4 in soup.find_all(["h4", "h5"]):
        product_name = clean_text(h4.get_text(" ", strip=True))
        if not product_name:
            continue

        # footer/sabit alanları ele
        banned_names = {
            "WHATSAPP", "İADE & DEĞİŞİM", "ÜCRETSİZ KARGO",
            "9 TAKSİT", "Yurtdışı Kargo"
        }
        if product_name in banned_names:
            continue

        # ürün linkini bul
        a = h4.find("a", href=True)
        if not a:
            parent_a = h4.find_parent("a", href=True)
            a = parent_a

        product_url = normalize_url(a["href"]) if a and a.get("href") else ""

        # isim çevresindeki bloktan fiyat ara
        block = h4
        for _ in range(4):
            if block.parent:
                block = block.parent

        block_text = clean_text(block.get_text(" ", strip=True))
        fiyat = extract_price(block_text)

        if not fiyat:
            continue

        urun_id = extract_product_id(product_url)

        key = (product_name.lower(), kategori.lower(), fiyat, product_url)
        if key in seen:
            continue
        seen.add(key)

        products.append({
            "urun_id": urun_id,
            "urun_adi": product_name,
            "kategori": kategori,
            "fiyat": fiyat,
            "urun_url": product_url
        })

    return products


def build_page_url(category_url, page_num):
    if page_num == 1:
        return category_url
    return f"{category_url}/page-{page_num}"


def scrape_category(session, kategori, category_url):
    first_soup = get_soup(session, category_url)
    total_pages = get_total_pages(first_soup)
    total_products = get_total_products(first_soup)

    print(f"Kategori: {kategori}")
    print(f"Beklenen toplam ürün: {total_products}")
    print(f"Toplam sayfa: {total_pages}")

    rows = []

    for page in range(1, total_pages + 1):
        url = build_page_url(category_url, page)
        soup = first_soup if page == 1 else get_soup(session, url)

        products = parse_products(soup, kategori)
        print(f"  Sayfa: {page} | ürün: {len(products)}")

        rows.extend(products)
        time.sleep(SLEEP_SECONDS)

    return rows, total_products


def main():
    session = get_session()

    categories = get_categories(session)
    print(f"Bulunan kategori sayısı: {len(categories)}")

    today = datetime.now().strftime("%Y-%m-%d")
    file_name = f"han_civata_{today}.csv"
    kontrol_name = f"han_civata_kontrol_{today}.csv"

    # --- Yarıda kesilmeye karşı kaldığı yerden devam etme (Resume) Mantığı ---
    processed_categories = set()
    if os.path.exists(kontrol_name):
        try:
            kontrol_df = pd.read_csv(kontrol_name)
            processed_categories = set(kontrol_df["kategori"].tolist())
            print(f"\n[!] Kaldığı yerden devam ediliyor. {len(processed_categories)} kategori zaten çekilmiş.\n")
        except Exception as e:
            print(f"Kontrol dosyası okunamadı: {e}")

    for cat in categories:
        kategori = cat["kategori"]
        url = cat["url"]

        if kategori in processed_categories:
            print(f"ATLANDI (Zaten Çekilmiş) -> Kategori: {kategori}")
            continue

        try:
            rows, expected_total = scrape_category(session, kategori, url)
            
            # Bu kategori için verileri DataFrame'e dönüştür
            if rows:
                df = pd.DataFrame(rows)
                # Kategori bazında kopyaları temizle
                df.drop_duplicates(subset=["urun_id", "urun_adi", "kategori", "fiyat", "urun_url"], inplace=True)
                
                # CSV'ye ekleme modunda (append - 'a') yazdır
                # Dosya yoksa header ekle, varsa ekleme
                df.to_csv(file_name, mode='a', index=False, header=not os.path.exists(file_name), encoding="utf-8-sig")

            # Kontrol dosyasını güncelle
            kontrol_data = [{
                "kategori": kategori,
                "kategori_url": url,
                "beklenen_toplam_urun": expected_total,
                "cekilen_urun_sayisi": len(rows)
            }]
            kontrol_df = pd.DataFrame(kontrol_data)
            kontrol_df.to_csv(kontrol_name, mode='a', index=False, header=not os.path.exists(kontrol_name), encoding="utf-8-sig")

        except Exception as e:
            print(f"HATA -> {kategori}: {e}")
            # Hata alanları da kontrol dosyasına 0 ürün olarak ekle ki sürekli aynı hataya takılmasın
            # (İsteğe bağlı olarak bu kısmı atlayabilirsiniz, böylece hata alanlar bir sonraki çalışmada tekrar denenir)
            kontrol_data = [{
                "kategori": kategori,
                "kategori_url": url,
                "beklenen_toplam_urun": None,
                "cekilen_urun_sayisi": 0
            }]
            pd.DataFrame(kontrol_data).to_csv(kontrol_name, mode='a', index=False, header=not os.path.exists(kontrol_name), encoding="utf-8-sig")

    print(f"\nİşlem Tamamlandı!")
    print(f"Ana dosya: {file_name}")
    print(f"Kontrol dosyası: {kontrol_name}")


if __name__ == "__main__":
    main()