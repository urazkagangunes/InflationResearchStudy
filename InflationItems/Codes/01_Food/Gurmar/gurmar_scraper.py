import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# -------------------------------------------------------------------
# KATEGORİLER
# -------------------------------------------------------------------
KATEGORILER = [
    ("Meyve ve Sebze",          "https://www.gurmar.com.tr/meyve-ve-sebze-c"),
    ("Et ve Tavuk",             "https://www.gurmar.com.tr/et-ve-tavuk-urunleri-c"),
    ("Süt, Kahvaltılık, Sark.", "https://www.gurmar.com.tr/sut-kahvaltiliklar-sarkuteri-c"),
    ("Temel Gıda",              "https://www.gurmar.com.tr/temel-gida-c"),
    ("İçecekler",               "https://www.gurmar.com.tr/icecekler-c"),
    ("Atıştırmalıklar",         "https://www.gurmar.com.tr/atistirmaliklar-c"),
    ("Bebek Ürünleri",          "https://www.gurmar.com.tr/bebek-urunleri-c"),
    ("Deterjan ve Temizlik",    "https://www.gurmar.com.tr/deterjan-temizlik-c"),
    ("Kişisel Bakım",           "https://www.gurmar.com.tr/kisisel-bakim-ve-hijyen-c"),
    ("Ev ve Yaşam",             "https://www.gurmar.com.tr/ev-yasam-c"),
    ("Kitap, Kırtasiye",        "https://www.gurmar.com.tr/kitap-kirtasiye-oyuncak-c"),
    ("Petshop",                 "https://www.gurmar.com.tr/petshop-c"),
]


def fiyat_cek(kart, driver):
    """
    span.product-price içindeki fiyatı çeker.
    İçinde kilogram-price div'i de olduğundan, sadece ilk text node'unu alıyoruz.
    Örnek HTML: <span class="product-price">₺62,45<div class="kilogram-price">...</div></span>
    """
    try:
        fiyat_span = kart.find_element(By.CSS_SELECTOR, "span.product-price")
        # JavaScript ile sadece ilk text node'unu al (kg fiyatını hariç tut)
        ham_fiyat = driver.execute_script(
            "return arguments[0].childNodes[0].textContent;", fiyat_span
        )
        return ham_fiyat.replace("₺", "").strip()
    except Exception:
        return ""


def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Ekransız mod
    chrome_options.add_argument("--no-sandbox")  # CI/CD için gerekli
    chrome_options.add_argument("--disable-dev-shm-usage")  # Bellek sınırlarına takılmamak için
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    tum_urunler = []

    for kategori_adi, link in KATEGORILER:
        print(f"\n🔍 İşleniyor: {kategori_adi}")
        driver.get(link)
        time.sleep(3)

        # ── Beklenen ürün sayısını çek ──────────────────────────────
        try:
            sayi_metni = driver.find_element(
                By.XPATH, "//*[contains(text(), 'ürün listeleniyor')]"
            ).text
            beklenen_sayi = int(re.search(r"\d+", sayi_metni).group())
            print(f"  📦 Beklenen ürün sayısı: {beklenen_sayi}")
        except Exception:
            beklenen_sayi = -1

        # ── Infinite scroll: Maksimum 50 kaydırma limiti ekleyelim ──
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        while scroll_count < 50: # Bir kategoride max 50 kez aşağı kaydır (Yeterli olacaktır)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # 2 saniyeyi 1.5'e çekebilirsin
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_count += 1

        time.sleep(2)  # Son yükleme için ekstra bekleme

        # ── Ürün kartlarını bul ─────────────────────────────────────
        # Gerçek HTML'e göre: div.product-vertical
        urun_kartlari = driver.find_elements(By.CSS_SELECTOR, "div.product-vertical")
        cekilen_urun_sayisi = 0

        for kart in urun_kartlari:
            try:
                # İsim: h4.product-title > span
                # Gerçek HTML: <h4 class="product-title"><span aria-describedby=":rp:">Armut...</span></h4>
                isim = kart.find_element(
                    By.CSS_SELECTOR, "h4.product-title span"
                ).text

                if not isim:
                    continue

                # Fiyat: span.product-price'ın sadece ilk text node'u
                fiyat = fiyat_cek(kart, driver)

                tum_urunler.append({
                    "kategori":      kategori_adi,
                    "product_name":  isim,
                    "product_price": fiyat,
                })
                cekilen_urun_sayisi += 1

            except Exception:
                continue

        # ── Sayı kontrolü ───────────────────────────────────────────
        if beklenen_sayi != -1:
            if cekilen_urun_sayisi == beklenen_sayi:
                print(f"  ✅ Başarılı! Beklenen: {beklenen_sayi} | Çekilen: {cekilen_urun_sayisi}")
            else:
                print(f"  ⚠️  Uyuşmazlık! Beklenen: {beklenen_sayi} | Çekilen: {cekilen_urun_sayisi}")
        else:
            print(f"  ✅ Çekilen ürün sayısı: {cekilen_urun_sayisi}")

    driver.quit()

    # ── CSV'ye kaydet ────────────────────────────────────────────────
    bugunun_tarihi = datetime.now().strftime("%Y-%m-%d")
    csv_dosyasi = f"Datas/Markets/Gurmar/gurmar_prices_{bugunun_tarihi}.csv"

    with open(csv_dosyasi, "w", newline="", encoding="utf-8-sig") as file:
        fieldnames = ["kategori", "product_name", "product_price"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n🎉 İşlem tamam! Toplam {len(tum_urunler)} ürün '{csv_dosyasi}' dosyasına kaydedildi.")


if __name__ == "__main__":
    main()
