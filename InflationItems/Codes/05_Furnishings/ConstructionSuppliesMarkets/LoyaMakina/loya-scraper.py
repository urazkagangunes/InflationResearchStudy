"""
Loya Makina - Ürün Scraper
Site: https://www.loyamakina.com
Platform: T-Soft E-Ticaret

Çalıştırmak için:
    pip install selenium webdriver-manager
    python loya_scraper.py

Çıktı: data/loya_urunler_YYYY-MM-DD.csv
"""

import time
import csv
import os
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ─────────────────────────────────────────────
# Chrome ayarları
# ─────────────────────────────────────────────
chrome_options = Options()
# chrome_options.add_argument("--headless")          # Arka planda çalıştırmak için açabilirsiniz
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

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 20)

BASE_URL = "https://www.loyamakina.com"

# ─────────────────────────────────────────────
# Ana (üst) kategori URL'leri  →  alt kategoriler otomatik keşfedilecek
# İstersen buraya elle de ekleyebilirsin; scraper tekrarları zaten eliyor.
# ─────────────────────────────────────────────
ANA_KATEGORILER = [
    "https://www.loyamakina.com/utu-grubu",
    "https://www.loyamakina.com/ev-ve-yasam",
    "https://www.loyamakina.com/hirdavat-el-aletleri",
    "https://www.loyamakina.com/bahce-camping",
    "https://www.loyamakina.com/isitma-sogutma",
    "https://www.loyamakina.com/raflar-ve-dolaplar",
]

tum_urunler = []
ziyaret_edilen = set()   # Tekrar ziyareti önlemek için


# ─────────────────────────────────────────────
# JS ile güvenli tıklama
# ─────────────────────────────────────────────
def js_click(element):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", element)


# ─────────────────────────────────────────────
# Scroll — lazy-load içerikler için
# ─────────────────────────────────────────────
def scroll_to_bottom():
    onceki = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == onceki:
            break
        onceki = yeni


# ─────────────────────────────────────────────
# Menüden tüm leaf kategorileri topla
# (T-Soft sitenin <nav> menüsündeki tüm linkleri tarar)
# ─────────────────────────────────────────────
def menuden_kategorileri_al():
    print("📋 Kategori listesi çekiliyor...")
    driver.get(BASE_URL)
    time.sleep(4)

    kategoriler = set()

    # Tüm nav linkleri tara
    linkler = driver.find_elements(By.CSS_SELECTOR, "nav a, .menu a, ul.nav a, ul.categories a")

    if not linkler:
        # Fallback: tüm <a> elementlerini tara, loyamakina.com içerenleri al
        linkler = driver.find_elements(By.TAG_NAME, "a")

    for link in linkler:
        try:
            href = link.get_attribute("href") or ""
            # Sadece kategori benzeri URL'ler (product sayfası değil, sepet vs. değil)
            if (
                BASE_URL in href
                and href != BASE_URL
                and href != BASE_URL + "/"
                and "sepet" not in href
                and "uye" not in href
                and "iletisim" not in href
                and "blog" not in href
                and "siparis" not in href
                and "index.php" not in href
                and "#" not in href
                and "indirimli" not in href
                and "yeni-urunler" not in href
            ):
                # Ürün sayfası mı kategori mi? Kategori URL'leri genellikle kısa slug
                # Ürün URL'leri çok daha uzun olur ama menüde genellikle kategori linkleri var
                path = href.replace(BASE_URL, "").strip("/")
                # 1-3 kelimeli slug → muhtemelen kategori
                if path and "/" not in path:
                    kategoriler.add(href.rstrip("/"))
        except Exception:
            continue

    print(f"  ✅ {len(kategoriler)} adet kategori URL'si bulundu")
    return sorted(kategoriler)


