# Bershka Türkiye Product Scraper

A Python tool to scrape all product data from [bershka.com/tr](https://www.bershka.com/tr/) and save it as CSV.

## Features

- 🗂️ Discovers **all leaf categories** automatically via the Inditex REST API.
- 🔀 **Parallel scraping** with a configurable number of worker threads (`--workers`).
- 💾 Output as **CSV**, named with today's date.
- ♻️ **Resume support** — restart an interrupted run without re-scraping completed categories.
- ⏱️ Configurable **rate limiting** with per-request jitter and User-Agent rotation.
- 🔄 Automatic **retry** with exponential back-off on failed or timeout requests.
- 🧹 Final **deduplication** pass removes any cross-category duplicate products.
- 📈 **Inflation calculation** — compares prices against historical data (1/7/15/30 days).

## Project Structure

```
Codes/ClothingStores/Bershka/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all categories from the Inditex API
│   ├── product_fetcher.py   # Fetches product details per category (batch API)
│   ├── inflation.py         # Calculates inflation from historical data
│   └── config.py            # All settings, paths, headers, and API constants
├── checkpoints/
│   └── bershka_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

Datas/ClothingStores/Bershka/          ← output lives here (outside Codes/)
├── ProductData/
│   └── bershka_<DATE>.csv
└── InflationData/
    ├── bershka_inflation_<DATE>.csv
    └── inflation_summary.csv
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Calls the Inditex REST API to discover the full category tree.
  │       Walks recursively and returns only leaf categories.
  │
  ├─ 2. (optional) filter by --category ID
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category()  →  fetch_products_for_category()
  │               Two-step: get product IDs → batch fetch details.
  │               Results saved to disk after every completed category.
  │
  ├─ 5. Final deduplication pass  →  CSV output file
  │
  └─ 6. Inflation calculation
```

## Output Fields

| Field           | Type   | Description                                                   |
| --------------- | ------ | ------------------------------------------------------------- |
| `product_id`    | string | Bershka internal product ID                                   |
| `name`          | string | Full product name                                             |
| `brand`         | string | Brand name (always `Bershka`)                                 |
| `category`      | string | Category path (e.g. `Giyim > Pantolon`)                       |
| `color`         | string | Colour variant                                                |
| `regular_price` | float  | Original price (TRY)                                          |
| `sale_price`    | float  | Discounted price (TRY); equals `regular_price` if no discount |
| `discount_pct`  | float  | Discount percentage (0 if none)                               |
| `currency`      | string | Currency (always `TRY`)                                       |

## Setup

```bash
# 1. Go to the project root
cd InflationResearchStudy

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r Codes/ClothingStores/Bershka/requirements.txt
```

## Usage

Run all commands from inside the `scripts/` directory:

```bash
cd Codes/ClothingStores/Bershka/scripts

# List all discovered categories
python main.py --list-categories

# Scrape a single category — quick test
python main.py --category <CATEGORY_ID>

# Scrape ALL categories with 2 parallel workers
python main.py --workers 2

# Resume an interrupted run
python main.py --resume

# Verbose debug logging
python main.py -v
```

### CLI Reference

| Argument            | Default            | Description                                                           |
| ------------------- | ------------------ | --------------------------------------------------------------------- |
| `--list-categories` | —                  | Print all discovered categories with their IDs and exit.              |
| `--category ID`     | _(all categories)_ | Scrape only the specified category ID.                                |
| `--workers N`       | `1`                | Number of parallel category worker threads.                           |
| `--delay SECONDS`   | `2.0`              | Base delay between requests per worker.                               |
| `--resume`          | —                  | Skip categories already recorded in the checkpoint file.              |
| `-v` / `--verbose`  | —                  | Enable DEBUG-level logging.                                           |

## Troubleshooting

| Symptom                    | Likely cause             | Fix                                                         |
| -------------------------- | ------------------------ | ------------------------------------------------------------ |
| HTTP 403 Forbidden         | Rate limited / blocked   | Increase `--delay` or reduce `--workers`                     |
| HTTP 429 Too Many Requests | Rate limit triggered     | Auto-backed-off via `RATE_LIMIT_BACKOFF` (60s)               |
| Empty CSV after full run   | API structure changed    | Check Inditex itxrest API response format                    |
| Resume doesn't skip cats   | Checkpoint from diff day | Delete old checkpoint or use `--resume` on same day          |

---

> **Disclaimer**: This tool is for educational / research purposes. Always respect `robots.txt` and the site's Terms of Service.
