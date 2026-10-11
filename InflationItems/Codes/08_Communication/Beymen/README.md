# Beymen teknoloji scraper (sunucu)

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Kaynak (Beymen "Teknoloji" kategorisi 95935, 2026-10-10 verisinden örnek) |
|---|---|---|
| Cep telefonu | ✅ | iPhone 17 / 17 Pro akıllı telefonlar |
| Bilgisayar | ✅ | Dizüstü bilgisayarlar (ThinkPad, Legion, ROG), tabletler |
| Bilgisayar çevre birimleri | ✅ | Monitör, klavye, mouse, yazıcı, harici disk |
| Ses ve görüntü ekipmanı | ✅ | Kulaklık, hoparlör, fotoğraf makinesi, projeksiyon cihazı |
| Televizyon | ✅ | Smart / QNED / Crystal UHD TV'ler |
| Diğer iletişim cihazları | ✅ | Akıllı saatler (Garmin Venu, Huawei Watch GT) |
| Bilgi ve iletişim aksesuarları | ✅ | Telefon / laptop kılıfları, şarj cihazları, saat kordonları |
| Cep telefonu hizmet ücreti | — | |
| İnternet hizmet ücreti | — | |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | — | |
| Dijital içerik / streaming platform aboneliği | — | |

Kapsam dışı (aynı CSV'ye yazılır): oyun konsolları ve VR gözlükleri, küçük ev aletleri
(süpürge, kahve makinesi, ütü), kişisel bakım cihazları. CSV'de kategori kolonu olmadığı için
bunlar ürün adından ayrılmalı.

## Nasıl çalışır

Beymen'in listeleme API'si (`/api/product/list`, `categoryId=95935`) Akamai arkasında.
Çoğu çalıştırmada Chrome TLS parmak izli `curl_cffi` istemcisi cookie olmadan geçer ve tarayıcı
açılmaz. API sadece 403 dönerse tek bir headless undetected-chromedriver açılır, Akamai
cookie'leri alınıp diske yazılır (`.beymen_cookies.json`, git'te yok sayılıyor) ve istekler
`curl_cffi` ile devam eder. Toplu isteklerden önce tarayıcı her zaman kapatılır.

Aynı kategoriyi GitHub Actions üzerinde ayrıca `BeymenTech` scraper'ı çeker (`beymen_tech_*`); o scraper inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`).

## Çalıştırma

```bash
python InflationItems/Codes/08_Communication/Beymen/scraper.py
```

Sunucuda `bin/run_scraper.sh beymen` ile her gün 02:00'de çalışır (`deploy/scraper-server/`, inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`)).

## Çıktı

`InflationItems/Datas/08_Communication/Beymen/beymen_YYYY-MM-DD.csv`

`Tarih, UrunID, UrunAdi, FiyatFloat`
