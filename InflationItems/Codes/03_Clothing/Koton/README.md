# Koton Türkiye Product Scraper

A Python-based web scraping system that systematically extracts product data from [koton.com](https://www.koton.com) through HTML parsing and XML sitemap analysis.

## Architecture Overview

The scraper implements a modular architecture with four core components:

- **`main.py`** - CLI interface and orchestration controller
- **`category_fetcher.py`** - XML sitemap-based category discovery
- **`product_fetcher.py`** - HTML parsing and product data extraction
- **`config.py`** - Centralized configuration and constants management

## Core Functionality

### Category Discovery

Automatically maps the complete product catalog by downloading and parsing the compressed XML sitemap (`sitemap-categories-1.xml.gz`). Extracts all unique category slugs, currently identifying 311+ categories across the product taxonomy.

### Data Extraction

- **HTML Parsing**: BeautifulSoup-based extraction from product listing pages
- **JSON Integration**: Parses embedded product data from page JavaScript
- **Pagination Handling**: Systematic navigation through all result pages
- **Anti-Detection**: User-Agent rotation and configurable rate limiting
- **Error Resilience**: Exponential backoff retry mechanism (max 5 retries)

### Output Management

- **CSV Export**: UTF-8 with BOM formatting for Excel compatibility
- **Deduplication**: Automatic removal of cross-category duplicate products
- **Checkpoint System**: Resume capability for interrupted scraping sessions
- **Session Persistence**: Daily checkpoint files with completed category tracking

## Project Structure

```
InflationItems/Codes/ClothingStores/Koton/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all categories from the XML sitemap
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, headers, and API constants
├── checkpoints/
│   └── koton_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/ClothingStores/Koton/          ← output lives here (outside Codes/)
├── koton_<DATE>.csv
└── InflationData/
    └── koton_inflation_<DATE>.csv

Inflations/Codes/ClothingStores/Koton/
└── inflation.py             # Inflation calculation script triggered by main.py

Inflations/Datas/ClothingStores/Koton/
└── inflation_summary.csv    # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Downloads Koton's gzip XML sitemap (`sitemap-categories-1.xml.gz`)
  │       and extracts all unique category slugs.
  │
  ├─ 2. (optional) filter by --category slug
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Results saved to disk after every completed category.
  │
  └─ 5. Final deduplication pass  →  CSV output file
```

## Data Schema

The scraper extracts comprehensive product information with the following structure:

| Field           | Type    | Description                                                  |
| --------------- | ------- | ------------------------------------------------------------ | --- |
| `pk`            | string  | Koton internal product-variant identifier                    |
| `sku`           | string  | EAN barcode number                                           |
| `base_code`     | string  | Style code (e.g., `6SAK60098EW`)                             |
| `name`          | string  | Complete product display name                                |
| `brand`         | string  | Brand name (always `Koton`)                                  |
| `category`      | string  | Full taxonomy path (e.g., `WOMEN > WOVEN TOPS > SHIRTS LS`)  |
| `color`         | string  | Color variant specification                                  |
| `size`          | string  | Size variant information                                     |
| `regular_price` | float   | Standard retail price (TRY)                                  |
| `sale_price`    | float   | Current discounted price (TRY)                               |
| `discount_pct`  | float   | Discount percentage (0 if no discount)                       |
| `currency`      | string  | Currency code (always `TRY`)                                 |
| `stock`         | integer | Available stock quantity for variant (null when unavailable) |     |

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
pip install -r InflationItems/Codes/ClothingStores/Koton/requirements.txt
```

### Dependencies

- `requests>=2.28.0` - HTTP client for web requests
- `beautifulsoup4>=4.12.0` - HTML parsing library
- `lxml>=4.9.0` - XML parser for sitemap processing
- `pandas>=1.5.0` - Data manipulation and CSV export
- `tqdm>=4.65.0` - Progress bar visualization

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory to ensure proper module resolution:

```bash
cd InflationItems/Codes/ClothingStores/Koton/scripts
```

### Command Line Interface

#### Category Discovery

```bash
# Display all available categories with slugs
python main.py --list-categories
```

#### Targeted Scraping

```bash
# Scrape single category for testing (1 page limit)
python main.py --category kadin-giyim --limit 1

# Complete single category scrape
python main.py --category kadin-giyim
```

#### Full Dataset Extraction

```bash
# Complete catalog scrape with default settings
python main.py

# Parallel processing with multiple workers
python main.py --workers 2

# Custom rate limiting
python main.py --delay 1.5
```

#### Session Management

```bash
# Resume interrupted scraping session
python main.py --resume

# Verbose logging for debugging
python main.py --category kadin-giyim -v
```

### CLI Parameters

| Parameter           | Default         | Description                                   |
| ------------------- | --------------- | --------------------------------------------- |
| `--list-categories` | N/A             | Display category taxonomy and exit            |
| `--category SLUG`   | All categories  | Limit scraping to specific category slug      |
| `--workers N`       | `1`             | Parallel thread count for category processing |
| `--delay SECONDS`   | `2.0`           | Base delay between requests (with jitter)     |
| `--limit PAGES`     | `0` (unlimited) | Maximum pages per category for testing        |
| `--resume`          | N/A             | Skip completed categories from checkpoint     |
| `-v, --verbose`     | N/A             | Enable debug-level logging                    |

### Output Files

| File Path                                                                            | Description                  |
| ------------------------------------------------------------------------------------ | ---------------------------- |
| `InflationItems/Datas/ClothingStores/Koton/koton_<DATE>.csv`                         | CSV dataset (UTF-8 with BOM) |
| `InflationItems/Codes/ClothingStores/Koton/checkpoints/koton_checkpoint_<DATE>.json` | Resume state tracking        |

File paths are automatically resolved relative to the script location, ensuring consistent operation regardless of execution directory.

## Configuration Management

### Core Settings

Configuration parameters are centralized in `scripts/config.py`:

| Parameter            | Default       | Function                                   |
| -------------------- | ------------- | ------------------------------------------ |
| `REQUEST_DELAY`      | `2.0` seconds | Base interval between page requests        |
| `MAX_RETRIES`        | `5`           | Maximum retry attempts per failed request  |
| `RETRY_BACKOFF`      | `3` seconds   | Exponential backoff multiplier             |
| `RATE_LIMIT_BACKOFF` | `60` seconds  | Minimum delay for 429/403 responses        |
| `DEFAULT_WORKERS`    | `1`           | Thread pool size for parallel processing   |
| `JITTER_MIN`         | `0.5`         | Minimum delay multiplier for rate limiting |
| `JITTER_MAX`         | `1.5`         | Maximum delay multiplier for rate limiting |

### Anti-Detection Features

- **User-Agent Rotation**: Pool of 7 realistic browser User-Agents
- **Per-Worker Assignment**: Each thread uses a consistent User-Agent
- **Rate Limiting**: Configurable delays with random jitter
- **Backoff Strategy**: Exponential backoff for failed requests

### Path Configuration

All file paths are computed relative to the config file location:

- `OUTPUT_DIR`: Target directory for CSV exports
- `CHECKPOINT_DIR`: Location for session checkpoint files
- Daily file naming with YYYY-MM-DD format

### Sitemap Configuration

- **Category Sitemap URL**: Configurable XML sitemap endpoint
- **Automatic Decompression**: Gzip decompression for sitemap files
- **Slug Extraction**: Regex-based category slug parsing

## Data Extraction Process

### Sitemap Analysis

The scraper downloads and processes the compressed XML sitemap to discover all category URLs:

1. Downloads `sitemap-categories-1.xml.gz`
2. Decompresses and parses XML structure
3. Extracts category slugs using URL pattern matching
4. Filters valid category entries

### HTML Parsing Strategy

Product data extraction uses multiple techniques:

- **CSS Selectors**: Targeted element extraction
- **JavaScript Parsing**: Embedded JSON data extraction
- **Attribute Extraction**: Product metadata from HTML attributes
- **Price Normalization**: Currency and discount calculation

### Pagination Handling

Automatic navigation through category pages:

- Detects pagination controls
- Iterates through all available pages
- Handles edge cases (empty categories, single pages)
- Maintains session state across page requests

## Error Handling & Troubleshooting

### Common Issues

| Symptom                    | Cause                          | Resolution                                       |
| -------------------------- | ------------------------------ | ------------------------------------------------ |
| HTTP 403 Forbidden         | Rate limiting or bot detection | Increase `--delay`; reduce worker count          |
| HTTP 429 Too Many Requests | Rate limit exceeded            | Automatic backoff with `RATE_LIMIT_BACKOFF`      |
| Empty output files         | Site structure changes         | Verify CSS selectors in product_fetcher.py       |
| Resume failure             | Mismatched checkpoint date     | Use current day's checkpoint or clear checkpoint |
| Module import errors       | Incorrect execution directory  | Run from `scripts/` directory                    |

### Debug Mode

Enable verbose logging with `-v` flag for detailed execution information:

```bash
python main.py --category kadin-giyim -v
```

### Rate Limiting Strategy

- **Base Delay**: 2 seconds between requests
- **Jitter Application**: ±50% random variation
- **Backoff Triggering**: Automatic on 429/403 responses
- **Worker Isolation**: Independent sessions per thread

## Technical Architecture

### Module Separation

The scraper follows a modular design pattern:

- **`config.py`** - Configuration constants, User-Agent pool, and path management
- **`category_fetcher.py`** - Stateless sitemap downloading and XML parsing
- **`product_fetcher.py`** - Stateless HTML parsing and product data extraction
- **`main.py`** - Orchestration, CLI handling, and session management

### Concurrency Model

- Thread-based parallel processing with `ThreadPoolExecutor`
- Independent `requests.Session` per thread with unique User-Agent
- Incremental checkpoint writing after category completion
- Final deduplication pass across all collected products

### Data Flow

1. Sitemap download and category discovery
2. Parallel product extraction per category
3. Real-time data validation and normalization
4. Incremental CSV writing and checkpointing
5. Cross-category deduplication
6. Final dataset export

---

**Technical Notice**: This tool is designed for research and data analysis purposes. Users must comply with applicable terms of service and rate limiting policies.
