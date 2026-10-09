# Migros Inflation Calculator

Calculates inflation metrics for Migros supermarket products using TUIK 2026 CPI basket weights.

## Overview

Computes three inflation metrics for Migros products:

1. **Basic Inflation** - Basket-level price index change (%) calculated as sum of current prices vs sum of past prices
2. **Average Inflation** - Arithmetic mean of all per-product percentage price changes
3. **TUIK Weighted Average** - Weighted average using TUIK 2026 CPI basket weights, normalised to present categories

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/Markets/Migros/migros_YYYY-MM-DD.csv`
- **Required columns**: `id`, `shown_price`, `category`

### Key Columns

- `id`: Unique product identifier for matching across dates
- `shown_price`: Displayed price after discounts (numeric)
- `category`: Product category (mapped to TUIK groups)

## TUIK Category Mapping

Maps ~700 Migros categories to 9 TUIK groups:

| TUIK Group | Description                | Example Categories          |
| ---------- | -------------------------- | --------------------------- |
| 01         | Gıda ve alkolsüz içecekler | Süt, Yoğurt, Ekmek, Meyve   |
| 02         | Alkollü içecekler, tütün   | Malt İçeceği                |
| 03         | Giyim ve ayakkabı          | Kadın Giyim, Çocuk Giyim    |
| 05         | Mobilya, ev aletleri       | Temizlik, Deterjan, Tencere |
| 06         | Sağlık                     | İlk Yardım, Takviye Edici   |
| 07         | Ulaştırma                  | Oto Aksesuar, Oto Bakım     |
| 08         | Bilgi ve iletişim          | Telefon, Tablet, HDMI       |
| 09         | Eğlence, dinlence          | Kitap, Oyuncak, Scooter     |
| 12         | Kişisel bakım              | Şampuan, Krem, Deodorant    |

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

`migros_inflation_YYYY-MM-DD.csv`

- Per-product inflation data with percentage price changes
- Columns: All original columns + `tuik_category` + `basic_inflation_{interval}` for each available interval
- `basic_inflation_{interval}`: Per-product percentage price change for that interval
- Location: `Inflations/Datas/Markets/Migros/`

### Summary Data

`inflation_summary.csv`

- Store-level metrics, one row per date
- Columns: `date`, `avg_inflation_{interval}`, `tuik_weighted_{interval}` for each interval
- Appends new data, updates existing dates

## Example Output

### inflation_summary.csv

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-03-19,-1.6302,-0.6781,-2.3092,-1.1658,-1.3185,-0.7561,,
```

### migros_inflation_YYYY-MM-DD.csv (first columns)

```csv
id,sku,name,brand,category,...,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Calculation Methodology

1. **Data Matching**: Products matched across dates using unique `id`
2. **Per-product Inflation**: `((current_price - past_price) / past_price) * 100`
3. **Basic Inflation**: Sum-based basket index using matched products only
4. **Average Inflation**: Mean of all valid per-product inflation rates
5. **TUIK Weighted**: Category-level averages weighted by normalised TUIK weights

## Configuration

The `tuik_config.py` file contains:

- TUIK 2026 CPI basket weights
- `migros_category_to_tuik()` mapping function
- `normalised_weights()` helper function

## Integration

Designed to run after daily Migros scraping completes:

1. Migros scraper saves data to `InflationItems/Datas/Markets/Migros/`
2. Run `python inflation.py` to calculate metrics
3. Results saved to `Inflations/Datas/Markets/Migros/`

## Error Handling

- Missing historical data → NaN values for affected intervals
- Invalid price data → Coerced to NaN and excluded from calculations
- Missing categories → Default to TUIK group 01 (food)
- Price changes of 0/0 → Handled gracefully, excluded from basket calculations
- Infinite inflation rates → Converted to NaN and excluded

## Dependencies

- Python 3.8+
- pandas
- Standard library: datetime, pathlib, logging
