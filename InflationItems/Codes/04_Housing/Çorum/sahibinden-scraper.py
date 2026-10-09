import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import csv
import time
import random
from datetime import date

CITIES = {
    "corum":    "https://www.sahibinden.com/kiralik-daire/corum",
    "cankiri":  "https://www.sahibinden.com/kiralik-daire/cankiri",
    "kirikkale":"https://www.sahibinden.com/kiralik-daire/kirikkale",
    "kirsehir": "https://www.sahibinden.com/kiralik-daire/kirsehir"
}

def captcha_kontrol(driver):
    """CAPTCHA veya erişim engeli varsa kullanıcıdan bekle."""
    url = driver.current_url.lower()
    title = driver.title.lower()

    engel_url      = any(k in url   for k in ["captcha", "blocked", "verify", "challenge", "giris"])
    engel_title    = any(k in title for k in ["captcha", "erişim", "engel", "robot", "doğrula"])
    ilan_yok       = "searchResultsItem" not in driver.page_source and "kiralik-daire" in url

    if engel_url or engel_title or ilan_yok:
        print(f"\n⚠️  Engel algılandı! URL: {driver.current_url}")
        print(f"   Sayfa başlığı: {driver.title}")
        input("  Tarayıcıda çöz / giriş yap, sonra Enter'a bas...")
        time.sleep(2)

def son_sayfayi_bul(driver):
    """Sayfa navigasyon linklerinden toplam sayfa sayısını bul."""
    sayfa_linkleri = driver.find_elements(By.CSS_SELECTOR, ".pageNavigator a")
    numaralar = []
    for a in sayfa_linkleri:
        if "prevNextBut" in (a.get_attribute("class") or ""):
            break
        try:
            numaralar.append(int(a.text.strip()))
        except:
            continue
    return max(numaralar) if numaralar else 1


# --- Tarayıcıyı başlat ---
driver = uc.Chrome(version_main=145)

# --- Giriş ---
print("Sahibinden.com giriş sayfası açılıyor...")
driver.get("https://secure.sahibinden.com/giris")
input("\nTarayıcıda giriş yap, ana sayfaya yönlendirildikten sonra Enter'a bas...")
time.sleep(3)
print("Giriş başarılı, scraping başlıyor...\n")


# --- Ana döngü ---
for sehir, base_url in CITIES.items():
    print(f"\n{'='*40}")
    print(f"{sehir.upper()} işleniyor...")
    print(f"{'='*40}")

    driver.get(base_url)
    time.sleep(random.uniform(6, 10))
    captcha_kontrol(driver)

    son_sayfa = son_sayfayi_bul(driver)
    print(f"Toplam sayfa: {son_sayfa}")

    dosya_adi = f"{sehir}_{date.today()}.csv"

    with open(dosya_adi, mode="w", newline="", encoding="utf-8-sig") as csvfile:
        yazici = csv.writer(csvfile)
        yazici.writerow(["Date", "Price", "District", "Rooms"])

        for sayfa in range(son_sayfa):
            offset = sayfa * 20
            url = f"{base_url}?pagingOffset={offset}"
            driver.get(url)
            time.sleep(random.uniform(4, 8))
            captcha_kontrol(driver)

            rows = driver.find_elements(By.CSS_SELECTOR, "tr.searchResultsItem")
            print(f"  Sayfa {sayfa+1}/{son_sayfa}: {len(rows)} ilan")

            for row in rows:
                try:
                    price    = int(row.find_element(By.CSS_SELECTOR, ".searchResultsPriceValue").text.strip().replace(".", "").replace(" TL", "").replace(",", ""))
                    location = row.find_element(By.CSS_SELECTOR, ".searchResultsLocationValue").text.strip()
                    attrs    = row.find_elements(By.CSS_SELECTOR, ".searchResultsAttributeValue")
                    rooms    = attrs[1].text.strip() if len(attrs) > 1 else "?"

                    yazici.writerow([date.today(), price, location, rooms])
                    print(f"    {location} | {rooms} | {price}")
                except Exception as e:
                    print(f"    Hata: {e}")
                    continue

    print(f"\n✅ {sehir} tamamlandı → {dosya_adi}")

driver.quit()
print("\n✅ Tüm şehirler tamamlandı!")
