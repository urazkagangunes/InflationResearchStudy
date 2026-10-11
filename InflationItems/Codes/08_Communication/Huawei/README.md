# Huawei Türkiye scraper

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Kaynak (sitedeki kategori, 2026-10-10 verisi) |
|---|---|---|
| Cep telefonu | ✅ | Telefon (12) |
| Bilgisayar | ✅ | PC / MateBook (3), Tablet / MatePad (12) |
| Bilgisayar çevre birimleri | ✅ | Monitör (1), Router / WiFi Mesh (8) |
| Ses ve görüntü ekipmanı | ✅ | Ses: FreeBuds, FreeArc (13) |
| Televizyon | — | |
| Diğer iletişim cihazları | ✅ | Akıllı Saat (27) |
| Bilgi ve iletişim aksesuarları | ✅ | Aksesuar: kayış, kalem, klavye kılıfı, şarj cihazı (40) |
| Cep telefonu hizmet ücreti | — | |
| İnternet hizmet ücreti | — | |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | — | Huawei yedek parça fiyatları `Telecom/repair.py` içinde |
| Dijital içerik / streaming platform aboneliği | — | |

Kapsam dışı ürün yok; bütün katalog 08 kapsamında.

## Nasıl çalışır

Tarayıcı kullanmaz, sadece `requests`. Katalog `/.rest/service/ecommerce/v1/products/tr` ucundan
gelir (~290 ürün kimliği, çoğu satıştan kalkmış). Fiyatlar sitenin kendi çağırdığı
`queryMinPriceAndInv` ucundan toplu çekilir; sadece fiyatı olan ürünler (~120) satıştadır.
Fiyat, sitede gösterilen "Başlangıç" fiyatıdır (renk/varyantlar arasındaki en düşük birim fiyat).

Hiçbir listeleme sayfasında görünmeyen ürünlerin (bazı aksesuarlar) adı URL'den türetilir ve
`listed_on_site=False` yazılır; analizde sadece sitede görünen ürünler isteniyorsa bu kolonla
filtrelenebilir.

## Çalıştırma

```bash
python InflationItems/Codes/08_Communication/Huawei/huawei_scraper.py
```

Sunucuda `bin/run_scraper.sh huawei` ile her gün 01:10'da çalışır (`deploy/scraper-server/`, inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`)).

## Çıktı

`InflationItems/Datas/08_Communication/Huawei/huawei_YYYY-MM-DD.csv`

`Product ID, Product Name, Price, Category, listed_on_site, Product URL`
