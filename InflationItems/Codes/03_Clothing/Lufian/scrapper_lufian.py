import json
import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE = "https://www.lufian.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

_ws = re.compile(r"\s+")

def clean_text(s: str) -> str:
    return _ws.sub(" ", (s or "").strip())

def extract_product_item(item):
    title_a = item.select_one("a.product-title")
    if title_a:
        title = clean_text(title_a.get_text())
        product_url = urljoin(BASE, title_a.get("href", ""))
    else:
        a = item.select_one("a.image-wrapper") or item.find("a")
        title = clean_text(a.get("title", "")) if a else ""
        product_url = urljoin(BASE, a.get("href", "")) if a and a.get("href") else ""

    image_urls = []
    for img in item.select("picture.image-inner img"):
        url = img.get("data-src") or img.get("src")
        if url:
            image_urls.append(urljoin(BASE, url))

    price_el = item.select_one(".product-price")
    price = clean_text(price_el.get_text()) if price_el else ""

    discount_el = item.select_one(".cart-discount")
    cart_discount_text = clean_text(discount_el.get_text()) if discount_el else ""

    fav = item.select_one(".add-favourite-btn[data-id]")
    product_id = fav.get("data-id") if fav else ""

    return {
        "product_id": product_id,
        "title": title,
        "product_url": product_url,
        "image_urls": " | ".join(image_urls),
        "price": price,
        "cart_discount_text": cart_discount_text,
    }

def parse_page(category_link: str, page_num: int):
    url = f"{BASE}/{category_link}?ps={page_num}"
    r = session.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.product-item")
    products = []
    for it in items:
        p = extract_product_item(it)
        if p["title"] and p["product_url"]:
            products.append(p)
    return products

def scrape_category(category_link: str, kategori_adi: str, max_pages: int = 200):
    all_products = []
    seen_ids = set()
    no_new_count = 0

    for p in range(0, max_pages):
        products = parse_page(category_link, p)
        
        # Yeni (daha önce görülmemiş) ürünleri filtrele
        new_products = []
        for prod in products:
            uid = prod.get("product_id") or prod.get("product_url")
            if uid and uid not in seen_ids:
                seen_ids.add(uid)
                prod["kategori"] = kategori_adi
                new_products.append(prod)

        print(f"  [{kategori_adi}] ps={p}: {len(products)} ürün geldi, {len(new_products)} yeni | toplam: {len(all_products) + len(new_products)}")

        if not new_products:
            no_new_count += 1
            if no_new_count >= 3:
                print(f"  [{kategori_adi}] Yeni ürün kalmadı → bitti.")
                break
        else:
            no_new_count = 0
            all_products.extend(new_products)

        time.sleep(0.75)

    return all_products

def main():
    all_products = []

    # Erkek kategorisi
    print("\n[1] Erkek kategorisi taranıyor...")
    erkek = scrape_category("erkek", "erkek")
    all_products.extend(erkek)
    print(f"  Erkek toplam: {len(erkek)}")

    # Kadın kategorisi
    print("\n[2] Kadın kategorisi taranıyor...")
    kadin = scrape_category("kadin", "kadin")
    all_products.extend(kadin)
    print(f"  Kadın toplam: {len(kadin)}")

    # CSV'ye kaydet
    df = pd.DataFrame(all_products)
    cols = ["kategori", "title", "price", "cart_discount_text",
            "image_urls", "product_url", "product_id"]
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    df.to_csv("lufian_urunler.csv", index=False, encoding="utf-8-sig")

    print(f"\n{'='*50}")
    print(f"  ✅ Tamamlandı!")
    print(f"  Erkek : {len(erkek)}")
    print(f"  Kadın : {len(kadin)}")
    print(f"  Toplam: {len(all_products)}")
    print(f"  Dosya : lufian_urunler.csv")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()