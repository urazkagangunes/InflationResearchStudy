# Rossmann Inflation Calculator

Calculates inflation metrics for Rossmann Türkiye drug-store / cosmetics products
using TUIK 2026 CPI basket weights.

## Overview

Computes three inflation metrics for Rossmann products:

1. **Basic Inflation**       – Basket-level price index change (%) calculated as
   sum of current prices vs sum of past prices
2. **Average Inflation**     – Arithmetic mean of all per-product percentage
   price changes
3. **TUIK Weighted Average** – Weighted average using TUIK 2026 CPI basket
   weights, normalised to the categories present

The calculator runs for four standard intervals (1d, 7d, 15d, 30d) by default
and additionally supports an arbitrary `--compare` date.

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/Cosmetics/Rossmann/rossmann_YYYY-MM-DD.csv`
- **Required columns**: `id`, `shown_price`, `category`

### Key Columns

- `id` – GraphQL UID, used to match the same product across dates
- `shown_price` – Displayed price after any discount (numeric, TRY)
- `category` – Top-level navigation category, mapped to TUIK groups

## TUIK Category Mapping

Maps Rossmann's 7 navigation categories to **3 TUIK groups**:

| Rossmann Category | TUIK Group | TUIK Description                            | Weight |
| ----------------- | ---------- | ------------------------------------------- | ------ |
| Makyaj            | 12         | Kişisel bakım, sosyal koruma ve diğer       | 4.49%  |
| Cilt Bakımı      | 12         | Kişisel bakım, sosyal koruma ve diğer       | 4.49%  |
| Kişisel Bakım    | 12         | Kişisel bakım, sosyal koruma ve diğer       | 4.49%  |
| Anne & Bebek     | 12         | Kişisel bakım, sosyal koruma ve diğer       | 4.49%  |
| Sağlık & Gıda    | 06         | Sağlık                                       | 2.79%  |
| Temizlik          | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri | 7.92%  |
| Ev & Yaşam       | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri | 7.92%  |

> **Why these groupings?**
> - The four cosmetics-leaning categories all map to TUIK 12 (Personal care).
> - "Sağlık & Gıda" is dominated by vitamins / supplements / OTC items, so it
>   maps to TUIK 06 (Health) rather than TUIK 01 (Food).
> - "Temizlik" and "Ev & Yaşam" are household-maintenance goods, mapped to
>   TUIK 05 (Furnishings & household appliances) – consistent with how the
>   Bauhaus calculator treats home / cleaning items.

### A Note on TUIK Code Labelling

This file follows the **same code labels used by every other per-store
calculator in this repository** (Migros, Bauhaus, …):

```
"12" → Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler   (4.49%)
"13" → Sigorta ve finansal hizmetler                              (1.07%)
```

The numerical weights themselves match the TÜİK 2026 publication
(2025 = 100 base). Only the code labels differ from the very latest
COICOP-2018 ordering, but since every per-store calculator uses the same
labelling, downstream tools (`CrossStore_Compare.py`, `inflation_engine.py`)
can compare Rossmann outputs against Migros / Bauhaus / etc. without any
translation step. **The important guarantee is that "Personal care"
products consistently get the 4.49% weight, never 1.07%.**

## Usage

```bash
# Calculate today's inflation
python inflation.py

# Calculate for a specific date (uses today's date if omitted)
python inflation.py --date 2026-04-25

# Compare two arbitrary dates
python inflation.py --date 2026-04-25 --compare 2026-04-18
```

The calculator is also invoked automatically at the end of every successful
scraper run (`InflationItems/Codes/Cosmetics/Rossmann/scripts/main.py`).

## Output Files

### Detailed Data

`rossmann_inflation_YYYY-MM-DD.csv`

- All original columns from the daily scraper CSV plus:
  - `tuik_category` – TUIK 2-digit group code for each product
  - `basic_inflation_1d` / `_7d` / `_15d` / `_30d` – per-product %change
- Location: `Inflations/Datas/Cosmetics/Rossmann/`

### Summary Data

`inflation_summary.csv`

- One row per `date`
- Columns: `date`, `avg_inflation_1d`, `tuik_weighted_1d`, … (×4 intervals)
- Append-only: rerunning for the same date overwrites that single row
- Location: `Inflations/Datas/Cosmetics/Rossmann/`

### Example Output

#### `inflation_summary.csv`

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-04-25,9.0850,5.5592,,,,,,
```

#### `rossmann_inflation_YYYY-MM-DD.csv` (column overview)

```csv
id,sku,name,brand,category,...,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Calculation Methodology

1. **Data matching**: Products matched across dates using the unique `id`
   column (Magento UID, base64-encoded).
2. **Per-product inflation**: `((current_price − past_price) / past_price) × 100`
3. **Basic inflation (basket index)**: Sum-based price-index change using
   only products that exist on both dates.
4. **Average inflation**: Arithmetic mean of all valid per-product inflation
   rates (NaN for products that disappeared between dates).
5. **TUIK weighted**: Per-`tuik_category` mean inflation, then a weighted
   average using `normalised_weights({categories present})` so the weights
   sum to 100% across only the groups actually present in the data.

### Why TUIK Weighted ≠ Average

For Rossmann specifically the two metrics often differ noticeably because
the TUIK weights treat one TRY of cleaning supplies (TUIK 05 – 7.92%
basket weight) very differently from one TRY of cosmetics (TUIK 12 – 4.49%):
the weighted result reflects how an *average Turkish household* spends,
not how a Rossmann customer spends.

## Configuration

`tuik_config.py` exposes:

- `TUIK_WEIGHTS` – dict of 13 TUIK 2026 main-group weights
- `rossmann_category_to_tuik(name)` – maps a Rossmann navigation category
  to its TUIK 2-digit code
- `normalised_weights(present_codes)` – rescales weights so the present
  codes sum to 100

To adjust the mapping (e.g. moving "Anne & Bebek" out of Personal care into
Health), edit `_ROSSMANN_TUIK_MAP` in `tuik_config.py` – no other code
changes are required.

## Integration

Designed to run after each daily Rossmann scraper run:

1. The scraper saves data to `InflationItems/Datas/Cosmetics/Rossmann/`.
2. `main.py` automatically calls `inflation.calculate_inflation()` at the
   end of a successful scrape.
3. Results land in `Inflations/Datas/Cosmetics/Rossmann/`.

The inflation module can also run standalone: `python inflation.py [--date …]`.

## Error Handling

- **Missing historical data** → NaN values for the affected interval(s)
- **Invalid price data** → Coerced to NaN and excluded from calculations
- **Unknown categories** → Default to TUIK group 12 (Personal care),
  the dominant group for a drug-store catalogue
- **Price changes of 0/0** → Handled gracefully, excluded from basket calc
- **Infinite inflation rates** (price went from 0 to non-zero) → Converted
  to NaN and excluded

## Dependencies

- Python 3.8+
- `pandas`
- Standard library: `argparse`, `datetime`, `pathlib`, `logging`, `sys`

No additional install is required if the scraper's `requirements.txt` is
already installed.

## File Layout

```
Inflations/Codes/Cosmetics/Rossmann/
├── inflation.py       # Daily calculator (also importable from main.py)
├── tuik_config.py     # TUIK weights + Rossmann→TUIK category mapping
└── README.md          # this file

Inflations/Datas/Cosmetics/Rossmann/
├── rossmann_inflation_<DATE>.csv   # daily per-product detail
└── inflation_summary.csv           # store-level summary, append-only
```
