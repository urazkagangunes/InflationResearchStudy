# Hapeloglu Market - Daily Price Data

**Author:** Batu Koray Masak

Daily product price scrapes from [Hapeloglu](https://www.hapeloglu.com/), a regional grocery market chain. Part of the **AI 201.A Inflation Research Study** tracking consumer price movements across Turkish markets.

## Data Format

Each daily scrape is saved as both CSV and TSV with the naming convention:

```
hapeloglu_YYYY-MM-DD.csv
hapeloglu_YYYY-MM-DD.tsv
```

## Schema

| Column | Type | Description |
|--------|------|-------------|
| `product_id` | int | Unique product identifier |
| `name` | str | Product name |
| `current_price` | float | Current listed price (TRY) |
| `regular_price` | float | Pre-discount price (NaN if not discounted) |
| `is_discounted` | bool | Whether the product is currently on sale |
| `discount_pct` | float | Discount percentage (NaN if not discounted) |
| `category` | str | Product category |
| `product_url` | str | Direct link to product page |
| `image_url` | str | Product image URL |
| `in_stock` | bool | Stock availability at scrape time |
| `scrape_date` | str | Date of scrape (YYYY-MM-DD) |
| `scrape_timestamp` | str | ISO 8601 timestamp of scrape |

## Categories

The store organizes products into 13 categories:

- Kisisel Bakim, Kozmetik
- Temel Gida
- Atistirmalik
- Deterjan, Temizlik
- Sut, Kahvaltilik
- Icecek
- Ev, Yasam
- Firin, Pastane
- Bebek
- Kagit, Islak Mendil
- Et, Tavuk, Balik
- Meyve, Sebze
- Evcil Hayvan

## Collection

- **Method:** SeleniumBase web scraper
- **Frequency:** Manual daily runs (Hopefully Raspberry PI daily running will be implemented in the future)
- **Coverage:** ~6,200+ products per scrape
- **File size:** ~1.8-1.9 MB per daily snapshot
- **Start date:** 2026-02-24

## Quality Check Notebook

`Quality_Check.ipynb` provides a comprehensive data validation pipeline for each daily scrape. It automatically resolves the current day's filename using `datetime.now()`, so it always targets the latest data without manual edits.

### Checks Performed

- **Shape and duplicates:** Verifies row/column counts and flags any duplicate entries.
- **Null analysis:** Reports null counts and percentages per column. Expected behavior: `regular_price` and `discount_pct` are NaN for non-discounted products (~96% of items on a typical day).
- **Data type validation:** Confirms all columns have the correct dtype for downstream analysis.
- **Price sanity:** Checks for negative and zero prices (should always be 0).
- **Outlier detection:** Uses the IQR method to flag price outliers. These are generally legitimate high-value items (bulk olive oil, kitchenware, premium meat) rather than scraping errors.
- **Discount validation:** Verifies discount percentages fall within a reasonable range (0-100%) and flags anything above 80% as suspicious.
- **Consistency check:** Cross-references `is_discounted` against `discount_pct` to catch any rows marked as discounted but missing a discount percentage, or vice versa.
- **Category distribution:** Outputs product counts per category to detect any unexpected shifts in catalog coverage.
- **Top outlier inspection:** Displays the 20 most expensive outlier products with their names and categories for manual review.

## Notes

- Both CSV and TSV are provided for flexibility; content is identical.
- Outliers should not be dropped without manual inspection, most are valid products.