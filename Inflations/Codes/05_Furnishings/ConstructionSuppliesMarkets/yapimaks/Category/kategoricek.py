import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import os
import re


def kategori_bul(soup):
    bc = soup.find('ul', class_='breadcrumb') or soup.find('div', class_='breadcrumb')
    if bc:
        links = bc.find_all(['a', 'span'])
        if len(links) >= 2:
            return links[-2].get_text(strip=True)

    meta_desc = soup.find('meta', property='og:description')
    if meta_desc:
        content = meta_desc.get('content', '')
        if 'ürünleri' in content:
            return content.split('ürünleri')[0].strip()

    title = soup.find('title')
    if title:
        parts = [p.strip() for p in re.split(r'[|]|\s-\s', title.text)]
        if len(parts) >= 2:
            for p in parts[1:]:
                if "Yapımaks" not in p and len(p) > 2:
                    return p
    return "Bilinmeyen Kategori"


def baslat_scraper(csv_yolu, cikti_json="kategori_haritasi.json"):
    if not os.path.exists(csv_yolu):
        print("CSV bulunamadı!")
        return

    df = pd.read_csv(csv_yolu)
    urller = df['url'].dropna().unique()

    scraper = cloudscraper.create_scraper()

    harita = {}
    if os.path.exists(cikti_json):
        with open(cikti_json, 'r', encoding='utf-8') as f:
            try:
                harita = json.load(f)
            except:
                harita = {}

    taranacak = [u for u in urller if u not in harita]
    print(f"Yeni Taranacak: {len(taranacak)}")

    bekleme_suresi = 1.5  # Başlangıç bekleme süresini biraz artırdık

    for i, url in enumerate(taranacak, 1):
        try:
            res = scraper.get(url, timeout=15)

            if res.status_code == 200:
                soup = BeautifulSoup(res.content, 'html.parser')
                kategori = kategori_bul(soup)
                harita[url] = kategori
                print(f"[{i}/{len(taranacak)}] {kategori}")
                # Başarılı istekte standart bekleme
                time.sleep(bekleme_suresi)

            elif res.status_code == 429:
                print(f"\n[!] 429 Hatası! Sunucu bizi engelledi. 60 saniye soğuma bekleniyor...")
                time.sleep(60)  # 1 dakika tam duruş
                # Döngüyü kırmıyoruz, 60 sn sonra aynı URL'yi tekrar deneyecek (i-1 mantığı için continue kullanmıyoruz, enumerate devam eder ama haritaya eklenmediği için bir sonraki çalıştırmada oradan başlar)
                continue

            else:
                print(f"[{i}/{len(taranacak)}] Hata: {res.status_code}")
                time.sleep(2)

            if i % 20 == 0:
                with open(cikti_json, 'w', encoding='utf-8') as f:
                    json.dump(harita, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(5)

    with open(cikti_json, 'w', encoding='utf-8') as f:
        json.dump(harita, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    HEDEF_CSV = r"C:\Users\arhan\PycharmProjects\inflationstudymirror\Datas\yapimaks\2026-03-28.csv"
    baslat_scraper(HEDEF_CSV)