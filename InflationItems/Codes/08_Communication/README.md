# TÜİK 08 — Bilgi ve iletişim scraper'ları

Bu klasördeki scraper'ların TÜİK 08 kalemlerine dağılımı. Sayılar **tek bir günün** (2026-10-10)
CSV'lerinden çıkarılmış **yaklaşık** ürün sayılarıdır. Hizmet kalemlerinde "ürün", bir tarife,
paket, abonelik planı ya da onarım fiyatı satırıdır.

Her scraper'ın kendi README'sinde hangi kalemleri hangi site kategorisinden topladığı yazıyor.

`BeymenTech` scraper'ı ve `deploy/scraper-server/` (cron sunucusu) inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`); bu repoda sadece BeymenTech'in verisi (`Datas/08_Communication/Beymen/beymen_tech_*`) var.

## Özet

| Kalem | Scraper sayısı | Scraper'lar | Günlük ürün (yaklaşık) | BeymenTech hariç |
|---|---|---|---|---|
| Cep telefonu | 7 | Vatan, Pozitif, Beymen, BeymenTech, Samsung, Huawei, DR | ~970 | ~840 |
| Bilgisayar | 6 | Vatan, Beymen, Pozitif, BeymenTech, Samsung, Huawei | ~1.700 | ~1.300 |
| Bilgisayar çevre birimleri | 7 | Vatan, Beymen, BeymenTech, Pozitif, DR, Samsung, Huawei | ~2.800 | ~2.400 |
| Ses ve görüntü ekipmanı | 7 | Beymen, BeymenTech, DR, Vatan, Pozitif, Samsung, Huawei | ~3.100 | ~1.900 |
| Televizyon | 4 | Vatan, Beymen, BeymenTech, Samsung | ~420 | ~320 |
| Diğer iletişim cihazları | 7 | Vatan, Beymen, BeymenTech, Pozitif, DR, Huawei, Samsung | ~570 | ~460 |
| Bilgi ve iletişim aksesuarları | 7 | Beymen, BeymenTech, Pozitif, Vatan, DR, Samsung, Huawei | ~11.500 | ~6.500 |
| Cep telefonu hizmet ücreti | 1 (`Telecom/scraper.py`, 4 operatör) | Turkcell, Türk Telekom, Vodafone, NetGSM | ~760 | ~760 |
| İnternet hizmet ücreti | 1 (`Telecom/internet.py`, 6 sağlayıcı) | Türk Telekom, Superonline, Kablonet, TurkNet, Vodafone, Milleni | ~360 | ~360 |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | 1 (`Telecom/repair.py`, 5 kaynak) | GSM İletişim, Huawei, Apple, Samsung, Egemek | ~5.900 | ~5.900 |
| Dijital içerik / streaming platform aboneliği | 1 (`Telecom/streaming.py`, 12 servis) | YouTube Premium, Disney+, Spotify, Tivibu, TV+, MUBI, Netflix, HBO Max, GAIN, Prime, Apple TV+, Tabii | ~34 | ~34 |

Scraper'lar listede o kalemdeki ürün sayısına göre büyükten küçüğe sıralı.

**BeymenTech hariç** kolonu: `Beymen` (sunucu) ve `BeymenTech` (GitHub Actions) Beymen'in aynı
"Teknoloji" kategorisini çekiyor, yani ürünlerin neredeyse tamamı iki kez sayılıyor. Kalemdeki
tekil ürün sayısı için bu kolona bakılmalı.

## Ürün ve cihaz kalemleri: scraper başına

