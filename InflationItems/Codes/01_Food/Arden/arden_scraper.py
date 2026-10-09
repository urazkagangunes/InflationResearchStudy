import time
import csv
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


chrome_options = Options()
# Headless kapalı — site headless modda hata sayfası gösteriyor
# chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 20)

KATEGORILER = [
    "https://ardenmarket.com.tr/et-ve-tavuk.html",
    "https://ardenmarket.com.tr/meyve-ve-sebze.html",
    "https://ardenmarket.com.tr/kahvaltilik.html",
    "https://ardenmarket.com.tr/sut-urunleri.html",
    "https://ardenmarket.com.tr/temel-gida.html",
    "https://ardenmarket.com.tr/dondurulmus-urunler.html",
    "https://ardenmarket.com.tr/unlu-mamul-tatli.html",
    "https://ardenmarket.com.tr/dondurma.html",
    "https://ardenmarket.com.tr/atistirmalik.html",
    "https://ardenmarket.com.tr/icecekler.html",
    "https://ardenmarket.com.tr/temizlik-urunleri.html",
    "https://ardenmarket.com.tr/kisisel-bakim.html",
    "https://ardenmarket.com.tr/bebek.html",
    "https://ardenmarket.com.tr/evcil-hayvan-urunleri.html",
    "https://ardenmarket.com.tr/ev-yasam-oyuncak.html",
    "https://ardenmarket.com.tr/ofis-ve-teknoloji.html",
    "https://ardenmarket.com.tr/firsat-urunleri.html",
    "https://ardenmarket.com.tr/catalog/category/view/s/sarkuteri-urunleri/id/4463/",
]

tum_urunler = []


def konum_sec():
    driver.get("https://ardenmarket.com.tr/")
    time.sleep(6)

    # delivery-button'ı birden fazla seçiciyle dene
    konum_btn = None
    btn_selectors = [
        (By.ID, "delivery-button"),
        (By.CSS_SELECTOR, "[id*='delivery']"),
        (By.CSS_SELECTOR, "button[class*='delivery']"),
        (By.XPATH, "//button[contains(text(),'Konum') or contains(text(),'Teslimat') or contains(text(),'Adres') or contains(text(),'delivery')]"),
        (By.CSS_SELECTOR, ".delivery-button"),
        (By.CSS_SELECTOR, "[data-role='delivery']"),
    ]

    for by, selector in btn_selectors:
        try:
            konum_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, selector)))
            print(f"  ✅ Konum butonu bulundu: {by}={selector}")
            break
        except:
            continue

    if konum_btn is None:
        # Butonu bulamazsak sayfadaki tüm butonları logla, debug için
        tum_butonlar = driver.find_elements(By.TAG_NAME, "button")
        print(f"  ⚠️  delivery-button bulunamadı! Sayfadaki butonlar ({len(tum_butonlar)} adet):")
        for b in tum_butonlar[:15]:
            print(f"     id='{b.get_attribute('id')}' class='{b.get_attribute('class')}' text='{b.text[:50]}'")

        # Yine de devam etmeyi dene — belki konum seçimi gerekmiyordur
        print("  ⚠️  Konum seçimi atlanıyor, devam ediliyor...")
        return

    konum_btn.click()
    time.sleep(3)

    # delivery_state dropdown
    try:
        state_select = Select(WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "delivery_state"))
        ))
        # İstanbul'u bul (value veya text olarak)
        istanbulu_sec = False
        for o in state_select.options:
            if "stanbul" in o.text or o.get_attribute("value") == "İstanbul":
                state_select.select_by_value(o.get_attribute("value"))
                istanbulu_sec = True
                break
        if not istanbulu_sec:
            state_select.select_by_index(1)  # İlk geçerli seçenek
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠️  İl seçimi hatası: {e}")

    # delivery_city dropdown
    try:
        ilce = Select(WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "delivery_city"))
        ))
        for o in ilce.options:
            if o.get_attribute("value") != "":
                ilce.select_by_value(o.get_attribute("value"))
                break
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠️  İlçe seçimi hatası: {e}")

    # delivery_neighborhood dropdown
    try:
        mahalle = Select(WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "delivery_neighborhood"))
        ))
        for o in mahalle.options:
            if o.get_attribute("value") != "":
                mahalle.select_by_value(o.get_attribute("value"))
                break
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠️  Mahalle seçimi hatası: {e}")

    # Submit butonu
    try:
        submit_selectors = [
            "#delivery-form button[type='submit']",
            "form button[type='submit']",
            "button[type='submit']",
        ]
        for sel in submit_selectors:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                break
            except:
                continue
    except Exception as e:
        print(f"  ⚠️  Submit hatası: {e}")

    print("✅ Konum seçildi")
    time.sleep(8)