# ─────────────────────────────────────────────
# Bir sayfadaki ürünleri çek
# T-Soft teması CSS selektörleri
# ─────────────────────────────────────────────
def urunleri_topla(kategori_adi, kategori_url):
    """
    T-Soft vitrin teması ürün listesi selektörleri.
    Birden fazla selektör denenir; ilk çalışan kullanılır.
    """
    urunler_raw = []

    # Loya Makina T-Soft teması: ürünler ul.fl.masonry > li içinde
    # Fiyat class'ı: .currentPrice
    kapsayici_selektorler = [
        "ul.masonry li",
        "ul.fl.masonry li",
        ".col-xs-6",
    ]

    items = []
    for sel in kapsayici_selektorler:
        kandidatlar = driver.find_elements(By.CSS_SELECTOR, sel)
        # Gerçek ürün li'lerini filtrele: içinde currentPrice olan
        items = [i for i in kandidatlar if i.find_elements(By.CSS_SELECTOR, ".currentPrice")]
        if items:
            break

    if not items:
        # Son çare: tüm <a> içinde .png/.jpg/.webp olan kart benzeri bloklar
        print(f"    ⚠️  Ürün elementi bulunamadı (kapsayıcı yok)")
        return []

    for item in items:
        try:
            # ── İsim ──
            isim = ""
            for sel in ["a[title]", "h2", "h3", "[class*='name']", "[class*='title']"]:
                try:
                    el = item.find_element(By.CSS_SELECTOR, sel)
                    isim = el.get_attribute("title") or el.text.strip()
                    if isim:
                        break
                except Exception:
                    continue

            # ── Fiyat ──
            fiyat = ""
            try:
                fiyat = item.find_element(By.CSS_SELECTOR, ".currentPrice").text.strip()
            except Exception:
                pass

            # ── Link ──
            link = ""
            try:
                link = item.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
            except Exception:
                pass

            # ── Resim ──
            resim = ""
            try:
                img = item.find_element(By.TAG_NAME, "img")
                resim = img.get_attribute("src") or img.get_attribute("data-src") or ""
            except Exception:
                pass

            if isim or link:
                urunler_raw.append({
                    "kategori": kategori_adi,
                    "kategori_url": kategori_url,
                    "isim": isim,
                    "fiyat": fiyat,
                    "link": link,
                    "resim": resim,
                })
        except Exception:
            continue

    return urunler_raw


# ─────────────────────────────────────────────
# Toplam sayfa sayısını bul (T-Soft ?pg=N formatı)
# ─────────────────────────────────────────────
def son_sayfa_numarasini_al(base_url):
    """
    T-Soft sayfa numaralarını ?pg=N ile yapar.
    Sayfalama butonlarından max numarayı okur,
    yoksa next butonunu takip eder.
    """
    def sayfadaki_max_numara():
        numaralar = []
        for sel in [
            ".pager a", ".pagination a", ".pages a",
            "[class*='pager'] a", "[class*='pagination'] a",
            "a[href*='?pg=']", "a[href*='&pg=']",
        ]:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    numaralar.append(int(el.text.strip()))
                except Exception:
                    pass
                # href'den de al
                href = el.get_attribute("href") or ""
                m = re.search(r'[?&]pg=(\d+)', href)
                if m:
                    numaralar.append(int(m.group(1)))
        return max(numaralar) if numaralar else 1

    def sonraki_sayfa_href():
        """Sadece URL döndür, elemente dokunma → StaleElement riski yok"""
        next_sels = [
            ".pager .next a",
            ".pagination .next a",
            "[class*='next'] a",
            "a[rel='next']",
            "a.next",
        ]
        for sel in next_sels:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    href = els[0].get_attribute("href")
                    if href and re.search(r'[?&]pg=\d+', href):
                        return href
            except Exception:
                pass
        return None

    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        # Önce mevcut sayfadaki max numarayı oku
        max_no = sayfadaki_max_numara()
        if max_no > 1:
            return max_no

        # Numaralar yoksa next butonunu takip ederek son sayfayı bul
        adim = 0
        while True:
            href = sonraki_sayfa_href()
            if not href:
                break
            driver.get(href)
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            adim += 1
            yeni_max = sayfadaki_max_numara()
            if yeni_max > max_no:
                max_no = yeni_max
            if adim > 200:
                break

        son = max_no
        print(f"  🔍 Son sayfa: {son}")

        # Başa dön
        driver.get(base_url)
        time.sleep(3)
        scroll_to_bottom()
        return son

    except Exception as ex:
        print(f"  ⚠️  son_sayfa_numarasini_al hatası: {ex}")
        try:
            driver.get(base_url)
            time.sleep(3)
        except Exception:
            pass
        return 1


