# TÜİK Group 13: Personal Care, Social Protection and Miscellaneous Goods & Services

This module implements scrapers and CPI calculation for official TÜİK COICOP Group 13:
**"Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler"** (Total CPI Basket Weight: **4.4935%**).

Every sub-category includes **at least 3 independent scrapers/data sources** to provide deep coverage, high resilience, and rigorous academic methodology.

---

## 1. Sub-Category Breakdown & 18 Scrapers Overview

| COICOP Code | Description | Basket Weight (%) | Normalized Share (%) | Scraper Name | Data Source & Scope | Scraper Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1311 / 1312** | **Kişisel Bakım Ürünleri & Aletleri** | **1.2867%** | **28.63%** | 14 Cosmetic Stores | Dermomarket, Watsons, Rossmann, Gratis, Boyner, Sephora, Yves Rocher, Flormar, Golden Rose, Avon, Kiehl's, L'Occitane, M&S, Beymen Beauty | `InflationItems/Codes/Cosmetics/` |
| **1313** | **Kuaför & Berber Hizmetleri** | **0.5853%** | **13.03%** | **1. Kolay Randevu** | Anlık kuaför/berber salon randevu ve paket fiyatları | `Codes/Hairdresser/KolayRandevu/` |
| | | | | **2. Berberler Odası** | İstanbul, Ankara, İzmir Berberler Odası resmi 1./2./3. sınıf saç ve sakal kesim tarifeleri | `Codes/Hairdresser/BerberlerOdasi/` |
| | | | | **3. Kuaförler Odası** | Kadın kuaförleri odaları resmi saç kesim, fön, boya, röfle, manikür/pedikür tarifeleri | `Codes/Hairdresser/KuaforlerOdasi/` |
| **1321** | **Mücevherat ve Kol Saatleri** | **0.4489%** | **9.99%** | **1. Canlı Altın Piyasası** | Gram altın, çeyrek, yarım, cumhuriyet, 22 ayar bilezik canlı kuyumcu satış fiyatları | `Codes/Jewelry/Gold/` |
| | | | | **2. Altınbaş Perakende Takı** | Altınbaş perakende altın kolye, bilezik, yüzük, küpe ve alyans katalog fiyatları | `Codes/Jewelry/Altinbas/` |
| | | | | **3. Saat & Saat** | 300+ marka ve model kol saati (Tommy Hilfiger, Casio, Seiko, Fossil, Lacoste vb.) | `Codes/Jewelry/SaatVeSaat/` |
| **1330** | **Sosyal Koruma ve Kreş Hizmetleri** | **0.3517%** | **7.83%** | **1. Metropol Kreş Endeksi** | İstanbul, Ankara, İzmir özel kreş ve gündüz bakımevi tam gün/yarım gün aylık bakım | `Codes/Daycare/Daycare/` |
| | | | | **2. Bölgesel Kreşler** | Kocaeli, Bursa, Antalya, Adana, Gaziantep, Konya bölgesel sanayi illeri kreş ücretleri | `Codes/Daycare/KreslerCom/` |
| | | | | **3. Erken Çocuk & Bebek Bakımı** | 0-1 yaş bebek kreşi, 1-2 yaş oyun grubu ve oryantasyon programı aylık ücretleri | `Codes/Daycare/ChildcareServices/` |
| **1390** | **Çeşitli Hizmetler (Noter, Hukuk, Ekspertiz)** | **0.7737%** | **17.22%** | **1. Noterlik Resmi Tarifesi** | Adalet Bakanlığı Resmi Gazete Noterlik Ücret Tarifesi (yazı, çeviri, tescil, emanet) | `Codes/Services/Notary/` |
| | | | | **2. Noter Araç Tescil Masrafları** | TNB ikinci el araç satış, devir, sicil ve değerli kağıt masrafları | `Codes/Services/NotaryVehicle/` |
| | | | | **3. Noter Gayrimenkul Sözleşmeleri** | Noterlik taşınmaz satış sözleşmesi asgari/azami yasal tavan ve taban ücretleri | `Codes/Services/NotaryRealEstate/` |
| | | | | **4. TBB Asgari Avukatlık Tarifesi** | Türkiye Barolar Birliği Resmi Gazete Avukatlık Asgari Ücret Tarifesi (AAÜT) | `Codes/Services/Legal/` |
| | | | | **5. İstanbul Barosu Tavsiye Çizelgesi** | İstanbul Barosu serbest piyasa koşulları tavsiye niteliğindeki en az ücret çizelgesi | `Codes/Services/IstanbulBarosu/` |
| | | | | **6. Resmi Arabuluculuk Tarifesi** | Adalet Bakanlığı dava şartı iş, ticaret, kira uyuşmazlıkları resmi arabuluculuk tarifesi | `Codes/Services/Mediation/` |
| | | | | **7. Pilot Garage Ekspertiz** | Pilot Garage ekspertiz paket fiyatları (Eko, Bold, First Class, Dyno motor testi) | `Codes/Services/AutoExpertise/` |
| | | | | **8. TÜVTÜRK Araç Muayenesi** | Ulaştırma Bakanlığı resmi periyodik araç muayenesi ve egzoz emisyon ölçüm bedeli | `Codes/Services/Tuvturk/` |
| | | | | **9. Dynobil Ekspertiz** | Dynobil Türkiye geneli şube araç ekspertiz paketleri | `Codes/Services/Dynobil/` |

