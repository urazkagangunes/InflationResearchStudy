"""
Colin's Ürün Scraper
---------------------
HTML yapısı (F12 ile doğrulandı):
  Kart wrapper : div.productCartMain
  Ürün data    : div.productbox → data-ga attribute (JSON: name + price)
  Link + isim  : a.product-name → href ve title attribute

Çalıştır: python colins_scraper.py
"""

import time
import csv
import os
import json
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ──────────────────────────────────────────────────────────────
# Chrome ayarları
# ──────────────────────────────────────────────────────────────
chrome_options = Options()
# chrome_options.add_argument("--headless=new")  # görünmez mod istersen aç
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), options=chrome_options
)
wait = WebDriverWait(driver, 20)

BASE = "https://www.colins.com.tr"

# ──────────────────────────────────────────────────────────────
# Kategoriler — (ad, path)
# URL'ler F12 Elements'ten doğrulandı
# ──────────────────────────────────────────────────────────────
KATEGORILER = [
    # Kadın
    ("Kadın Giyim",         "/c/kadin-giyim-57"),
    ("Kadın Jean",          "/c/kadin-jean-modelleri-121"),
    ("Kadın Pantolon",      "/c/kadin-pantolon-209"),
    ("Kadın Elbise",        "/c/kadin-elbise-212"),
    ("Kadın Etek",          "/c/kadin-elbise-etek-667"),
    ("Kadın Gömlek",        "/c/kadin-gomlek-968"),
    ("Kadın Sweatshirt",    "/c/kadin-sweatshirt-189"),
    ("Kadın Kazak",         "/c/kadin-kazak-1211"),
    ("Kadın Hırka",         "/c/kadin-hirka-181"),
    ("Kadın Ceket",         "/c/kadin-ceket-211"),
    ("Kadın Yelek",         "/c/kadin-yelek-232"),
    ("Kadın Mont",          "/c/kadin-mont-185"),
    ("Kadın Yağmurluk",     "/c/kadin-yagmurluk-1115"),
    # Erkek
    ("Erkek Giyim",         "/c/erkek-giyim-modelleri-2"),
    ("Erkek Jean",          "/c/erkek-jean-56"),
    ("Erkek Pantolon",      "/c/erkek-pantolon-201"),
    ("Erkek Gömlek",        "/c/erkek-gomlek-1202"),
    ("Erkek Tişört",        "/c/erkek-tisort-6"),
    ("Erkek Polo Tişört",   "/c/erkek-polo-yaka-tisort-225"),
    ("Erkek Sweatshirt",    "/c/erkek-sweatshirt-177"),
    ("Erkek Kazak",         "/c/erkek-kazak-1212"),
    ("Erkek Hırka",         "/c/erkek-hirka-169"),
    ("Erkek Ceket",         "/c/erkek-ceket-245"),
    ("Erkek Yelek",         "/c/erkek-yelek-260"),
    ("Erkek Mont",          "/c/erkek-mont-243"),
    ("Erkek Yağmurluk",     "/c/erkek-yagmurluk-1113"),
    # İndirim
    ("İndirim",             "/c/indirimdekiler-1284"),
]

tum_urunler: list[dict] = []
tum_linkler: set[str]   = set()  # global duplicate önleme


# ──────────────────────────────────────────────────────────────
# Yardımcılar
# ──────────────────────────────────────────────────────────────
def fiyat_parse(fiyat_str: str) -> float:
    """'1.199,90 TL' → 1199.9  |  '599' → 599.0  |  '' → 0.0"""
    if not fiyat_str:
        return 0.0
    temiz = re.sub(r"[^\d,\.]", "", str(fiyat_str))
    if "," in temiz and "." in temiz:
        # Türkçe format: 1.299,90 → binlik=nokta, ondalık=virgül
        temiz = temiz.replace(".", "").replace(",", ".")
    elif "," in temiz:
        temiz = temiz.replace(",", ".")
    try:
        return float(temiz)
    except ValueError:
        return 0.0


def scroll_to_bottom():
    onceki = 0
    for _ in range(30):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.2)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == onceki:
            break
        onceki = yeni


def urunleri_bekle():
    """div.productCartMain DOM'a girene kadar bekle (max 15s)."""
    try:
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div.productCartMain")
        ))
    except Exception:
        pass  # timeout olursa devam et, belki kategori boş


