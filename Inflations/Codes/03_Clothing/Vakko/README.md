# Vakko Inflation Calculator

This tool calculates daily, weekly, and monthly inflation metrics for Vakko luxury fashion products using TUIK 2026 CPI (Consumer Price Index) basket weights.

## Overview

Computes three key inflation metrics for Vakko products across standard intervals (1d, 7d, 15d, 30d):

1. **Basic Inflation**: Basket-level price index change (%).
2. **Average Inflation**: Arithmetic mean of all per-product percentage price changes.
3. **TUIK Weighted Average**: Weighted average using TUIK 2026 CPI basket weights, normalised to the categories present in the current dataset.

## Directory Structure & Paths

- **Input Data**: `C:\Users\arhan\PycharmProjects\inflationstudymirror\Datas\ClothingStores\Vakko\`
- **Output Data**: `C:\Users\arhan\PycharmProjects\inflationstudymirror\Inflations\Datas\Markets\ClothingStores\Vakko\`
- **Scripts**: `C:\Users\arhan\PycharmProjects\inflationstudymirror\Inflations\Codes\ClothingStores\Vakko\`

## Data Requirements

The input CSV files must be named in the `vakko_YYYY-MM-DD.csv` format and contain the following required columns:

- `Stok Kodu`: Unique product identifier for matching across dates.
- `Fiyat`: Current sale price (the script automatically cleans '₺', thousand separators, and decimal commas).
- `Ürün Adı`: Product name used for TUIK category classification.

## TUIK Category Mapping (`vakko_tuik_config.py`)

Products are mapped to TUIK 2026 groups by analyzing the `Ürün Adı` (Product Name) column:

| Keyword Pattern in `Ürün Adı`        | TUIK Group | Description                                              |
| ------------------------------------ | ---------- | -------------------------------------------------------- |
| PARFÜM, KOZMETİK, PERFUME, COSMETICS | 12         | Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler |
| All other products                   | 03         | Giyim ve ayakkabı                                        |

## Usage

Navigate to the script directory before running the commands to ensure local imports (`vakko_tuik_config.py`) work correctly.

```powershell
cd "C:\Users\arhan\PycharmProjects\inflationstudymirror\Inflations\Codes\ClothingStores\Vakko"
```
Single Date Calculation

Calculate inflation for a specific date against standard past intervals (1d, 7d, 15d, 30d):
PowerShell

python vakko_inflation.py --date 2026-03-27

Custom Date Comparison

Compare two specific dates:
PowerShell
```
python vakko_inflation.py --date 2026-03-27 --compare 2026-03-10
```
Batch Processing (PowerShell)

To process all available daily CSVs in your data folder at once, run this loop in PowerShell:
PowerShell
```
Get-ChildItem -Path "C:\Users\arhan\PycharmProjects\inflationstudymirror\Datas\ClothingStores\Vakko\vakko_*.csv" | ForEach-Object { python "vakko_inflation.py" --date $_.BaseName.Replace('vakko_', '') }
```
Output Files

  Detailed Data (vakko_inflation_YYYY-MM-DD.csv)

  Contains per-product inflation data with percentage price changes for each calculated interval.

  Saves a separate file for every target date processed.

  Summary Data (inflation_summary.csv)

  Store-level metrics tracking overall inflation.

  Contains columns: date, avg_inflation_{interval}, tuik_weighted_{interval}.

  Appends new data for each processed date automatically. If a date is re-processed, its existing row is updated.

Error Handling

  Missing Historical Data: Intervals without past data yield <null> or empty values.

  Price Changes of 0/0: Gracefully handled and mathematically neutral.

  Infinite Inflation Rates: Converted to NaN (pd.NA) to prevent calculation crashes.
