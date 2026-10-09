import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Hedef özel sayfamız
url = "https://www.vakko.com/esarbini-tasarla"

gizli_user_agent = os.getenv("VAKKO_USER_AGENT")

# Standart tarayıcı kılığımız (WAF'a yakalanmamak için)
headers = {
    "User-Agent": gizli_user_agent
}

print("Özel tasarım eşarp sayfası taranıyor...\n")

# İsteği atıyoruz
response = requests.get(url, headers=headers)

if response.status_code == 200:
    # Sayfanın bütün HTML kodunu BeautifulSoup'a verip parçalıyoruz
    soup = BeautifulSoup(response.content, "html.parser")

    # Senin ekran görüntüsünde bulduğun o "div" sınıfını arıyoruz
    tasarim_ogeleri = soup.find_all("div", class_="custom-scarf__item")

    if not tasarim_ogeleri:
        print("Sayfa çekildi ama 'custom-scarf__item' class'ı bulunamadı. Yapı değişmiş olabilir.")

    # Bulduğumuz her bir fiyat kutusu için dönüyoruz
    for i, oge in enumerate(tasarim_ogeleri, 1):
        # 1. FİYATI ÇEKME: Görsele göre fiyat, div'in direkt altındaki ilk metin (text node)
        fiyat = oge.contents[0].strip() if oge.contents else "Fiyat Bulunamadı"

        # 2. BEDEN/KUMAŞ ÇEKME: Fiyatın altındaki "label" etiketinin içindeki metin
        label = oge.find("label", class_="custom-scarf__item-border")
        # Metnin içindeki fazladan boşlukları ve satır atlamalarını temizliyoruz
        beden = " ".join(label.text.split()) if label else "Beden Bulunamadı"

        print(f"{i}. Seçenek")
        print(f"Tür/Beden: {beden}")
        print(f"Fiyat: {fiyat}")
        print("-" * 30)

else:
    print(f"HATA! Sayfaya erişilemedi. Durum Kodu: {response.status_code}")