# ──────────────────────────────────────────────────────────────
# Ürün toplama — kesin seçicilerle
# ──────────────────────────────────────────────────────────────
def urunleri_topla(kategori_adi: str) -> list[dict]:
    kartlar = driver.find_elements(By.CSS_SELECTOR, "div.productCartMain")
    sayfa_urunleri = []

    for kart in kartlar:
        try:
            isim      = ""
            fiyat_str = ""
            link      = ""

            # ── Birincil: data-ga JSON (isim + fiyat) ────────
            # Örnek: data-ga='{"name":"Comfort Fit...","price":"1199,90 TL",...}'
            try:
                productbox = kart.find_element(By.CSS_SELECTOR, "div.productbox")
                data_ga    = productbox.get_attribute("data-ga") or ""
                if data_ga:
                    ga        = json.loads(data_ga)
                    isim      = ga.get("name", "").strip()
                    fiyat_str = str(ga.get("price", "")).strip()
            except Exception:
                pass

            # ── Link + yedek isim: a.product-name ────────────
            try:
                a_tag = kart.find_element(By.CSS_SELECTOR, "a.product-name")
                href  = a_tag.get_attribute("href") or ""
                link  = href if href.startswith("http") else BASE + href
                if not isim:
                    isim = (
                        a_tag.get_attribute("title")
                        or a_tag.text
                        or ""
                    ).strip()
            except Exception:
                pass

            # ── Yedek fiyat: productWrapper içindeki span'lar ─
            if not fiyat_str:
                try:
                    for span_sel in [
                        "div.productWrapper span",
                        "div.product-text-container span",
                        "[class*='price']",
                    ]:
                        spans = kart.find_elements(By.CSS_SELECTOR, span_sel)
                        for s in spans:
                            txt = s.text.strip()
                            if txt and any(c.isdigit() for c in txt):
                                fiyat_str = txt
                                break
                        if fiyat_str:
                            break
                except Exception:
                    pass

            fiyat_float = fiyat_parse(fiyat_str)

            # Linki olmayan veya daha önce eklenmiş ürünleri atla
            if link and link not in tum_linkler:
                tum_linkler.add(link)
                sayfa_urunleri.append({
                    "kategori":  kategori_adi,
                    "isim":      isim,
                    "fiyat":     fiyat_float,   # float
                    "fiyat_ham": fiyat_str,      # ham string
                    "link":      link,
                })

        except Exception:
            continue

    return sayfa_urunleri


# ──────────────────────────────────────────────────────────────
# Sayfalama — "Daha Fazla Ürün Göster" butonu (div#moreBtn)
# span#pageNumber    → mevcut sayfa
# span#totalpagesNumber → toplam sayfa
# ──────────────────────────────────────────────────────────────
def toplam_sayfa() -> int:
    try:
        return int(driver.find_element(By.ID, "totalpagesNumber").text.strip())
    except Exception:
        return 1


def mevcut_sayfa() -> int:
    try:
        return int(driver.find_element(By.ID, "pageNumber").text.strip())
    except Exception:
        return 1


def more_btn_tikla() -> bool:
    """
    #moreBtn butonuna tıkla, yeni kartlar yüklenene kadar bekle.
    Başarılıysa True, buton yoksa/gizliyse False döner.
    """
    try:
        btn = driver.find_element(By.ID, "moreBtn")
        if not btn.is_displayed():
            return False
        onceki_kart_sayisi = len(driver.find_elements(By.CSS_SELECTOR, "div.productCartMain"))
        driver.execute_script("arguments[0].click();", btn)
        # Yeni kartlar DOM'a eklenene kadar bekle (max 10s)
        for _ in range(20):
            time.sleep(0.5)
            yeni_kart_sayisi = len(driver.find_elements(By.CSS_SELECTOR, "div.productCartMain"))
            if yeni_kart_sayisi > onceki_kart_sayisi:
                return True
        return True  # zaman aşımı olsa da devam
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# Kategori işleyici
# ──────────────────────────────────────────────────────────────
def kategori_isle(adi: str, path: str):
    base_url = BASE + path
    print(f"\n📂 {adi}")

    driver.get(base_url)
    time.sleep(4)
    urunleri_bekle()
    # İlk scroll — görünür kartları yükle
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    son = toplam_sayfa()
    print(f"  📊 Toplam sayfa: {son}")

    # Tüm sayfaları "Daha Fazla Ürün Göster" ile yükle
    while True:
        mevcut = mevcut_sayfa()
        # Butona tıklamadan önce sayfayı en alta kaydır (lazy-load tetikle)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        yeni = urunleri_topla(adi)
        tum_urunler.extend(yeni)
        print(f"  📄 Sayfa {mevcut}/{son} → {len(yeni)} yeni | Toplam: {len(tum_urunler)}")

        if mevcut >= son:
            break  # son sayfadayız

        basarili = more_btn_tikla()
        if not basarili:
            break


# ──────────────────────────────────────────────────────────────
# Ana akış
# ──────────────────────────────────────────────────────────────
try:
    print("🌐 Colin's açılıyor...")
    driver.get(BASE)
    time.sleep(4)

    # Popup/cookie banner kapat
    for sel in [
        "button[id*='accept']", "button[class*='accept']",
        "button[class*='cookie']",
        "//button[contains(text(),'Onayla')]",
        "//button[contains(text(),'Kabul')]",
    ]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            el = driver.find_element(by, sel)
            if el.is_displayed():
                el.click()
                print("✅ Popup kapatıldı")
                time.sleep(1)
                break
        except Exception:
            pass

    # Tüm kategorileri işle
    for adi, path in KATEGORILER:
        try:
            kategori_isle(adi, path)
        except Exception as e:
            print(f"  ❌ {adi} hatası: {e}")
            continue

    # CSV kaydet
    os.makedirs("data", exist_ok=True)
    tarih = datetime.now().strftime("%Y-%m-%d")
    dosya = f"colins-data/colins_urunler_{tarih}.csv"

    with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["kategori", "isim", "fiyat", "fiyat_ham", "link"],
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n{'='*55}")
    print(f"🎉 TOPLAM ÜRÜN: {len(tum_urunler)}")
    print(f"💾 {dosya}")
    print(f"{'='*55}")

finally:
    driver.quit()