def scroll_to_bottom():
    onceki = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == onceki:
            break
        onceki = yeni


def son_sayfa_numarasini_al():
    """
    Site sliding-window pagination kullanıyor (1 2 3 4 5 > gibi).
    Gerçek son sayfayı bulmak için > butonuna tıklayarak en sona gidiyoruz,
    oradan max sayfa numarasını okuyoruz. Sonra ilk sayfaya geri dönüyoruz.
    """
    import re

    def sayfadaki_max_numara():
        numaralar = []
        elems = driver.find_elements(By.CSS_SELECTOR, ".pages-items .item a, .pages-items .item strong")
        for e in elems:
            try:
                numaralar.append(int(e.text.strip()))
            except:
                pass
        for e in driver.find_elements(By.CSS_SELECTOR, "a[href*='?p=']"):
            href = e.get_attribute("href") or ""
            m = re.search(r'\?p=(\d+)', href)
            if m:
                numaralar.append(int(m.group(1)))
        return max(numaralar) if numaralar else 1

    def sonraki_btn():
        btns = driver.find_elements(By.CSS_SELECTOR, ".pages-items .item.pages-item-next a")
        return btns[0] if btns else None

    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        current_url = driver.current_url

        # > butonunu takip ederek en son sayfaya git
        adim = 0
        while True:
            btn = sonraki_btn()
            if btn is None:
                break
            btn.click()
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            adim += 1
            if adim > 100:
                break

        son = sayfadaki_max_numara()
        print(f"  🔍 Son sayfa: {son} ({adim} adım ilerlendi)")

        # İlk sayfaya geri dön
        driver.get(current_url)
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        return son

    except Exception as ex:
        print(f"  ⚠️  son_sayfa_numarasini_al hatası: {ex}")
        return 1

def sonraki_sayfa_var_mi():
    """'Sonraki' (next) butonu aktif mi? Varsa True döner."""
    try:
        sonraki = driver.find_elements(By.CSS_SELECTOR, ".pages-items .item.pages-item-next a")
        return len(sonraki) > 0
    except:
        return False


def urunleri_topla(kategori_adi):
    urunler = driver.find_elements(By.CSS_SELECTOR, "li.product-item")
    sayfa_urunleri = []

    for u in urunler:
        try:
            isim = ""
            for sel in [".product-name", ".product-title", "h2", "h3", "[class*='name']"]:
                try:
                    isim = u.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if isim:
                        break
                except:
                    continue

            fiyat = ""
            for sel in [".price-wrapper .price", ".price", "[class*='price']"]:
                try:
                    fiyat = u.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if fiyat:
                        break
                except:
                    continue

            link = ""
            try:
                link = u.find_element(By.TAG_NAME, "a").get_attribute("href")
            except:
                pass

            resim = ""
            try:
                resim = u.find_element(By.TAG_NAME, "img").get_attribute("src")
            except:
                pass

            if isim or link:
                sayfa_urunleri.append({
                    "kategori": kategori_adi,
                    "isim": isim,
                    "fiyat": fiyat,
                    "link": link,
                    "resim": resim,
                })
        except:
            continue

    return sayfa_urunleri


