# Rossmann Türkiye Product Scraper

A Python-based scraping tool that systematically extracts product data from
[rossmann.com.tr](https://www.rossmann.com.tr) through its public **Magento 2 GraphQL API**.

## Architecture Overview

The scraper operates through a modular architecture consisting of four core components:

- **`main.py`** – CLI interface and orchestration layer
- **`category_fetcher.py`** – Category discovery via GraphQL `categoryList`
- **`product_fetcher.py`** – Paginated product extraction via GraphQL `products`
- **`config.py`** – Centralised configuration (endpoint, headers, paths, top-level category IDs)

## Why GraphQL?

Rossmann is a Magento 2 store and exposes a public, unauthenticated GraphQL endpoint at
`https://www.rossmann.com.tr/graphql`. We use it directly instead of HTML parsing because:

- No browser automation, no Selenium / Playwright required
- A single endpoint handles category discovery, product listing, and pagination
- Native JSON output – no HTML / CSS selectors to maintain
- `pageSize` up to **500** keeps the request count low (~20 calls for the whole catalogue)
- Brand information is exposed as a clean `brand` string attribute

## Core Functionality

### Category Discovery

Uses a hard-coded list of 7 top-level navigation categories (Makyaj, Cilt Bakımı, Kişisel Bakım,
Anne & Bebek, Sağlık & Gıda, Temizlik, Ev & Yaşam) defined in `config.TOP_LEVEL_CATEGORIES`.
Each one is augmented at runtime with a live `total_count` probe.

> **Why hard-code top-level categories?** Rossmann's `categoryList` returns hundreds of
> entries that include campaign / brand buckets (e.g. "Flormar Sepet Kampanyası") whose
> products are strict subsets of the 7 navigation categories. Restricting to the 7 nav
> categories gives full coverage with no duplicate work.

### Data Extraction

- **API Integration**: POST `https://www.rossmann.com.tr/graphql` with a `products` query
- **Filter**: `category_id: {eq: "<id>"}`
- **Pagination**: `pageSize: 200`, advancing `currentPage` until `total_pages` is reached
- **Rate Limiting**: Configurable base delay with jitter (`0.5–1.5×` multiplier) between pages
- **Error Resilience**: Linear-backoff retry mechanism (`MAX_RETRIES = 3`)

### Output Management

- **Format**: CSV (UTF-8 with BOM) for Excel compatibility
- **Deduplication**: Cross-category duplicates removed in a final pass on `id`
- **Checkpoint System**: Daily JSON checkpoint enables `--resume` after interruption
- **Date-stamped Files**: Daily output organisation with `YYYY-MM-DD` naming

## Project Structure

```
InflationItems/Codes/Cosmetics/Rossmann/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers top-level categories via GraphQL
│   ├── product_fetcher.py   # Paginates GraphQL `products` queries
│   └── config.py            # All settings, paths, and API constants
├── checkpoints/
│   └── rossmann_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/Cosmetics/Rossmann/      ← scraped CSV output lives here
└── rossmann_<DATE>.csv

Inflations/Codes/Cosmetics/Rossmann/
├── inflation.py             # Inflation calculator triggered by main.py
├── tuik_config.py           # TUIK weights + Rossmann→TUIK category map
└── README.md

Inflations/Datas/Cosmetics/Rossmann/          ← inflation outputs live here
├── rossmann_inflation_<DATE>.csv
└── inflation_summary.csv
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Probes 7 top-level navigation categories via GraphQL
  │       (the IDs are hard-coded in config.TOP_LEVEL_CATEGORIES).
  │
  ├─ 2. (optional) filter by --category ID or url_key
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates GraphQL, retries, normalises product records.
  │               Each worker owns its own requests.Session.
  │               Results saved to disk after every completed category.
  │
  ├─ 5. Final deduplication pass  →  rossmann_<DATE>.csv
  │
  └─ 6. Trigger inflation.calculate_inflation()  (best-effort import)
```

## Data Schema

Each row in `rossmann_<DATE>.csv` represents one Rossmann product:

| Field           | Type   | Description                                                       |
| --------------- | ------ | ----------------------------------------------------------------- |
| `id`            | string | GraphQL UID (base64 of the Magento product id) – primary key      |
| `sku`           | string | SKU / internal article number                                     |
| `name`          | string | Product display name (Turkish)                                    |
| `brand`         | string | Magento `brand` custom attribute (falls back to first name token) |
| `category`      | string | Top-level navigation category being scraped                       |
| `regular_price` | float  | Regular shelf price (TRY)                                         |
| `shown_price`   | float  | Currently displayed price (TRY) after any discount                |
| `discount_rate` | float  | Discount percentage (0 when none)                                 |
| `unit`          | string | Empty for cosmetics – Magento does not expose a unit attribute    |
| `status`        | string | `IN_STOCK` / `OUT_OF_STOCK`                                       |
| `image_url`     | string | Product image URL                                                 |
| `product_url`   | string | Full product page URL                                             |

**Price source**: GraphQL returns prices already in TRY (no kuruş conversion needed).
We round to 2 decimal places.

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- A virtual environment is recommended

### Installation Steps

```bash
# Navigate to project root
cd InflationResearchStudy

# Create virtual environment (optional)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r InflationItems/Codes/Cosmetics/Rossmann/requirements.txt
```

### Dependencies

- `requests >= 2.31.0` – HTTP client for the GraphQL endpoint
- `pandas >= 2.0.0` – DataFrame handling and CSV export
- `tqdm >= 4.65.0` – Progress bar for category-level progress

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory so that
`import config`, `import category_fetcher`, etc. resolve correctly:

```bash
cd InflationItems/Codes/Cosmetics/Rossmann/scripts
```

### Command Line Interface

#### Category Discovery

```bash
# Display all top-level categories with live product counts
python main.py --list-categories
```

#### Targeted Scraping

```bash
# Scrape a single category by id (e.g. 6 = Sağlık & Gıda)
python main.py --category 6

# Scrape a single category by url_key
python main.py --category makyaj

# Scrape with a page limit (great for smoke tests)
python main.py --category makyaj --limit 1
```

#### Full Catalogue Extraction

```bash
# Complete scrape with default settings (3 workers)
python main.py

# Custom worker count (one worker per category for max parallelism)
python main.py --workers 7

# Adjust rate-limiting
python main.py --delay 1.0
```

#### Session Management

```bash
# Resume an interrupted run (skips categories already in the checkpoint)
python main.py --resume

# Verbose logging for debugging GraphQL responses
python main.py --category makyaj -v
```

### CLI Parameters

| Parameter           | Default         | Description                                          |
| ------------------- | --------------- | ---------------------------------------------------- |
| `--list-categories` | N/A             | Display category taxonomy (with counts) and exit     |
| `--category ID`     | All categories  | Scrape only this category id or url_key             |
| `--workers N`       | `3`             | Parallel thread count for category processing        |
| `--delay SECONDS`   | `0.5`           | Base delay between paginated requests (with jitter)  |
| `--limit PAGES`     | `0` (unlimited) | Maximum GraphQL pages per category (testing aid)     |
| `--resume`          | N/A             | Skip categories already listed in the checkpoint     |
| `-v, --verbose`     | N/A             | Enable debug-level logging                           |

### Output Files

| File Path                                                                            | Description                  |
| ------------------------------------------------------------------------------------ | ---------------------------- |
| `InflationItems/Datas/Cosmetics/Rossmann/rossmann_<DATE>.csv`                        | CSV dataset (UTF-8 with BOM) |
| `InflationItems/Codes/Cosmetics/Rossmann/checkpoints/rossmann_checkpoint_<DATE>.json` | Resume state tracking        |

File paths are automatically resolved relative to the script location, ensuring
consistent operation regardless of which directory you run the script from.

## Configuration Management

### Core Settings

Configuration parameters are centralised in `scripts/config.py`:

| Parameter         | Default       | Function                                            |
| ----------------- | ------------- | --------------------------------------------------- |
| `REQUEST_DELAY`   | `0.5` seconds | Base interval between page requests                 |
| `MAX_RETRIES`     | `3`           | Maximum retry attempts per failed GraphQL call      |
| `RETRY_BACKOFF`   | `2` seconds   | Linear backoff multiplier (wait = seed × attempt)   |
| `DEFAULT_WORKERS` | `3`           | Thread pool size for parallel category processing   |
| `JITTER_MIN`      | `0.5`         | Minimum delay multiplier (uniform random)           |
| `JITTER_MAX`      | `1.5`         | Maximum delay multiplier (uniform random)           |
| `PAGE_SIZE`       | `200`         | GraphQL `pageSize` per request (server max ≈ 500)   |

### Path Configuration

All file paths are computed relative to `config.py`:

- `OUTPUT_DIR`     → `InflationItems/Datas/Cosmetics/Rossmann/`
- `CHECKPOINT_DIR` → `InflationItems/Codes/Cosmetics/Rossmann/checkpoints/`

Daily file naming uses `YYYY-MM-DD`, so re-running on the same day with
`--resume` picks up exactly where the previous run stopped.

### API Configuration

- **Base URL**: `https://www.rossmann.com.tr`
- **GraphQL Endpoint**: `/graphql`
- **Required Headers**: standard browser headers + `Content-Type: application/json`
  and `Store: default`. No authentication / API key required.

## Category Taxonomy

The scraper systematically processes 7 top-level navigation categories:

| ID  | Name           | url_key       | Description                                 |
| --- | -------------- | ------------- | ------------------------------------------- |
| 3   | Makyaj         | makyaj        | Make-up                                     |
| 49  | Cilt Bakımı   | cilt-bakimi   | Skin care                                   |
| 4   | Kişisel Bakım | kisisel-bakim | Personal care (largest section)             |
| 5   | Anne & Bebek  | anne-bebek    | Mother & baby (mostly hygiene & toiletries) |
| 6   | Sağlık & Gıda | saglik-gida   | Health & food (vitamins, supplements, etc.) |
| 7   | Temizlik      | temizlik      | Household cleaning supplies                 |
| 8   | Ev & Yaşam    | ev-yasam      | Home & lifestyle goods                      |

Total: ~8,500 unique products as of 2026-04.

## Performance Notes

A full catalogue scrape typically completes in **30–40 seconds** with the default
3 workers (≈8,500 products across 7 categories, ~50 GraphQL requests total).
The bottleneck is GraphQL latency, not local processing.

## Error Handling & Troubleshooting

### Common Issues

| Symptom                    | Likely Cause                              | Resolution                                       |
| -------------------------- | ----------------------------------------- | ------------------------------------------------ |
| HTTP 403 Forbidden         | Rate limiting on the GraphQL endpoint     | Increase `--delay`; reduce `--workers`           |
| HTTP 429 Too Many Requests | Burst rate limit                          | Increase `--delay` (e.g. 1.0)                    |
| Empty output file          | API schema change (e.g. renamed field)    | Update the GraphQL document in `product_fetcher.py` |
| Resume failure             | Checkpoint date mismatch                  | Use today's checkpoint or delete it for a fresh run |
| `ModuleNotFoundError`      | Running from the wrong directory          | `cd` into `scripts/` first, or use `python -m`   |

### Debug Mode

Enable verbose logging with the `-v` flag for detailed GraphQL request / response info:

```bash
python main.py --category makyaj -v
```

## Technical Architecture

### Module Separation

The scraper follows a strict modular separation:

- **`config.py`** – Configuration constants and path management (no logic)
- **`category_fetcher.py`** – Stateless category discovery via GraphQL
- **`product_fetcher.py`** – Stateless product extraction and normalisation
- **`main.py`** – Orchestration, CLI handling, threading, persistence

### Concurrency Model

- Thread-based parallel processing with `ThreadPoolExecutor`
- One independent `requests.Session` per worker (no shared state)
- Three thread-safety locks: `_csv_lock`, `_checkpoint_lock`, `_counter_lock`
- Incremental CSV / checkpoint writes after each category completes
- Final deduplication pass across all collected products

### Data Flow

1. Fetch top-level categories from `config.TOP_LEVEL_CATEGORIES`
2. Parallel GraphQL extraction per category
3. Real-time JSON → flat record normalisation
4. Incremental CSV append + checkpoint write
5. Cross-category deduplication on `id`
6. Trigger inflation calculator (when present)

## Inflation Integration

After a successful scrape, `main.py` automatically calls
`inflation.calculate_inflation()` from
`Inflations/Codes/Cosmetics/Rossmann/inflation.py`. See the inflation calculator's
[README](../../../../Inflations/Codes/Cosmetics/Rossmann/README.md) for details.

If the inflation module cannot be imported (e.g. during local development of the
scraper alone), the scraper logs a warning and continues without failing.

---

**Technical Notice**: This tool is designed for research and data analysis
purposes. Users must comply with Rossmann's terms of service and any
applicable rate-limiting policies.
