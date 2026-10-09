# Vivense Inflation Calculator

Computes daily inflation metrics for the Vivense product catalogue scraped by
`InflationItems/Codes/HomeGoods/Vivense/scripts/main.py`.

## Metrics

| Metric                  | Description                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `basic_inflation_<lbl>` | Per-product percentage price change relative to the comparison date         |
| `avg_inflation_<lbl>`   | Arithmetic mean of all per-product inflation rates                          |
| `tuik_weighted_<lbl>`   | TUIK 2026 CPI-weighted average across the TUIK groups present in the data  |

Standard interval labels: `1d`, `7d`, `15d`, `30d`. Custom comparisons supported
via the `--compare` flag.

## Inputs / Outputs

```
InflationItems/Datas/HomeGoods/Vivense/vivense_<DATE>.csv         (input)
        ↓
Inflations/Codes/HomeGoods/Vivense/inflation.py
        ↓
Inflations/Datas/HomeGoods/Vivense/vivense_inflation_<DATE>.csv   (per-product)
Inflations/Datas/HomeGoods/Vivense/inflation_summary.csv          (store-level, append-only)
```

The calculator joins datasets on the `id` column and uses `shown_price` as the
authoritative current-price value.

## TUIK Mapping

Vivense is a furniture / home-goods retailer, so every top-level category maps
to TUIK group **05** (*Mobilya, ev aletleri ve ev bakım hizmetleri*, weight
7.92 % in the 2026 basket).  See `tuik_config.py` for the full mapping.

## Usage

```bash
# Standard daily run (uses today's date and the four standard intervals)
python inflation.py

# Specific target date
python inflation.py --date 2026-04-29

# Arbitrary two-date comparison
python inflation.py --date 2026-04-29 --compare 2026-04-22
```

The scraper's `main.py` invokes `calculate_inflation()` automatically after a
successful run, so this script normally does not need to be invoked manually.
