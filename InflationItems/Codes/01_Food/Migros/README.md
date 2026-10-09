# Migros Türkiye Product Scraper

A Python-based web scraping tool that systematically extracts product data from [migros.com.tr](https://www.migros.com.tr) through direct integration with the site's REST API endpoints.

## Architecture Overview

The scraper operates through a modular architecture consisting of four core components:

- **`main.py`** - CLI interface and orchestration layer
- **`category_fetcher.py`** - Automated category discovery via API probing
- **`product_fetcher.py`** - Product data extraction and normalization
- **`config.py`** - Centralized configuration management

## Core Functionality

### Category Discovery

Automatically maps the complete product taxonomy by probing 13 top-level category IDs against the `/rest/products/search` endpoint. Extracts sub-category filters from `aggregationGroups[kategoriler].aggregationInfos` arrays, skipping empty categories (count == 0).

### Data Extraction

- **API Integration**: Direct REST API calls to `https://www.migros.com.tr/rest/products/search`
- **Pagination Handling**: Automatic navigation through all result pages per category
- **Rate Limiting**: Configurable delays with jitter (0.5-1.5x multiplier) to prevent detection
- **Error Resilience**: Exponential backoff retry mechanism (max 3 retries)

### Output Management

- **Format Option**: CSV (UTF-8 with BOM) output only
- **Deduplication**: Automatic removal of cross-category duplicate products
- **Checkpoint System**: Resume capability for interrupted scraping sessions
- **Date-stamped Files**: Daily output organization with YYYY-MM-DD naming

## Project Structure

```
InflationItems/Codes/Markets/Migros/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all scrapable (sub)categories via the REST API
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, and API constants
├── checkpoints/
│   └── migros_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/Markets/Migros/                   ← output lives here (outside Codes/)
├── migros_<DATE>.csv
└── InflationData/
    └── migros_inflation_<DATE>.csv

Inflations/Codes/Markets/Migros/
└── inflation.py             # Inflation calculation script triggered by main.py

Inflations/Datas/Markets/Migros/
└── inflation_summary.csv    # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Probes 13 top-level category IDs against the REST API
  │       and extracts sub-category filters from aggregationGroups.
  │
  ├─ 2. (optional) filter by --category ID
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Results saved to disk after every completed category.
  │
  └─ 5. Final deduplication pass  →  CSV output file
```

## Data Schema

The scraper extracts comprehensive product information with the following structure:

| Field           | Type   | Description                               |
| --------------- | ------ | ----------------------------------------- |
| `id`            | string | Unique product identifier from Migros API |
| `sku`           | string | Product SKU/barcode number                |
| `name`          | string | Product display name (Turkish)            |
| `brand`         | string | Manufacturer or brand name                |
| `category`      | string | Subcategory classification                |
| `regular_price` | float  | Standard retail price (TRY)               |
| `shown_price`   | float  | Current display price (TRY)               |
| `discount_rate` | float  | Discount percentage (0 when no promotion) |
| `unit`          | string | Unit of measurement (GRAM, PIECE, etc.)   |
| `status`        | string | Availability status (IN_SALE, etc.)       |
| `image_url`     | string | Product image URL                         |
| `product_url`   | string | Full product page URL                     |

**Price Processing**: API returns prices in kuruş (1/100 TRY). Values are converted to TRY and rounded to 2 decimal places.

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)

### Installation Steps

```bash
# Navigate to project root
cd InflationResearchStudy

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r InflationItems/Codes/Markets/Migros/requirements.txt
```

### Dependencies

- `requests>=2.31.0` - HTTP client for API calls
- `lxml>=5.1.0` - XML processing
- `tqdm>=4.66.0` - Progress bars
- `pandas>=2.2.0` - Data manipulation and CSV export

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory to ensure proper module resolution:

```bash
cd InflationItems/Codes/Markets/Migros/scripts
```

### Command Line Interface

#### Category Discovery

```bash
# Display all available categories with IDs
python main.py --list-categories
```

#### Targeted Scraping

```bash
# Scrape single category (ID 2 = Meyve, Sebze)
python main.py --category 2

# Scrape single category with page limit for testing
python main.py --category 2 --limit 2
```

#### Full Dataset Extraction

```bash
# Complete scrape with CSV output
python main.py

# Parallel processing with custom worker count
python main.py --workers 5

# Rate limiting adjustment
python main.py --delay 1.5
```

#### Session Management

```bash
# Resume interrupted scraping session
python main.py --resume

# Verbose logging for debugging
python main.py --category 2 -v
```

### CLI Parameters

| Parameter           | Default         | Description                                   |
| ------------------- | --------------- | --------------------------------------------- |
| `--list-categories` | N/A             | Display category taxonomy and exit            |
| `--category ID`     | All categories  | Limit scraping to specific category ID        |
| `--workers N`       | `3`             | Parallel thread count for category processing |
| `--delay SECONDS`   | `0.5`           | Base delay between requests (with jitter)     |
| `--limit PAGES`     | `0` (unlimited) | Maximum pages per category for testing        |
| `--resume`          | N/A             | Skip completed categories from checkpoint     |
| `-v, --verbose`     | N/A             | Enable debug-level logging                    |

