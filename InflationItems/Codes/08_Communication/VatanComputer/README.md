# Vatan Bilgisayar scraper

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Kaynak (kök kategori, 2026-10-10 verisinden örnek) |
|---|---|---|
| Cep telefonu | ✅ | `cep-telefonu-modelleri`: akıllı telefonlar ve tuşlu telefonlar |
| Bilgisayar | ✅ | `bilgisayar`: dizüstü (MacBook, Vivobook, Ideapad…), tablet, iMac |
| Bilgisayar çevre birimleri | ✅ | `bilgisayar-bilesenleri`, `aksesuarlar`, `ofis-malzemeleri`: monitör, klavye, mouse, SSD, yazıcı, modem |
| Ses ve görüntü ekipmanı | ✅ | `fotograf-makinesi-video-kamera`: kamera, fotoğraf makinesi; kulaklık, hoparlör |
| Televizyon | ✅ | `televizyon`: Smart / QLED TV'ler |
| Diğer iletişim cihazları | ✅ | Akıllı saatler (Apple Watch, Huawei Watch) |
| Bilgi ve iletişim aksesuarları | ✅ | `aksesuarlar`: kılıf, şarj cihazı, kablo |
| Cep telefonu hizmet ücreti | — | |
| İnternet hizmet ücreti | — | |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | — | |
| Dijital içerik / streaming platform aboneliği | — | |

Kapsam dışı (aynı CSV'ye yazılır): `ev-mutfak`, `kisisel-bakim-urunleri`, `iklimlendirme`,
`oyun-hobi`, `outlet` kök kategorilerinden gelen ürünler. CSV'de kategori kolonu olmadığı için
bunlar ürün adından ayrılmalı.

## Nasıl çalışır

12 kök kategori URL'sinden başlar. Bir sayfa ürün listesi değil de alt kategori vitriniyse,
en fazla 3 seviye derinliğe kadar alt kategori linklerini izler (sayfa başına en fazla 80 alt
kategori). Ürün listelerinde sayfa başına 24 ürünle `?page=N` sayfalama yapar.

## Çalıştırma

```bash
python InflationItems/Codes/08_Communication/VatanComputer/vatan_comp.py
```

Sunucuda `bin/run_scraper.sh vatan` ile her gün 04:00'te çalışır (`deploy/scraper-server/`, inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`)).

## Çıktı

`InflationItems/Datas/08_Communication/VatanComputer/vatan_computer_YYYY-MM-DD.csv`

Başlıksız, `;` ayraçlı iki kolon: `ürün adı;fiyat` (fiyat sitedeki metin, ör. `59.999 TL`).
