# Samsung Inflation Calculator

Computes daily inflation metrics for the Samsung Türkiye product
catalogue scraped by
`InflationItems/Codes/TechnologicalProducts/Samsung/scripts/main.py`.

## Metrics

| Metric                  | Description                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `basic_inflation_<lbl>` | Per-product percentage price change relative to the comparison date         |
| `avg_inflation_<lbl>`   | Arithmetic mean of all per-product inflation rates                          |
| `tuik_weighted_<lbl>`   | TUIK 2026 CPI-weighted average across the TUIK groups present in the data  |

Standard interval labels: `1d`, `7d`, `15d`, `30d`.  Custom comparisons
supported via the `--compare` flag.

## Inputs / Outputs

```
InflationItems/Datas/TechnologicalProducts/Samsung/samsung_<DATE>.csv    (input)
        ↓
Inflations/Codes/TechnologicalProducts/Samsung/inflation.py
        ↓
Inflations/Datas/TechnologicalProducts/Samsung/samsung_inflation_<DATE>.csv   (per-product)
Inflations/Datas/TechnologicalProducts/Samsung/inflation_summary.csv          (store-level, append-only)
```

The calculator joins datasets on the `id` column (Samsung `modelCode`)
and uses `shown_price` (post-promotion) as the authoritative
current-price value.

## TUIK Mapping

Samsung's catalogue spans three distinct TUIK CPI main groups, so the
TUIK-weighted metric is meaningfully different from the arithmetic
average (unlike single-group retailers):

| TUIK Group | Weight (2026) | Samsung Categories                                             |
| ---------- | ------------- | -------------------------------------------------------------- |
| `05`       | 7.92 %        | Refrigerators, Washers & Dryers, Dishwashers, Air Purifier,    |
|            |               | Air Conditioners, Vacuum Cleaners, Cooking Appliances,         |
|            |               | Microwave Ovens                                                |
| `08`       | 3.10 %        | Smartphones, Tablets, Watches, Rings, Mobile Accessories,      |
|            |               | Monitors, Memory & Storage                                     |
| `09`       | 4.34 %        | TVs, TV Accessories, Projectors, Audio Sound, Audio Devices    |

See `tuik_config.py` for the full category → group mapping.  Weights
are normalised to sum to 100.0 across whichever groups are actually
present in the day's scraped file.

## Usage

```bash
# Standard daily run (uses today's date and the four standard intervals)
python inflation.py

# Specific target date
python inflation.py --date 2026-04-29

# Arbitrary two-date comparison
python inflation.py --date 2026-04-29 --compare 2026-04-22
```

The scraper's `main.py` invokes `calculate_inflation()` automatically
after a successful run, so this script normally does not need to be
invoked manually.

## Output Schema

### `samsung_inflation_<DATE>.csv` (per-product)

All columns from the scraped CSV (`id`, `sku`, `name`, `brand`,
`category`, `sub_category`, `family`, `regular_price`, `shown_price`,
`discount_rate`, `unit`, `status`, `image_url`, `product_url`) plus:

| Column                      | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `tuik_category`             | TUIK group code for this SKU (`05` / `08` / `09`)            |
| `basic_inflation_1d`        | % change vs. yesterday (or `NaN` when no past data)          |
| `basic_inflation_7d`        | % change vs. 7 days ago                                      |
| `basic_inflation_15d`       | % change vs. 15 days ago                                     |
| `basic_inflation_30d`       | % change vs. 30 days ago                                     |

### `inflation_summary.csv` (store-level, append-only)

One row per scrape day:

| Column                   | Description                                        |
| ------------------------ | -------------------------------------------------- |
| `date`                   | Scrape date (`YYYY-MM-DD`)                         |
| `avg_inflation_<lbl>`    | Arithmetic mean of per-SKU `basic_inflation_<lbl>` |
| `tuik_weighted_<lbl>`    | TUIK-weighted average across the present groups    |

## Design Notes

- **Matching by modelCode**: Samsung uses stable alphanumeric codes
  like `SM-S931BLGGTUR` that persist for the life of a product, which
  makes cross-date joining robust even when display names change.
- **Price field**: we consistently use `shown_price` (post-promotion)
  rather than `regular_price`, because the displayed price is what a
  consumer would actually pay — and what shows up in the CPI.
- **Missing history is handled gracefully**: any interval for which
  the comparison CSV does not exist yields `NaN` for that interval's
  columns, without failing the pipeline.