### Output Files

| File Path                                                                       | Description                  |
| ------------------------------------------------------------------------------- | ---------------------------- |
| `InflationItems/Datas/Markets/Migros/migros_<DATE>.csv`                         | CSV dataset (UTF-8 with BOM) |
| `InflationItems/Codes/Markets/Migros/checkpoints/migros_checkpoint_<DATE>.json` | Resume state tracking        |

File paths are automatically resolved relative to the script location, ensuring consistent operation regardless of execution directory.

## Configuration Management

### Core Settings

Configuration parameters are centralized in `scripts/config.py`:

| Parameter         | Default       | Function                                   |
| ----------------- | ------------- | ------------------------------------------ |
| `REQUEST_DELAY`   | `0.5` seconds | Base interval between API requests         |
| `MAX_RETRIES`     | `3`           | Maximum retry attempts per failed request  |
| `RETRY_BACKOFF`   | `2` seconds   | Exponential backoff multiplier             |
| `DEFAULT_SORT`    | `onerilenler` | API sorting parameter                      |
| `DEFAULT_WORKERS` | `3`           | Thread pool size for parallel processing   |
| `JITTER_MIN`      | `0.5`         | Minimum delay multiplier for rate limiting |
| `JITTER_MAX`      | `1.5`         | Maximum delay multiplier for rate limiting |

### Path Configuration

All file paths are computed relative to the config file location:

- `OUTPUT_DIR`: Target directory for data exports
- `CHECKPOINT_DIR`: Location for session checkpoint files
- Daily file naming with YYYY-MM-DD format

### API Configuration

- **Base URL**: `https://www.migros.com.tr`
- **Endpoint**: `/rest/products/search`
- **Required Headers**: Custom `X-Device-PWA` and `X-FORWARDED-REST` for API authentication

## Category Taxonomy

The scraper systematically processes 13 top-level categories:

| ID  | Category                        | Description                      |
| --- | ------------------------------- | -------------------------------- |
| 2   | Meyve, Sebze                    | Fresh produce                    |
| 3   | Et, Tavuk, Balık                | Meat, poultry, fish              |
| 4   | Süt, Kahvaltılık                | Dairy, breakfast items           |
| 5   | Temel Gıda                      | Basic food staples               |
| 6   | İçecek                          | Beverages                        |
| 7   | Deterjan, Temizlik              | Cleaning supplies                |
| 8   | Kişisel Bakım, Kozmetik, Sağlık | Personal care, cosmetics, health |
| 9   | Bebek                           | Baby products                    |
| 10  | Ev, Yaşam                       | Home, lifestyle                  |
| 158 | Oyuncak                         | Toys                             |
| 160 | Evcil Hayvan                    | Pet supplies                     |
| 165 | Kitap, Dergi, Gazete            | Books, magazines, newspapers     |
| 166 | Elektronik                      | Electronics                      |

### Subcategory Discovery

For each top-level category, the scraper extracts subcategory filters from API response aggregation data. Categories with zero products are automatically excluded from processing.

## Error Handling & Troubleshooting

### Common Issues

| Symptom                    | Cause                            | Resolution                                           |
| -------------------------- | -------------------------------- | ---------------------------------------------------- |
| HTTP 403 Forbidden         | Rate limiting or missing headers | Increase `--delay`; verify API headers in config     |
| HTTP 429 Too Many Requests | Rate limit exceeded              | Increase delay interval; reduce worker count         |
| Empty output files         | API structure changes            | Verify `storeProductInfos` key in product_fetcher.py |
| Resume failure             | Mismatched checkpoint date       | Use current day's checkpoint or clear checkpoint     |
| Module import errors       | Incorrect execution directory    | Run from `scripts/` directory                        |

### Debug Mode

Enable verbose logging with `-v` flag for detailed execution information:

```bash
python main.py --category 2 -v
```

## Technical Architecture

### Module Separation

The scraper follows a modular design pattern:

- **`config.py`** - Configuration constants and path management
- **`category_fetcher.py`** - Stateless category discovery via API
- **`product_fetcher.py`** - Stateless product extraction and normalization
- **`main.py`** - Orchestration, CLI handling, and session management

### Concurrency Model

- Thread-based parallel processing with `ThreadPoolExecutor`
- Independent `requests.Session` per thread
- Incremental checkpoint writing after category completion
- Final deduplication pass across all collected products

### Data Flow

1. Category discovery via API probing
2. Parallel product extraction per category
3. Real-time data validation and normalization
4. Incremental file writing and checkpointing
5. Cross-category deduplication
6. Final dataset export

---

**Technical Notice**: This tool is designed for research and data analysis purposes. Users must comply with applicable terms of service and rate limiting policies.
