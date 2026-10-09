import requests
from bs4 import BeautifulSoup
import re
import time
import json
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://www.ideal.com.tr"

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    })
    return session

def get_categories(session):
    print("Kategoriler çekiliyor...")
    response = session.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    category_links = set()
    
    # Menü içerisindeki veya genel tüm kategori linklerini topla
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "kategori" in href and BASE_URL in href:
            category_links.add(href)
        elif href.startswith("/kategori"):
            category_links.add(BASE_URL + href)
    
    print(f"Toplam {len(category_links)} kategori linki bulundu.")
    return list(category_links)

def parse_price(price_str):
    if not price_str:
        return 0.0
    # Örn: 1.250,50 TL veya 1250.50 olabilir
    cleaned = price_str.replace("TL", "").strip()
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def scrape_category(session, category_url):
    products = []
    page = 1
    while True:
        url = f"{category_url}?page={page}"
        print(f"Sayfa indiriliyor: {url}")
        try:
            response = session.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Hata Kodu {response.status_code}: {url}")
                break
            
            soup = BeautifulSoup(response.text, "html.parser")
            product_divs = soup.find_all("div", class_="product-list")
            
            if not product_divs:
                # Ürün bulunamadıysa (sayfalama bitti) döngüden çık
                break
                
            for div in product_divs:
                a_tag = div.find("a")
                if not a_tag:
                    continue
                
                product_url = a_tag.get("href", "")
                if not product_url.startswith("http"):
                    product_url = BASE_URL + product_url
                    
                name_tag = a_tag.find("span", class_="urun-baslik")
                product_name = name_tag.text.strip() if name_tag else "Bilinmeyen Ürün"
                
                price_tag = a_tag.find("span", class_="fiyat")
                
                current_price = 0.0
                if price_tag:
                    old_price_b = price_tag.find("b", class_="discount_list_price")
                    if old_price_b: old_price_b.decompose()
                    tl_span = price_tag.find("span", class_="tlStyle")
                    if tl_span: tl_span.decompose()
                        
                    raw_price_text = price_tag.text.strip()
                    current_price = parse_price(raw_price_text)
                    
                # Eğer çekilemediyse
                if current_price == 0.0:
                    continue
                    
                products.append({
                    "name": product_name,
                    "price": current_price,
                    "url": product_url,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d")
                })
                
            page += 1
            # Sunucuyu yormamak için kısa bekleme
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Hata oluştu: {e}")
            break
            
    return products

if __name__ == "__main__":
    session = get_session()
    categories = get_categories(session)
    
    all_products = []
    # Tüm kategorileri gez
    for cat in categories:
        prods = scrape_category(session, cat)
        all_products.extend(prods)
        
    print(f"\nToplam {len(all_products)} ürün çekildi.")
    if all_products:
        print("CSV dosyası oluşturuluyor...")
        try:
            os.makedirs("Datas/Markets/Ideal", exist_ok=True)
            today_str = datetime.now().strftime("%Y-%m-%d")
            csv_path = f"Datas/Markets/Ideal/ideal_prices_{today_str}.csv"
            
            # CSV dosyasına sadece isim ve fiyat ekliyoruz
            csv_payload = [{"name": p["name"], "price": p["price"]} for p in all_products]
            df = pd.DataFrame(csv_payload)
            
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"Veriler başarıyla {csv_path} dosyasına kaydedildi.")
        except Exception as e:
            print(f"CSV kaydedilirken hata oluştu: {e}")

        print("Supabase'e aktarılıyor...")
        try:
            # Supabase'e tüm veriyi formatıyla (isim, fiyat, link, sadecetarih) gönderiyoruz
            chunk_size = 500
            for i in range(0, len(all_products), chunk_size):
                chunk = all_products[i:i + chunk_size]
                response = supabase.table("products_price_history").insert(chunk).execute()
                print(f"Başarıyla {len(chunk)} ürün veritabanına eklendi.")
        except Exception as e:
            print(f"Supabase'e eklerken hata oluştu: {e}")
