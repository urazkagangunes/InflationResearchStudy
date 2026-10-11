# D&R Scraper

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Kaynak (D&R kategori > alt kategori, 2026-10-10 verisi) |
|---|---|---|
| Cep telefonu | ✅ | Telefon > Cep Telefonları (3) |
| Bilgisayar | — | Bilgisayar / tablet satılmıyor; sadece aksesuarları |
| Bilgisayar çevre birimleri | ✅ | Tablet & PC Aksesuarları > Çevre Birimleri (82) |
| Ses ve görüntü ekipmanı | ✅ | Ev Elektroniği > Kulaklıklar, Ses Sistemleri & Speaker, Pikaplar, Radyolar, Projeksiyon; Foto & Kamera > Fotoğraf Makineleri, Kameralar, Aksiyon Kameralar, Dronelar |
| Televizyon | — | |
| Diğer iletişim cihazları | ✅ | Giyilebilir Teknoloji > Akıllı Saatler, Akıllı Bileklikler (30) |
| Bilgi ve iletişim aksesuarları | ✅ | Telefon Aksesuarları (kablo, şarj cihazı, powerbank, kılıf), Tablet & PC Aksesuarları > Notebook Çantaları / Aksesuarları, Foto & Kamera > Kamera Aksesuarları, Kobo e-kitap aksesuarları |
| Cep telefonu hizmet ücreti | — | |
| İnternet hizmet ücreti | — | |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | — | |
| Dijital içerik / streaming platform aboneliği | — | |

Kapsam dışı (aynı CSV'ye yazılır, `Category` / `Subcategory` kolonlarıyla ayrılabilir): Oyun & Konsol,
Küçük Ev Aletleri, Isıtma ve Soğutma, Kişisel Bakım & Sağlık, Ofis Teknolojileri (hesap / etiket
makinesi), Outdoor (elektrikli scooter).

Daily technology scraper for `https://www.dr.com.tr/`.

Scope:
- collects only technology-related categories
- discovers the approved top-level categories under `Elektronik`
- also includes the standalone `Ofis Teknolojileri` catalog
- writes daily CSVs to `InflationItems/Datas/08_Communication/DR/`

Run:

```bash
uv run python InflationItems/Codes/08_Communication/DR/dr_scraper.py
```

From inside the scraper directory, this also works like your other module-based
scrapers:

```bash
cd InflationItems/Codes/08_Communication/DR
uv run python -m scripts.run_scraper
```

Useful smoke-test flags:

```bash
uv run python InflationItems/Codes/08_Communication/DR/dr_scraper.py --page-limit 1 --output /tmp/dr_smoke.csv
uv run python InflationItems/Codes/08_Communication/DR/dr_scraper.py --only telefon,oyun-konsol
```
