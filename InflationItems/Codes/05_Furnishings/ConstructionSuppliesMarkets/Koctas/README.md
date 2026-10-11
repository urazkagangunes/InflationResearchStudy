# Koçtaş scraper

## TÜİK kalemi

**05 Mobilya, ev aletleri ve ev bakım hizmetleri › 055 Ev ve bahçe alet ve ekipmanları.**
Ürünlerin hepsi elektrikli / motorlu el aleti (COICOP 0551 motorlu aletler); TÜİK sepetinde
055 altında bu ürünler için ayrı bir kalem yok, 055 grubunun ağırlığı altında kullanılabilir.

2026-10-11'e kadar `08_Communication/Koctas` altındaydı ve 08 sunucusunda her gün 03:00'te
çalışıyordu. Hiçbir 08 kalemine girmediği için 05'e taşındı ve 08 sunucusundan kaldırıldı;
çalıştırma planı artık 05 ekibinde.

Toplanan kategoriler (2026-10-10 verisi, 5.949 ürün): Matkaplar, Testereler, Taşlamalar,
Zımpara ve Polisaj, Akülü Vidalamalar, Kırıcılar ve Deliciler, Boya Tabancaları, Kaynak
Makineleri.

## Nasıl çalışır

koctas.com.tr Akamai'nin davranış kontrolünün arkasında (düz HTTP istemcileri 403 alır). Scraper
tüm çalıştırma boyunca tek bir headless undetected-chromedriver açık tutar ve her kategori
sayfasının yazdığı GTM dataLayer `product-impressions` verisini okur. Düşük RAM için resim/CSS
kapalı, izleyiciler engelli ve Chrome belirli sayfa sayısında bir yeniden başlatılır (bir tam
çalıştırma 2 vCPU / 1.9 GB sunucuda ~16 dk, ~620 MB).

Koçtaş kategoriyi sayısal `/c/<id>` ile yönlendirir. Her sayfanın dataLayer liste adı beklenen adla
karşılaştırılır ve `site_category` kolonuna yazılır; Koçtaş bir kimliği başka kategoriye
taşırsa veride görünür. Kategori listesi `koctas_scraper.py` içindeki `CATEGORIES`.

## Çalıştırma

```bash
python InflationItems/Codes/05_Furnishings/ConstructionSuppliesMarkets/Koctas/koctas_scraper.py
```

Sınırlı test için `KOCTAS_MAX_PAGES=1` ortam değişkeni kategori başına sayfa sayısını sınırlar.
Chrome sürümü otomatik bulunur; gerekirse `CHROME_VERSION_MAIN` ile sabitlenir.

## Çıktı

`InflationItems/Datas/05_Furnishings/ConstructionSuppliesMarkets/Koctas/koctas_YYYY-MM-DD.csv`

`product_id, product_name, price, brand, category, site_category`
