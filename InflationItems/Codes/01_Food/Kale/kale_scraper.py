import csv
import re
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


KATEGORILER = [
    ("Meyve, Sebze", "https://www.kalemarketleri.com/meyve-sebze"),
    ("Et, Tavuk", "https://www.kalemarketleri.com/et-tavuk"),
    ("Süt, Kahvaltılık", "https://www.kalemarketleri.com/sut-kahvaltilik"),
    ("Genel Gıda", "https://www.kalemarketleri.com/genel-gida"),
    ("İçecekler", "https://www.kalemarketleri.com/icecekler"),
    ("Unlu Mamuller", "https://www.kalemarketleri.com/unlu-mamuller"),
    ("Bisküvi, Kuruyemiş", "https://www.kalemarketleri.com/biskuvi-kuruyemis"),
    ("Deterjan, Temizlik", "https://www.kalemarketleri.com/deterjan-temizlik"),
    ("Kişisel Bakım, Kozmetik", "https://www.kalemarketleri.com/kisisel-bakim-kozmetik"),
    ("Kağıt Ürünleri", "https://www.kalemarketleri.com/kagit-urunleri"),
    ("Bebek Ürünleri", "https://www.kalemarketleri.com/bebek-urunleri"),
    ("Ev, Yaşam", "https://www.kalemarketleri.com/ev-yasam"),
]



BASE_DIR = os.getcwd()
OUT_DIR = os.path.join(BASE_DIR, "Datas", "Markets", "Kale")
os.makedirs(OUT_DIR, exist_ok=True)


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")

    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver


def scroll_sona_kadar(driver, max_scroll=90, bekle=1.2):
    last_height = driver.execute_script("return document.body.scrollHeight")
    sabit = 0
    for _ in range(max_scroll):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(bekle)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            sabit += 1
            if sabit >= 3:
                break
        else:
            sabit = 0
            last_height = new_height


def fiyat_temizle(text: str) -> str:
    if not text:
        return ""
    t = text.replace("₺", "").replace("TL", " ").strip()
    m = re.search(r"(\d+(?:[.,]\d+)?)", t)
    if not m:
        return ""
    val = m.group(1).replace(".", ",")
    return val.strip()


def isim_cek(kart) -> str:
    for sel in ["h1", "h2", "h3", "h4", ".productName", ".product-name", ".ProductName", ".product-title"]:
        try:
            txt = kart.find_element(By.CSS_SELECTOR, sel).text.strip()
            if txt:
                return txt
        except Exception:
            pass
    try:
        txt = kart.text.strip()
        if not txt:
            return ""
        return txt.splitlines()[0].strip()
    except Exception:
        return ""


def fiyat_cek(kart, driver) -> str:
    for sel in [".productPrice", ".product-price", ".price", ".Price", ".urunFiyat", ".currentPrice"]:
        try:
            txt = kart.find_element(By.CSS_SELECTOR, sel).text.strip()
            if txt:
                return fiyat_temizle(txt)
        except Exception:
            pass
    try:
        txt = driver.execute_script("return arguments[0].textContent;", kart)
        return fiyat_temizle(txt or "")
    except Exception:
        return ""


def norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def main():

    bugun = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    csv_file_name = f"kalemarketleri_prices_{bugun}.csv"
    csv_path = os.path.join(OUT_DIR, csv_file_name)

    driver = make_driver()
    seen = set()
    rows = []

    try:
        for kategori_adi, link in KATEGORILER:
            print(f"\n🔍 İşleniyor: {kategori_adi}")
            try:
                driver.get(link)
                time.sleep(5) 

                scroll_sona_kadar(driver)

                kart_selectors = [
                    "div.productItem", "div.ProductItem",
                    "li.productItem", "li.ProductItem",
                    "div.product", "div.products-item", "div.product-item"
                ]

                urun_kartlari = []
                for ks in kart_selectors:
                    urun_kartlari = driver.find_elements(By.CSS_SELECTOR, ks)
                    if urun_kartlari:
                        break

                if not urun_kartlari:
                    print("  ⚠️ Ürün kartları bulunamadı.")
                    continue

                cekilen = 0
                for kart in urun_kartlari:
                    try:
                        isim = isim_cek(kart)
                        if not isim: continue

                        fiyat = fiyat_cek(kart, driver)
                        if not fiyat: continue

                        key = (norm_key(isim), fiyat.strip())
                        if key in seen: continue
                        seen.add(key)

                        rows.append({
                            "kategori": kategori_adi,
                            "product_name": isim,
                            "product_price": fiyat,
                        })
                        cekilen += 1
                    except Exception:
                        continue

                print(f"  ✅ Eklendi: {cekilen}")
            except Exception as e:
                print(f"  ❌ Kategori hatası: {e}")
                continue

    finally:
        driver.quit()

    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["kategori", "product_name", "product_price"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n🎉 İşlem tamam! {len(rows)} ürün '{csv_path}' dosyasına kaydedildi.")
    else:
        print("\n❌ Hiç ürün çekilemedi!")


if __name__ == "__main__":
    main()
