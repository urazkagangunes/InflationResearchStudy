# D&R Scraper

Daily technology scraper for `https://www.dr.com.tr/`.

Scope:
- collects only technology-related categories
- discovers the approved top-level categories under `Elektronik`
- also includes the standalone `Ofis Teknolojileri` catalog
- writes daily CSVs to `InflationItems/Datas/TechnologicalProducts/DR/`

Run:

```bash
uv run python InflationItems/Codes/TechnologicalProducts/DR/dr_scraper.py
```

From inside the scraper directory, this also works like your other module-based
scrapers:

```bash
cd InflationItems/Codes/TechnologicalProducts/DR
uv run python -m scripts.run_scraper
```

Useful smoke-test flags:

```bash
uv run python InflationItems/Codes/TechnologicalProducts/DR/dr_scraper.py --page-limit 1 --output /tmp/dr_smoke.csv
uv run python InflationItems/Codes/TechnologicalProducts/DR/dr_scraper.py --only telefon,oyun-konsol
```
