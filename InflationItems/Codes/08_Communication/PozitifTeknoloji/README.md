# Pozitif Teknoloji scraper

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Kaynak (sitedeki kategori, 2026-10-10 verisi) |
|---|---|---|
| Cep telefonu | ✅ | iPhone |
| Bilgisayar | ✅ | Mac, MacBook, iPad, iPad Air / Pro / Mini |
| Bilgisayar çevre birimleri | ✅ | Mouse ve Klavyeler, Monitör & Ekranlar, Depolama (SSD/HDD), Yazıcı |
| Ses ve görüntü ekipmanı | ✅ | Kulaklıklar ve Hoparlörler, TV ve Ev (Apple TV, HomePod), projeksiyon cihazları |
| Televizyon | — | "TV ve Ev" kategorisinde televizyon yok; Apple TV bir medya kutusu |
| Diğer iletişim cihazları | ✅ | Apple Watch |
| Bilgi ve iletişim aksesuarları | ✅ | Kılıflar ve Koruyucu Ürünler, iPhone / Mac / iPad aksesuarları, Apple Pencil, şarj aletleri |
| Cep telefonu hizmet ücreti | — | |
| İnternet hizmet ücreti | — | |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | — | |
| Dijital içerik / streaming platform aboneliği | — | |

Kapsam dışı: Yazılım Lisans (Microsoft 365). Outlet / yenilenmiş ürünler `is_outlet` ile ayrılır.

## Nasıl çalışır

pt.com.tr WooCommerce üzerinde çalışıyor. Herkese açık Store API (`/wp-json/wc/store/v1/products`)
fiyat, stok, SKU ve kategoriyle bütün kataloğu döndürür (~1.300 ürün, 100'lük sayfalarla).
Bütün ürünler tutulur; `in_stock` ve `is_outlet` kolonları sayesinde analiz sırasında
filtrelenebilir.

## Çalıştırma

```bash
python InflationItems/Codes/08_Communication/PozitifTeknoloji/pozitifTeknoloji_scraper.py
```

Sunucuda `bin/run_scraper.sh pozitif` ile her gün 01:20'de çalışır (`deploy/scraper-server/`, inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`)).

## Çıktı

`InflationItems/Datas/08_Communication/PozitifTeknoloji/pozitifTeknoloji_YYYY-MM-DD.csv`

`name, category, price, regular_price, sku, product_id, in_stock, is_outlet, categories, url`
