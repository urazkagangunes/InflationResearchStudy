# InflationResearchStudy

A web-based price index for Türkiye. Every day the project collects prices from Turkish online retailers and rental listings, stores them as dated CSV files, and turns them into inflation figures weighted by TÜİK's consumer price basket. The aim is an independent, high-frequency view of inflation and the cost of living that can be compared with the official numbers.

The research project started in February 2026 and is ongoing, with prices collected daily. Its methodology and findings are published in the IEEE conference paper:
- 📄 **Paper:** [*A CPI-Weighted Web-Based Price Index for Monitoring Inflation and Cost of Living in Türkiye*](asyu2026/A_CPI_Weighted_Web_Based_Price_Index_Paper.pdf) (ASYU 2026)
- 📊 **Presentation:** [Conference Presentation Slides](asyu2026/A_CPI_Weighted_Web_Based_Price_Index_Presentation.pdf)

## What is collected

Scrapers cover about 110 retailers and service providers in 13 categories, plus rental listings for 46 city groups. Each category maps to a TÜİK COICOP 2026 group, which decides its weight in the index.

| Category folder | What it covers | COICOP group | In the index |
|---|---|---|---|
| `01_Food` | Supermarkets (food and groceries) | 01 Food and non-alcoholic beverages | Yes |
| `02_Alcohol_Tobacco` | Alcohol and tobacco products | 02 Alcoholic beverages and tobacco | Planned |
| `03_Clothing` | Clothing and footwear chains | 03 Clothing and footwear | Yes |
| `04_Housing` | Rental listings by city | 04 Housing (rent only) | Yes, handled separately |
| `05_Furnishings` | Furniture, home textiles, hardware and appliances | 05 Furnishings and household equipment | Yes |
| `06_Health` | Doctor, dentist, diagnostics, physical therapy, medicine and glasses | 06 Health | Yes, monthly |
| `07_Transport` | Taxi, minibus, train, ferry, boat fares & vehicle prices | 07 Transport | Yes |
| `08_Communication` | Electronics and technology retailers | 08 Information and communication | Yes |
| `09_Recreation` | Books, stationery, recreation | 09 Recreation, sport and culture | Yes |
| `10_Education` | Educational services | 10 Education services | Planned |
| `11_Restaurants` | Hotels, holiday packages, Hajj/Umrah, restaurant dining | 11 Restaurants and accommodation | Yes |
| `12_Insurance` | Insurance and financial services | 12 Insurance and financial services | Planned |
| `13_Personal_Care` | Cosmetics, salons, jewelry, watches, daycare, legal, notary, inspection | 13 Personal care, social protection, misc | Yes |

Groups are structured according to the official TÜİK COICOP-13 standard. Weighted figures are re-normalised over the groups present on each run.

## Repository layout

```
asyu2026/
  A_CPI_Weighted_Web_Based_Price_Index_Paper.pdf        conference paper (ASYU 2026)
  A_CPI_Weighted_Web_Based_Price_Index_Presentation.pdf presentation slides
InflationItems/
  Codes/<Category>/<Store>/    scraper code, one folder per store
  Datas/<Category>/<Store>/    daily price files, one CSV per store and day
Inflations/
  Codes/turkey_inflation.py    the country-wide index (see below)
  Codes/turkey_inflation_methodology.md
  Codes/tuik_config.py         TÜİK basket weights and category mapping
  Codes/<Category>/<Store>/    store-level inflation scripts
  Codes/Hungerthresholds/      hunger threshold (food basket cost) module
  Codes/product-to-ctagory/    product to TÜİK category mapping
  Datas/<Category>/<Store>/    store-level inflation outputs
  Datas/Final_Reports/         country-wide reports
```

Some categories also keep a daily server script at the repository root, for example `run_cosmetics.sh`.

## How the index is calculated

`Inflations/Codes/turkey_inflation.py` reads the raw CSV files of every category directly. For a target date it loads each store's file for that day and for the comparison dates (15 and 30 days earlier by default), matches products within each store by their normalised name, and computes:

| Metric | Meaning |
|---|---|
| Basic inflation | Change in the summed basket price (Dutot) |
| Average inflation | Mean of product-level changes (Carli) |
| Median inflation | Median product change; usually 0% because most prices do not change in a month |
| Median inflation (nonzero) | Median change among products whose price changed |
| Increased / decreased / unchanged | Share of matched products in each group |
| TÜİK weighted (products) | Category changes weighted by the COICOP 2026 basket |
| TÜİK weighted (full) | The same with rent (group 04) added from the housing data |

Price changes larger than 80% within one interval are treated as scraping errors and left out. The same product seen in several stores or categories is averaged so it counts once. Results go to `Inflations/Datas/Final_Reports/`. The full method, with the deduplication steps and known limitations, is in `Inflations/Codes/turkey_inflation_methodology.md`.

```bash
cd Inflations/Codes
python turkey_inflation.py                                       # today, 15- and 30-day intervals
python turkey_inflation.py --date 2026-05-01                     # a specific date
python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
```

The hunger threshold module in `Inflations/Codes/Hungerthresholds/` prices a fixed monthly food basket of 16 items across 13 online supermarkets; its method is in `hunger_threshold_methodology.md`.

## Running a scraper

```bash
pip install -r requirements.txt
python "InflationItems/Codes/<Category>/<Store>/<scraper>.py"
```

Most scrapers use plain HTTP (`requests`, `aiohttp`, `curl_cffi`); some still need a browser through Selenium or Playwright, so Chrome (and `playwright install` for Playwright) must be available. A scraper writes its CSV into the matching `InflationItems/Datas/<Category>/<Store>/` folder. Several categories are scraped every night on team servers and pushed here; check with the category owner before running a whole category yourself.

## Data rules

Everyone works with everyone else's data, so every file has to look the same:

1. Save prices as CSV, comma separated, one file per store and day inside `InflationItems/Datas/<Category>/<Store>/`.
2. Put the date in the file name as `YYYY-MM-DD`, for example `karaca_2026-10-06.csv`. The index script finds files by this pattern and skips other date formats such as `2026_10_06` or `06.10.2026`.
3. The header must contain a `product_name` and a `price` column (`Product Name`, `isim`, `Product Cost` and `fiyat` are also accepted). Files without them are not read.
4. Pull regularly, and always before you push, so you build on your teammates' latest code and data.

## Team

Each category has a responsible member, who maintains its scrapers and data, and a controller, who checks the data. The full history of contributions is in the commit log.

## Citation

If you use this dataset, methodology, or code in your research, please cite our ASYU 2026 conference paper:

```bibtex
@inproceedings{gunes2026cpi,
  title={A CPI-Weighted Web-Based Price Index for Monitoring Inflation and Cost of Living in T{\"u}rkiye},
  author={G{\"u}ne{\c{s}}, Uraz Ka{\u{g}}an and Demirta{\c{s}}, Onur Kaan and Y{\i}ld{\i}r{\i}m, Efe and {\c{C}}ilda{\c{s}}, Ata Hakan and Masak, Batu Koray and {\"O}nl{\"u}k{\"u}{\c{s}}, Batu and Er, Arhan and G{\"u}len, Doruk and {\c{C}}etin, Can Kenan and G{\"u}ng{\"o}r, Eren and Pehlivan, Batuhan Burak and Tural, Elif Sude and Kolmogorova, Aleksandra and {\"O}renli, Sinem and U{\u{g}}ra{\c{s}}kan, Dilara and Y{\i}ld{\i}z, Olcay Taner},
  booktitle={2026 Innovations in Intelligent Systems and Applications Conference (ASYU)},
  year={2026},
  publisher={IEEE}
}
```

