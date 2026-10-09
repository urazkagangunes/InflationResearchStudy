# Koton Inflation Calculator

Calculates inflation metrics for Koton fashion products using TUIK 2026 CPI basket weights.

## Overview

Computes three inflation metrics for Koton products:

1. **Basic Inflation** - Basket-level price index change (%) calculated as sum of current prices vs sum of past prices
2. **Average Inflation** - Arithmetic mean of all per-product percentage price changes
3. **TUIK Weighted Average** - Weighted average using TUIK 2026 CPI basket weights, normalised to present categories

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/ClothingStores/Koton/koton_YYYY-MM-DD.csv`
- **Required columns**: `pk`, `sale_price`, `category`

### Key Columns

- `pk`: Unique product identifier for matching across dates
- `sale_price`: Current sale price (numeric)
- `category`: Hierarchical product category (mapped to TUIK groups)

## TUIK Category Mapping

Maps Koton categories to 2 TUIK groups:

| Category Pattern   | TUIK Group | Description                                              |
| ------------------ | ---------- | -------------------------------------------------------- |
| COSMETICS, PERFUME | 12         | Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler |
| All other products | 03         | Giyim ve ayakkabı                                        |

### Example Categories

- **TUIK 12 (Personal Care)**: `ACCESSORIES > COSMETICS > WOMEN > PERFUME > PERFUME W`
- **TUIK 03 (Clothing)**: `MENSWEAR > MENSWEAR > MEN > JERSEY > SHIRTS SS`

## Usage

```bash
# Calculate today's inflation
python inflation.py

# Calculate for specific date
python inflation.py --date 2026-03-20

# Compare two arbitrary dates
python inflation.py --date 2026-03-20 --compare 2026-03-10
```

## Output Files

### Detailed Data

`koton_inflation_YYYY-MM-DD.csv`

- Per-product inflation data with percentage price changes
- Columns: All original columns + `tuik_category` + `basic_inflation_{interval}` for each available interval
- `basic_inflation_{interval}`: Per-product percentage price change for that interval
- Location: `Inflations/Datas/ClothingStores/Koton/`

### Summary Data

`inflation_summary.csv`

- Store-level metrics, one row per date
- Columns: `date`, `avg_inflation_{interval}`, `tuik_weighted_{interval}` for each interval
- Appends new data, updates existing dates

## Example Output

### inflation_summary.csv

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-03-19,0.0,0.0,0.2214,0.1414,0.3049,0.1947,,
```

### koton_inflation_YYYY-MM-DD.csv (first columns)

```csv
pk,sku,name,brand,category,...,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Calculation Methodology

1. **Data Matching**: Products matched across dates using unique `pk`
2. **Per-product Inflation**: `((current_price - past_price) / past_price) * 100`
3. **Basic Inflation**: Sum-based basket index using matched products only
4. **Average Inflation**: Mean of all valid per-product inflation rates
5. **TUIK Weighted**: Category-level averages weighted by normalised TUIK weights

## Configuration

The `tuik_config.py` file contains:

- TUIK 2026 CPI basket weights
- `koton_category_to_tuik()` mapping function
- `normalised_weights()` helper function

## Integration

Designed to run after daily Koton scraping completes:

1. Koton scraper saves data to `InflationItems/Datas/ClothingStores/Koton/`
2. Run `python inflation.py` to calculate metrics
3. Results saved to `Inflations/Datas/ClothingStores/Koton/`

## Error Handling

- Missing historical data → NaN values for affected intervals
- Invalid price data → Coerced to NaN and excluded from calculations
- Unknown categories → Default to TUIK group 03 (clothing)
- Price changes of 0/0 → Handled gracefully, excluded from basket calculations
- Infinite inflation rates → Converted to NaN and excluded

## Dependencies

- Python 3.8+
- pandas
- Standard library: datetime, pathlib, logging
