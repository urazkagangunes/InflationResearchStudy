import requests
import csv
import time
import random
import sys
from datetime import datetime
from seleniumbase import SB


def get_stealth_cookies(target_url):
    print(f"Bot korumasını aşmak için çerezler toplanıyor: {target_url}")
    # uc=True ile Undetected-Chromedriver aktif ediliyor
    with SB(uc=True, headless=True) as sb:
        sb.uc_open_with_reconnect(target_url, reconnect_time=5)
        sb.sleep(8)  # JavaScript'in Akamai tokenlarını üretmesi için bekleme
        sb.execute_script("window.scrollBy(0, 300)")
        sb.sleep(2)

        raw_cookies = sb.get_cookies()
        print("Çerezler başarıyla alındı.")
        return {c['name']: c['value'] for c in raw_cookies}


def scrape_beymen():
    base_api_url = "https://www.beymen.com/api/product/list"
    target_web_url = "https://www.beymen.com/tr/teknoloji-95935"

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"beymen_enflasyon_{date_str}.csv"

    # 1. Aşama: GitHub Actions ortamında engellenmemek için çerezleri çal
    try:
        cookies = get_stealth_cookies(target_web_url)
    except Exception as e:
        print(f"Çerez alınırken hata oluştu: {e}")
        sys.exit(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    # 2. Aşama: Alınan çerezlerle API'yi döngüye sok
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # ID, aynı ürünün isim değiştirse bile takip edilebilmesi için eklendi. Fiyat metni yerine hesaplamaya uygun Float fiyat eklendi.
        writer.writerow(["Tarih", "UrunID", "UrunAdi", "FiyatFloat"])

        with requests.Session() as session:
            session.headers.update(headers)
            session.cookies.update(cookies)

            for page in range(1, 201):
                # CERRAHİ MÜDAHALE 1: includeDocuments geri eklendi
                params = {
                    "languageCode": "tr",
                    "sayfa": page,
                    "categoryId": "95935",
                    "includeDocuments": "true"
                }

                try:
                    response = session.get(base_api_url, params=params, timeout=15)

                    if response.status_code == 403:
                        print(f"Kritik Hata: Sayfa {page}'de 403 yedik. Çerezler patladı veya süresi doldu.")
                        sys.exit(1)

                    response.raise_for_status()
                    json_data = response.json()

                    inner_data = json_data.get("data", {})

                    # CERRAHİ MÜDAHALE 2: API productList veya products dönüyor olabilir, ikisini de kontrol et
                    products = inner_data.get("productList") or inner_data.get("products") or []

                    if not products:
                        print(f"Sayfa {page}'de ürün bulunamadı.")
                        print(f"\n--- DEBUG BİLGİSİ ---")
                        print(f"HTTP Status: {response.status_code}")
                        # Veri çok uzunsa terminali kilitlememesi için str() kısıtlaması
                        print(f"Gelen JSON Yanıtı (İlk 500 karakter): {str(json_data)[:500]}")
                        print(f"---------------------\n")
                        print(f"Toplam taranan sayfa sayısı: {page - 1}. İşlem tamam.")
                        break

                    for item in products:
                        writer.writerow([
                            date_str,
                            item.get("productId"),
                            item.get("displayName"),
                            item.get("actualPrice")
                            # Float değer, istatistiksel analiz (Pandas vb.) için doğrudan kullanılabilir.
                        ])

                    print(f"Sayfa {page} kaydedildi. ({len(products)} ürün)")
                    time.sleep(random.uniform(1.5, 3.5))  # Bloklanmamak için rastgele gecikme

                except Exception as e:
                    print(f"Döngü hatası (Sayfa {page}): {e}")
                    sys.exit(1)


if __name__ == "__main__":
    scrape_beymen()