def kategori_isle(kategori_url):
    """
    Bir kategorinin TÜM sayfalarını dolaşır.
    Önce sayı bazlı sayfalama dener (daha hızlı).
    Sayı bulunamazsa 'Sonraki' butonuyla ilerler (yavaş ama garantili).
    """
    kategori_adi = kategori_url.rstrip("/").split("/")[-1]
    kategori_adi = kategori_adi.replace(".html", "").replace("-", " ").title()
    print(f"\n📂 Kategori: {kategori_adi}")

    base_url = kategori_url.split("?")[0]

    # İlk sayfayı yükle
    driver.get(base_url)
    time.sleep(3)
    scroll_to_bottom()

    son_sayfa = son_sayfa_numarasini_al()
    print(f"  📊 Toplam sayfa: {son_sayfa}")

    kategori_linkleri = set()  # Bu kategoride eklenen linkler (duplicate önleme)

    if son_sayfa > 1:
        # ── Sayı bazlı sayfalama ──────────────────────────────────────────
        for sayfa_no in range(1, son_sayfa + 1):
            if sayfa_no == 1:
                sayfa_url = base_url
            else:
                sayfa_url = f"{base_url}?p={sayfa_no}"
                driver.get(sayfa_url)
                time.sleep(3)
                scroll_to_bottom()

            print(f"  📄 Sayfa {sayfa_no}/{son_sayfa}: {sayfa_url}", end=" → ")
            bulunanlar = urunleri_topla(kategori_adi)

            mevcut_linkler = {u["link"] for u in tum_urunler}
            yeni = [u for u in bulunanlar if u["link"] not in mevcut_linkler and u["link"] not in kategori_linkleri]
            for u in yeni:
                kategori_linkleri.add(u["link"])
            tum_urunler.extend(yeni)

            print(f"{len(bulunanlar)} ürün, {len(yeni)} yeni | Toplam: {len(tum_urunler)}")

    else:
        # ── Fallback: "Sonraki" butonu ile ilerle ────────────────────────
        # İlk sayfayı işle
        sayfa_no = 1
        print(f"  📄 Sayfa {sayfa_no} (next-buton modu): {base_url}", end=" → ")
        bulunanlar = urunleri_topla(kategori_adi)
        mevcut_linkler = {u["link"] for u in tum_urunler}
        yeni = [u for u in bulunanlar if u["link"] not in mevcut_linkler]
        tum_urunler.extend(yeni)
        print(f"{len(bulunanlar)} ürün, {len(yeni)} yeni | Toplam: {len(tum_urunler)}")

        while sonraki_sayfa_var_mi():
            sayfa_no += 1
            sonraki_btn = driver.find_element(By.CSS_SELECTOR, ".pages-items .item.pages-item-next a")
            sonraki_url = sonraki_btn.get_attribute("href")
            driver.get(sonraki_url)
            time.sleep(3)
            scroll_to_bottom()

            print(f"  📄 Sayfa {sayfa_no} (next-buton): {sonraki_url}", end=" → ")
            bulunanlar = urunleri_topla(kategori_adi)
            mevcut_linkler = {u["link"] for u in tum_urunler}
            yeni = [u for u in bulunanlar if u["link"] not in mevcut_linkler]
            tum_urunler.extend(yeni)
            print(f"{len(bulunanlar)} ürün, {len(yeni)} yeni | Toplam: {len(tum_urunler)}")

            # Sonsuz döngü koruması
            if sayfa_no > 200:
                print("  ⚠️  200 sayfa limitine ulaşıldı, sonraki kategoriye geçiliyor.")
                break


try:
    konum_sec()

    for kategori_url in KATEGORILER:
        kategori_isle(kategori_url)

    # --- Tarihli dosya kaydı ---
    if not os.path.exists('data'):
        os.makedirs('data')

    tarih = datetime.now().strftime("%Y-%m-%d")
    dosya_adi = f"data/arden_urunler_{tarih}.csv"

    with open(dosya_adi, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["kategori", "isim", "fiyat", "link", "resim"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n{'='*50}")
    print(f"🎉 TOPLAM ÜRÜN: {len(tum_urunler)}")
    print(f"💾 {dosya_adi} kaydedildi")
    print(f"{'='*50}")

finally:
    driver.quit()
