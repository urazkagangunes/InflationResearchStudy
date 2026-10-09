# Nezih Scraper

Daily books and stationery scraper for `https://www.nezih.com.tr/`.

Scope:
- collects the assigned `Kitap` and `Kirtasiye` categories
- reads Nezih's embedded `PRODUCT_DATA` payloads instead of scraping visual text
- paginates through `?pg=N` listing pages
- writes daily CSVs to `InflationItems/Datas/BooksStationery/Nezih/`

Run:

```bash
uv run python InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py
```

From inside the scraper directory, this also works:

```bash
cd InflationItems/Codes/BooksStationery/Nezih
uv run python -m scripts.run_scraper
```

Useful smoke-test flags:

```bash
uv run python InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py --page-limit 1 --output /tmp/nezih_smoke.csv
uv run python InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py --only kitap --page-limit 2
```
