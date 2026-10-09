# Samsung Türkiye Product Scraper

A Python-based scraping tool that systematically extracts product data
from [samsung.com/tr](https://www.samsung.com/tr) through its public
**Product Finder v2 (`pfv2`) JSON API**.

## Architecture Overview

The scraper operates through a modular architecture consisting of four
core components:

- **`main.py`** – CLI interface and orchestration layer
- **`category_fetcher.py`** – Category discovery + live total-record probe
- **`product_fetcher.py`** – Paginated SKU extraction via `pfv2`
- **`config.py`** – Centralised configuration (endpoint, headers, paths,
  curated top-level categories + TUIK group codes)

## Why a JSON API?

Samsung Türkiye's product listing pages are powered by AEM + Hybris and
the Product Finder v2 widget (`pfv2`) populates each "all-*" category
grid by calling a public JSON endpoint on `searchapi.samsung.com`.
We call that endpoint directly instead of parsing HTML because:

- No browser automation, no Selenium / Playwright required
- A single endpoint handles every top-level category via the 8-digit
  `pfCategoryTypeCode` parameter
- Native JSON output – no HTML / CSS selectors to maintain
- Server-side `num` page size up to ~500 keeps the request count low
  (every Samsung Türkiye category finishes in ≤ 2 requests as of
  2026-05)
- Model-level metadata (listPrice, promo price, stock status, images,
  PDP URL, family, sub-category) is all exposed directly

## Core Functionality

### Category Discovery

Uses a hard-coded list of 20 top-level navigation categories spanning
Samsung's Turkish catalogue, defined in `config.TOP_LEVEL_CATEGORIES`.
Each entry carries:

- The slug `id` (e.g. `smartphones`)
- The 8-digit `pfCategoryTypeCode` (e.g. `01010000`)
- A display `name` (e.g. `Smartphones`)
- The `landing_path` of the public "all-*" page (for reference)

At runtime each entry is augmented with a live `product_count` probe
from the `pfv2` endpoint (a cheap `num=1` request just to read back
`totalRecord`).

> **Why hard-code top-level categories?** Samsung's nav tree exposes
> dozens of sub-category and campaign pages whose products are strict
> subsets of the "all-*" pages.  Restricting to the 20 curated
> top-level categories gives full SKU coverage with no duplicate work.

### Data Extraction

- **API Endpoint**: `GET https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris`
- **Query Params**: `type=<8-digit>`, `siteCode=tr`, `start`, `num`,
  `sort=newest`, `onlyFilterInfoYN=N`
- **Pagination**: 1-indexed `start`, page size `num=200` (tested-safe
  upper bound ~500; `num ≥ 1000` returns `resultData: null`)
- **Rate Limiting**: Configurable base delay with jitter
  (`0.5–1.5×` multiplier) between pages
- **Error Resilience**: Linear-backoff retry mechanism
  (`MAX_RETRIES = 4`)
- **Families → SKUs**: each family (`Galaxy S25`) carries a
  `modelList` of real SKUs (colour / capacity variants); we flatten
  that into a SKU-level CSV

### Output Management

- **Format**: CSV (UTF-8 with BOM) for Excel compatibility
- **Deduplication**: Cross-category duplicates removed in a final
  pass on `id` (Samsung occasionally cross-lists e.g. a Buds case in
  both `mobile-accessories` and `audio-sound`)
- **Checkpoint System**: Daily JSON checkpoint enables `--resume`
  after interruption
- **Date-stamped Files**: Daily output organisation with `YYYY-MM-DD`
  naming

## Project Structure

```
InflationItems/Codes/TechnologicalProducts/Samsung/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers top-level categories
│   ├── product_fetcher.py   # Paginates pfv2 product queries
│   └── config.py            # All settings, paths, API constants
├── checkpoints/
│   └── samsung_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/TechnologicalProducts/Samsung/      ← scraped CSV output
└── samsung_<DATE>.csv

Inflations/Codes/TechnologicalProducts/Samsung/
├── inflation.py             # Inflation calculator triggered by main.py
├── tuik_config.py           # TUIK weights + Samsung→TUIK category map
└── README.md

Inflations/Datas/TechnologicalProducts/Samsung/          ← inflation outputs
├── samsung_inflation_<DATE>.csv
└── inflation_summary.csv
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Probes every top-level category via pfv2 (the IDs are
  │       hard-coded in config.TOP_LEVEL_CATEGORIES).
  │
  ├─ 2. (optional) filter by --category slug, type code or name
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates pfv2, retries, flattens family→modelList,
  │               normalises each SKU record.
  │               Each worker owns its own requests.Session.
  │               Results saved to disk after every completed category.
  │
  ├─ 5. Final deduplication pass  →  samsung_<DATE>.csv
  │
  └─ 6. Trigger inflation.calculate_inflation()  (best-effort import)
```

## Data Schema

Each row in `samsung_<DATE>.csv` represents one Samsung SKU:

| Field           | Type   | Description                                                        |
| --------------- | ------ | ------------------------------------------------------------------ |
| `id`            | string | Samsung modelCode (e.g. `SM-S931BLGGTUR`) – primary key            |
| `sku`           | string | Same as `id` – `shopSKU` / `modelCode` are identical for Samsung   |
| `name`          | string | Product display name (Turkish) – `displayName` or family fallback  |
| `brand`         | string | Always `"Samsung"`                                                 |
| `category`      | string | Top-level category being scraped (e.g. `Smartphones`, `TVs`)       |
| `sub_category`  | string | `categorySubTypeName` (e.g. `Galaxy S`, `Bespoke AI`)              |
| `family`        | string | `fmyMarketingName` (e.g. `Galaxy S25 Ultra`)                       |
| `regular_price` | float  | `listPrice` or `lowestWasPrice` (falls back to `shown_price`)      |
| `shown_price`   | float  | `price` (what the customer actually pays after promos)             |
| `discount_rate` | float  | Derived percent off, clamped at 0                                  |
| `unit`          | string | Always `"PIECE"` – Samsung is a durable-goods retailer             |
| `status`        | string | `IN_STOCK` / `OUT_OF_STOCK` / `COMING_SOON` / `PRE_ORDER` / …       |
| `image_url`     | string | Product thumbnail URL                                              |
| `product_url`   | string | Full PDP URL on samsung.com/tr                                     |

**Price source**: the `pfv2` endpoint returns prices already in TRY
(native JSON numbers, no kuruş conversion). We round to 2 decimals.

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
pip install -r InflationItems/Codes/TechnologicalProducts/Samsung/requirements.txt
```

### Dependencies

- `requests >= 2.31.0` – HTTP client for the `pfv2` endpoint
- `pandas >= 2.0.0` – DataFrame handling and CSV export
- `tqdm >= 4.65.0` – Progress bar for category-level progress

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory so that
`import config`, `import category_fetcher`, etc. resolve correctly:

```bash
cd InflationItems/Codes/TechnologicalProducts/Samsung/scripts
```

### Command Line Interface

#### Category Discovery

```bash
# Display all top-level categories with live family counts
python main.py --list-categories
```

#### Targeted Scraping

```bash
# Scrape a single category by slug
python main.py --category smartphones

# Or by 8-digit type code
python main.py --category 01010000

# Or by display name (case-insensitive)
python main.py --category "Mobile Accessories"

# Smoke test: limit to 1 page per category
python main.py --category smartphones --limit 1
```

#### Full Catalogue Extraction

```bash
# Complete scrape with default settings (3 workers)
python main.py

# Custom worker count
python main.py --workers 6

# Adjust rate-limiting (seconds between pfv2 pages)
python main.py --delay 1.0
```

#### Session Management

```bash
# Resume an interrupted run (skips categories in the checkpoint)
python main.py --resume

# Verbose logging for debugging API responses
python main.py --category watches -v
```

### CLI Parameters

| Parameter           | Default         | Description                                          |
| ------------------- | --------------- | ---------------------------------------------------- |
| `--list-categories` | N/A             | Display category taxonomy (with counts) and exit     |
| `--category ID`     | All categories  | Scrape only this category (slug / type / name)       |
| `--workers N`       | `3`             | Parallel thread count for category processing        |
| `--delay SECONDS`   | `0.5`           | Base delay between paginated requests (with jitter)  |
| `--limit PAGES`     | `0` (unlimited) | Maximum pages per category (testing aid)             |
| `--resume`          | N/A             | Skip categories already listed in the checkpoint     |
| `-v, --verbose`     | N/A             | Enable debug-level logging                           |

### Output Files

| File Path                                                                                      | Description                  |
| ---------------------------------------------------------------------------------------------- | ---------------------------- |
| `InflationItems/Datas/TechnologicalProducts/Samsung/samsung_<DATE>.csv`                        | CSV dataset (UTF-8 with BOM) |
| `InflationItems/Codes/TechnologicalProducts/Samsung/checkpoints/samsung_checkpoint_<DATE>.json` | Resume state tracking        |

File paths are automatically resolved relative to the script location,
ensuring consistent operation regardless of which directory you run
the script from.

## Configuration Management

### Core Settings

Configuration parameters are centralised in `scripts/config.py`:

| Parameter         | Default       | Function                                            |
| ----------------- | ------------- | --------------------------------------------------- |
| `REQUEST_DELAY`   | `0.5` seconds | Base interval between page requests                 |
| `MAX_RETRIES`     | `4`           | Maximum retry attempts per failed API call          |
| `RETRY_BACKOFF`   | `2` seconds   | Linear backoff multiplier (wait = seed × attempt)   |
| `DEFAULT_WORKERS` | `3`           | Thread pool size for parallel category processing   |
| `JITTER_MIN`      | `0.5`         | Minimum delay multiplier (uniform random)           |
| `JITTER_MAX`      | `1.5`         | Maximum delay multiplier (uniform random)           |
| `PAGE_SIZE`       | `200`         | `num` parameter per request (tested max ~500)       |
| `DEFAULT_SORT`    | `"newest"`    | `sort` parameter (matches Samsung's default)        |

### Path Configuration

All file paths are computed relative to `config.py`:

- `OUTPUT_DIR`     → `InflationItems/Datas/TechnologicalProducts/Samsung/`
- `CHECKPOINT_DIR` → `InflationItems/Codes/TechnologicalProducts/Samsung/checkpoints/`

Daily file naming uses `YYYY-MM-DD`, so re-running on the same day
with `--resume` picks up exactly where the previous run stopped.

### API Configuration

- **Base URL**: `https://www.samsung.com`
- **Product Finder Endpoint**:
  `https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris`
- **Required Headers**: standard browser headers + `X-Requested-With:
  XMLHttpRequest` and a `Referer: https://www.samsung.com/tr/`.
  No authentication / API key required.

## Category Taxonomy

The scraper systematically processes 20 top-level categories across
three TUIK CPI main groups (05, 08, 09):

| Type Code  | Slug                 | Name                 | TUIK |
| ---------- | -------------------- | -------------------- | ---- |
| `01010000` | `smartphones`        | Smartphones          | 08   |
| `01020000` | `tablets`            | Tablets              | 08   |
| `01030000` | `watches`            | Watches              | 08   |
| `01040000` | `audio-sound`        | Audio Sound          | 09   |
| `01050000` | `mobile-accessories` | Mobile Accessories   | 08   |
| `01090000` | `rings`              | Rings                | 08   |
| `04010000` | `tvs`                | TVs                  | 09   |
| `04030000` | `tv-accessories`     | TV Accessories       | 09   |
| `04050000` | `projectors`         | Projectors           | 09   |
| `05010000` | `audio-devices`      | Audio Devices        | 09   |
| `07010000` | `monitors`           | Monitors             | 08   |
| `08010000` | `washers-and-dryers` | Washers & Dryers     | 05   |
| `08030000` | `refrigerators`      | Refrigerators        | 05   |
| `08040000` | `air-care`           | Air Purifier         | 05   |
| `08050000` | `air-conditioners`   | Air Conditioners     | 05   |
| `08070000` | `vacuum-cleaners`    | Vacuum Cleaners      | 05   |
| `08080000` | `cooking-appliances` | Cooking Appliances   | 05   |
| `08090000` | `dishwashers`        | Dishwashers          | 05   |
| `08110000` | `microwave-ovens`    | Microwave Ovens      | 05   |
| `09010000` | `memory-storage`     | Memory & Storage     | 08   |

Total: ~500 product families (≈1.5–3× as many SKUs) as of 2026-05.

## Performance Notes

A full catalogue scrape typically completes in **under a minute** with
the default 3 workers.  Most categories finish in a single `pfv2`
request (≤ 200 families); the bottleneck is network latency, not
local processing.

## Error Handling & Troubleshooting

### Common Issues

| Symptom                    | Likely Cause                              | Resolution                                          |
| -------------------------- | ----------------------------------------- | --------------------------------------------------- |
| HTTP 403 Forbidden         | Rate limiting on `searchapi.samsung.com`  | Increase `--delay`; reduce `--workers`              |
| `resultData: null`         | `num ≥ 1000` triggers an API-side cap     | Lower `config.PAGE_SIZE` (default 200 is safe)      |
| Empty output file          | API schema change (renamed field)         | Update the parser in `product_fetcher._parse_model` |
| Resume failure             | Checkpoint date mismatch                  | Use today's checkpoint or delete it for a fresh run |
| `ModuleNotFoundError`      | Running from the wrong directory          | `cd` into `scripts/` first                          |

### Debug Mode

Enable verbose logging with the `-v` flag to see every pfv2 request
and response size:

```bash
python main.py --category smartphones -v
```

## Technical Architecture

### Module Separation

The scraper follows a strict modular separation:

- **`config.py`** – Configuration constants and path management
- **`category_fetcher.py`** – Stateless category discovery + probe
- **`product_fetcher.py`** – Stateless SKU extraction and normalisation
- **`main.py`** – Orchestration, CLI handling, threading, persistence

### Concurrency Model

- Thread-based parallel processing with `ThreadPoolExecutor`
- One independent `requests.Session` per worker (no shared state)
- Three thread-safety locks: `_csv_lock`, `_checkpoint_lock`,
  `_counter_lock`
- Incremental CSV / checkpoint writes after each category completes
- Final deduplication pass across all collected SKUs

### Data Flow

1. Fetch top-level categories from `config.TOP_LEVEL_CATEGORIES`
2. Parallel pfv2 extraction per category (paginated on `start`)
3. Real-time family → `modelList` flattening + normalisation
4. Incremental CSV append + checkpoint write
5. Cross-category deduplication on `id`
6. Trigger inflation calculator (when present)

## Inflation Integration

After a successful scrape, `main.py` automatically calls
`inflation.calculate_inflation()` from
`Inflations/Codes/TechnologicalProducts/Samsung/inflation.py`.  See
the inflation calculator's
[README](../../../../Inflations/Codes/TechnologicalProducts/Samsung/README.md)
for details.

If the inflation module cannot be imported (e.g. during local
development of the scraper alone), the scraper logs a warning and
continues without failing.

---

**Technical Notice**: This tool is designed for research and data
analysis purposes. Users must comply with Samsung's terms of service
and any applicable rate-limiting policies.