| Scraper | Cep telefonu | Bilgisayar | Çevre birimleri | Ses ve görüntü | Televizyon | Diğer iletişim | Aksesuar | Kapsam dışı | Toplam |
|---|---|---|---|---|---|---|---|---|---|
| Beymen (sunucu) | ~130 | ~430 | ~440 | ~1.200 | ~100 | ~110 | ~5.100 | ~3.500 | ~10.900 |
| BeymenTech (GitHub Actions) | ~130 | ~340 | ~440 | ~1.200 | ~100 | ~110 | ~5.100 | ~3.500 | ~10.800 |
| VatanComputer | ~500 | ~490 | ~1.700 | ~130 | ~170 | ~190 | ~430 | ~1.800 | ~5.400 |
| PozitifTeknoloji | ~140 | ~380 | ~140 | ~100 | — | 98 | ~440 | 23 | ~1.300 |
| DR | 3 | — | 89 | ~480 | — | 30 | ~370 | ~430 | ~1.400 |
| Samsung | 61 | 22 | 32 | 16 | 52 | 10 | ~100 | 92 | ~390 |
| Huawei | 12 | 15 | 9 | 13 | — | 27 | 40 | — | 116 |

Nasıl sayıldı:

- **Site kategorisinden** (daha güvenilir): DR (`Category` / `Subcategory`), Huawei (`Category`),
  Samsung (`category`), PozitifTeknoloji (`category`; "Fırsatlar" / "Outlet" gibi karışık
  kategorilerde ürün adından).
- **Ürün adındaki anahtar kelimelerden** (daha kaba): Beymen, BeymenTech ve VatanComputer. Bu
  CSV'lerde kategori kolonu yok. Kılıf, kordon ve şarj cihazı gibi aksesuarlar önce ayrılır
  (örneğin "iPhone 17 uyumlu kılıf" telefon sayılmaz), sonra telefon, bilgisayar, TV, saat,
  çevre birimi ve ses/görüntü kelimeleri aranır. Hata payı birkaç yüz ürün mertebesinde.
- Eşleme tercihleri: tabletler **Bilgisayar**, akıllı saat ve bileklikler **Diğer iletişim
  cihazları**, bilgisayar bileşenleri (SSD, RAM, anakart, kasa) **Bilgisayar çevre birimleri**,
  Apple TV ve HomePod **Ses ve görüntü ekipmanı** altında.

**Kapsam dışı**: aynı CSV'lere düşen ama 08'e girmeyen ürünler. Oyun konsolları, VR gözlükleri,
küçük ev aletleri, beyaz eşya, kişisel bakım cihazları ve yazılım lisansları.

Koçtaş scraper'ı sadece elektrikli el aleti (matkap, testere, taşlama) topladığı için 2026-10-11'de
05'e taşındı (`05_Furnishings/ConstructionSuppliesMarkets/Koctas`, TÜİK 055 Ev ve bahçe alet ve
ekipmanları) ve 08 sunucusundan kaldırıldı.

## Hizmet kalemleri: kaynak başına

| Kalem | Scraper | Kaynak başına satır (2026-10-10) | Toplam |
|---|---|---|---|
| Cep telefonu hizmet ücreti | `Telecom/scraper.py` | Türk Telekom ~420, Turkcell ~220, Vodafone ~110, NetGSM 8 | ~760 |
| İnternet hizmet ücreti | `Telecom/internet.py` | Türk Telekom ~200, Superonline 92, Kablonet 27, TurkNet 14, Vodafone 11, Milleni 7 | ~360 |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | `Telecom/repair.py` | GSM İletişim ~4.500, Huawei ~600, Apple ~530, Samsung ~170, Egemek 87 | ~5.900 |
| Dijital içerik / streaming platform aboneliği | `Telecom/streaming.py` | YouTube Premium 5, Disney+ 4, Spotify 4, Tivibu 4, TV+ 4, MUBI 3, Netflix 3, HBO Max 2, GAIN 2, Prime 1, Apple TV+ 1, Tabii 1 | 34 |

- Mobil tarifelerde faturalı ve faturasız tarifeler ile ek paketler ayrı satırdır.
- Onarımda her model + hizmet (örneğin "iPhone 15 ekran değişimi") bir satırdır. Sepet henüz
  belirlenmedi, kaynakların yayımladığı her şey toplanıyor.
- Streaming'de her plan ve periyot (aylık / yıllık) bir satırdır. `streaming.py` TOD'u da
  destekliyor (2026-10-09 yerel çalıştırmada 8 satır), ama sunucunun 2026-10-10 çıktısında TOD dosyası
  yok; sunucu logunda kontrol edilmeli.