---

## 2. Directory Structure

```
InflationItems/
├── Codes/
│   ├── Cosmetics/                  # 14 Cosmetics scrapers (1312)
│   ├── Jewelry/
│   │   ├── Gold/                   # gold_scraper.py (1321101)
│   │   ├── Altinbas/               # altinbas_scraper.py (1321101)
│   │   └── SaatVeSaat/             # saatvesaat_scraper.py (1321105)
│   ├── Hairdresser/
│   │   ├── KolayRandevu/           # kolayrandevu_scraper.py (1313)
│   │   ├── BerberlerOdasi/         # berberler_odasi_scraper.py (1313101)
│   │   └── KuaforlerOdasi/         # kuaforler_odasi_scraper.py (1313102)
│   ├── Services/
│   │   ├── Notary/                 # notary_tariff_scraper.py (1390901)
│   │   ├── NotaryVehicle/          # notary_vehicle_transfer_scraper.py (1390901)
│   │   ├── NotaryRealEstate/       # notary_realestate_scraper.py (1390901)
│   │   ├── Legal/                  # legal_tariff_scraper.py (1390903)
│   │   ├── IstanbulBarosu/         # istanbul_barosu_scraper.py (1390903)
│   │   ├── Mediation/              # mediation_tariff_scraper.py (1390903)
│   │   ├── AutoExpertise/          # pilotgarage_scraper.py (1390902)
│   │   ├── Tuvturk/                # tuvturk_scraper.py (1390902)
│   │   └── Dynobil/                # dynobil_scraper.py (1390902)
│   ├── Daycare/
│   │   ├── Daycare/                # daycare_scraper.py (1330101)
│   │   ├── KreslerCom/             # kresler_com_scraper.py (1330101)
│   │   └── ChildcareServices/      # childcare_services_scraper.py (1330101)
│   └── PersonalCareServices/
│       ├── run_all_group13_scrapers.py
│       └── README.md
└── Datas/                          # Standardized daily CSVs (product_name,price)
    ├── Cosmetics/
    ├── Jewelry/
    ├── Hairdresser/
    ├── Services/
    └── Daycare/

Inflations/
├── Codes/
│   └── PersonalCareServices/
│       └── group13_inflation.py    # Group 13 Unified CPI Inflation Calculator
└── Datas/
    └── Group13/                    # Output summary tables & matched item CSVs
```

---

## 3. How to Run

### Run All 18 Service & Jewelry Scrapers
```bash
python InflationItems/Codes/PersonalCareServices/run_all_group13_scrapers.py --services-only
```

### Run All Scrapers (Including 14 Cosmetics Stores)
```bash
python InflationItems/Codes/PersonalCareServices/run_all_group13_scrapers.py
```

### Calculate Group 13 CPI Inflation
```bash
python Inflations/Codes/PersonalCareServices/group13_inflation.py --date 2026-10-06
```

---

## 4. Output Data Standards

All scrapers strictly adhere to repository specifications:
- **Column 0:** `product_name`
- **Column 1:** `price`
- **File naming:** `<store_or_service>_<YYYY-MM-DD>.csv`
- All code, docstrings, and console messages are written in English.