# ─────────────────────────────────────────────
# Kategori işleme — tüm sayfalarda ürün topla
# ─────────────────────────────────────────────
def kategori_isle(kategori_url):
    if kategori_url in ziyaret_edilen:
        return
    ziyaret_edilen.add(kategori_url)

    # Kategori adını URL'den türet
    path = kategori_url.rstrip("/").split("/")[-1]
    kategori_adi = path.replace("-", " ").title()
    print(f"\n📂 Kategori: {kategori_adi}  →  {kategori_url}")

    base_url = kategori_url.split("?")[0].rstrip("/")

    # İlk sayfayı yükle
    driver.get(base_url)
    time.sleep(3)
    scroll_to_bottom()

    # Sayfada hiç ürün yoksa bu URL bir kategori değil, atla
    ilk_deneme = urunleri_topla(kategori_adi, base_url)
    if not ilk_deneme:
        print(f"  ⏭️  Ürün bulunamadı, kategori atlanıyor.")
        return

    son_sayfa = son_sayfa_numarasini_al(base_url)
    print(f"  📊 Toplam sayfa: {son_sayfa}")

    kategori_linkleri = set()

    for sayfa_no in range(1, son_sayfa + 1):
        if sayfa_no == 1:
            sayfa_url = base_url
            # İlk sayfayı zaten yükledik, ürünleri yeniden çekmemize gerek yok
            # ama son_sayfa_numarasini_al base_url'e döndürdü, tekrar scroll edelim
            scroll_to_bottom()
            bulunanlar = urunleri_topla(kategori_adi, sayfa_url)
        else:
            sayfa_url = f"{base_url}?pg={sayfa_no}"
            driver.get(sayfa_url)
            time.sleep(3)
            scroll_to_bottom()
            bulunanlar = urunleri_topla(kategori_adi, sayfa_url)

        # Tekrar ekleme önleme
        mevcut_linkler = {u["link"] for u in tum_urunler}
        yeni = [
            u for u in bulunanlar
            if u["link"] and u["link"] not in mevcut_linkler and u["link"] not in kategori_linkleri
        ]
        for u in yeni:
            kategori_linkleri.add(u["link"])
        tum_urunler.extend(yeni)

        print(
            f"  📄 Sayfa {sayfa_no}/{son_sayfa}: "
            f"{len(bulunanlar)} ürün bulundu, {len(yeni)} yeni | "
            f"Toplam: {len(tum_urunler)}"
        )

        # Boş sayfa gelirse dur
        if not bulunanlar:
            print(f"  ⚠️  Boş sayfa, sayfalama erken bitiyor.")
            break


# ─────────────────────────────────────────────
# Ana akış
# ─────────────────────────────────────────────
try:
    # 1) Menüden tüm kategorileri otomatik keşfet
    kesfedilen_kategoriler = menuden_kategorileri_al()

    # Hem keşfedilenleri hem sabit listeyi birleştir (tekrar yok)
    tum_kategoriler = sorted(set(ANA_KATEGORILER) | set(kesfedilen_kategoriler))
    print(f"\n🗂️  Toplam işlenecek kategori: {len(tum_kategoriler)}\n")

    # 2) Her kategoriyi gez
    for kat_url in tum_kategoriler:
        kategori_isle(kat_url)

    # 3) CSV'ye kaydet
    if not os.path.exists("data"):
        os.makedirs("data")

    tarih = datetime.now().strftime("%Y-%m-%d")
    dosya_adi = f"data/loya_urunler_{tarih}.csv"

    with open(dosya_adi, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["kategori", "kategori_url", "isim", "fiyat", "link", "resim"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n{'='*55}")
    print(f"🎉 TOPLAM ÜRÜN: {len(tum_urunler)}")
    print(f"💾 Kaydedildi: {dosya_adi}")
    print(f"{'='*55}")

finally:
    driver.quit()
