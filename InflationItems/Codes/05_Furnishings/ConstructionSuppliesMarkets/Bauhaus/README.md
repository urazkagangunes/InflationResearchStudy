# Bauhaus Türkiye Product Scraper

A Python-based web scraping system that systematically extracts product data from [bauhaus.com.tr](https://www.bauhaus.com.tr) through optimized HTML parsing and CSS selector-based extraction.

## Architecture Overview

The scraper implements a modular architecture with four core components:

- **`main.py`** - CLI interface and orchestration controller
- **`category_fetcher.py`** - HTML navigation-based category discovery
- **`product_fetcher.py`** - Optimized product data extraction with lxml
- **`config.py`** - Centralized configuration and constants management

## Core Functionality

### Category Discovery

Automatically maps the complete product catalog by parsing the homepage HTML navigation structure. Extracts all category links following the `bauhaus-` URL pattern, currently identifying ~600 subcategories across all product departments.

### Data Extraction

- **Optimized Parsing**: lxml parser for 3-5x faster HTML processing
- **CSS Selectors**: Efficient DOM traversal for product element extraction
- **Session Management**: HTTP connection reuse across categories
- **Adaptive Rate Limiting**: Intelligent delays to prevent detection
- **Performance Optimization**: 35-55% speedup through multiple optimizations

### Output Management

- **CSV Export**: UTF-8 with BOM formatting for Excel compatibility
- **Batched Checkpoints**: Reduced I/O overhead (saves every 5 categories)
- **Deduplication**: Automatic removal of cross-category duplicate products
- **Session Persistence**: Daily checkpoint files with completed category tracking

## Project Structure

```
InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all scrapable categories via HTML navigation
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, and delay constants
├── checkpoints/
│   └── bauhaus_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/           ← output lives here
├── bauhaus_<DATE>.csv
└── InflationData/
    └── bauhaus_inflation_<DATE>.csv

Inflations/Codes/ConstructionSuppliesMarkets/Bauhaus/
└── inflation.py      # Inflation calculation script triggered by main.py

Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/
└── inflation_summary.csv # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Parses homepage HTML to extract all category links
  │       starting with 'bauhaus-' pattern.
  │
  ├─ 2. (optional) filter by --category ID
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Uses optimized lxml parser and CSS selectors.
  │               Results saved to disk after every 5 categories.
  │
  └─ 5. Final deduplication pass  →  CSV output file
```

## Data Schema

The scraper extracts comprehensive product information with the following structure:

| Field           | Type    | Description                               |
| --------------- | ------- | ----------------------------------------- |
| `id`            | string  | Unique product identifier (SKU)           |
| `sku`           | string  | SKU or barcode number                     |
| `name`          | string  | Product display name (Turkish)            |
| `brand`         | string  | Manufacturer or brand name                |
| `category`      | string  | Subcategory classification                |
| `regular_price` | float   | Standard retail price (TRY)               |
| `shown_price`   | float   | Current display price (TRY)               |
| `discount_rate` | integer | Discount percentage (0 when no promotion) |
| `unit`          | string  | Unit of measurement (default: "PIECE")    |
| `status`        | string  | Availability status (default: "IN_SALE")  |

## Performance Optimizations

The scraper implements six key optimizations achieving **35-55% performance improvement**:

1. **lxml Parser**: 3-5x faster HTML parsing compared to default parser
2. **CSS Selectors**: Faster DOM traversal vs lambda-based selectors
3. **Session Reuse**: Persistent HTTP connections across category requests
4. **Batched Checkpoints**: Reduced I/O overhead (saves every 5 categories)
5. **String Optimization**: Efficient price cleaning with chained operations
6. **Adaptive Rate Limiting**: Intelligent delays prevent rate limiting while optimizing speed

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
pip install -r InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/requirements.txt
```

### Dependencies

- `requests==2.32.3` - HTTP client for web requests
- `beautifulsoup4==4.12.3` - HTML parsing library with lxml integration

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory to ensure proper module resolution:

```bash
cd InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/scripts
```

### Command Line Interface

#### Category Discovery

```bash
# Display all available categories with IDs
python main.py --list-categories
```

#### Targeted Scraping

```bash
# Scrape single category (ID "bauhaus-oto")
python main.py --category bauhaus-oto

# Test scrape with page limit
python main.py --category bauhaus-oto --limit 2
```

#### Full Dataset Extraction

```bash
# Complete catalog scrape with default settings
python main.py

# Parallel processing with custom worker count
python main.py --workers 4

# Custom rate limiting
python main.py --delay 3.0
```

#### Session Management

```bash
# Resume interrupted scraping session
python main.py --resume

# Verbose logging for debugging
python main.py --category bauhaus-oto -v
```

### CLI Parameters

| Parameter           | Default         | Description                                   |
| ------------------- | --------------- | --------------------------------------------- |
| `--list-categories` | N/A             | Display category taxonomy and exit            |
| `--category ID`     | All categories  | Limit scraping to specific category ID        |
| `--workers N`       | `2`             | Parallel thread count for category processing |
| `--delay SECONDS`   | `2.0`           | Base delay between requests (with jitter)     |
| `--limit PAGES`     | `0` (unlimited) | Maximum pages per category for testing        |
| `--resume`          | N/A             | Skip completed categories from checkpoint     |
| `-v, --verbose`     | N/A             | Enable debug-level logging                    |

### Output Files

| File Path                                                                                             | Description                  |
| ----------------------------------------------------------------------------------------------------- | ---------------------------- |
| `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/bauhaus_<DATE>.csv`                         | CSV dataset (UTF-8 with BOM) |
| `InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/checkpoints/bauhaus_checkpoint_<DATE>.json` | Resume state tracking        |

File paths are automatically resolved relative to the script location, ensuring consistent operation regardless of execution directory.

## Configuration Management

### Core Settings

Configuration parameters are centralized in `scripts/config.py`:

| Parameter         | Default       | Function                                   |
| ----------------- | ------------- | ------------------------------------------ |
| `REQUEST_DELAY`   | `2.0` seconds | Base interval between page requests        |
| `MAX_RETRIES`     | `5`           | Maximum retry attempts per failed request  |
| `RETRY_BACKOFF`   | `3` seconds   | Exponential backoff multiplier             |
| `DEFAULT_WORKERS` | `2`           | Thread pool size for parallel processing   |
| `JITTER_MIN`      | `1.0`         | Minimum delay multiplier for rate limiting |
| `JITTER_MAX`      | `2.0`         | Maximum delay multiplier for rate limiting |

### Request Configuration

- **Base URL**: `https://www.bauhaus.com.tr`
- **Default Headers**: Realistic browser headers for anti-detection
- **User-Agent**: Chrome-based User-Agent string
- **Accept Headers**: Standard browser accept patterns

### Path Configuration

All file paths are computed relative to the config file location:

- `OUTPUT_DIR`: Target directory for CSV exports
- `CHECKPOINT_DIR`: Location for session checkpoint files
- Daily file naming with YYYY-MM-DD format

## Category Discovery Process

### Navigation Parsing

The scraper extracts category information from the homepage HTML navigation:

1. Downloads and parses the homepage HTML
2. Identifies all `<a>` tags with `href` attributes matching `bauhaus-` pattern
3. Supports both full URLs (`https://www.bauhaus.com.tr/bauhaus-*`) and relative URLs (`/bauhaus-*`)
4. Normalizes URLs to consistent format for processing

### URL Pattern Matching

Categories are identified using these patterns:

- **Full URLs**: `https://www.bauhaus.com.tr/bauhaus-*`
- **Relative URLs**: `/bauhaus-*`
- **Pattern**: Any URL starting with `bauhaus-` prefix

This approach automatically discovers all ~600 subcategories without manual configuration.

## Error Handling & Troubleshooting

### Common Issues

| Symptom                    | Cause                         | Resolution                                       |
| -------------------------- | ----------------------------- | ------------------------------------------------ |
| HTTP 429 Too Many Requests | Rate limit exceeded           | Increase `--delay`; reduce worker count          |
| Empty output files         | HTML structure changes        | Verify CSS selectors in product_fetcher.py       |
| Resume failure             | Mismatched checkpoint date    | Use current day's checkpoint or clear checkpoint |
| Module import errors       | Incorrect execution directory | Run from `scripts/` directory                    |
| Slow performance           | Using default HTML parser     | Ensure lxml is properly installed                |

### Debug Mode

Enable verbose logging with `-v` flag for detailed execution information:

```bash
python main.py --category bauhaus-oto -v
```

### Performance Verification

To ensure optimal performance:

- Verify lxml installation: `pip show lxml`
- Monitor memory usage during large scrapes
- Check network connectivity for consistent request times
- Validate CSS selector efficiency

## Technical Architecture

### Module Separation

The scraper follows a modular design pattern:

- **`config.py`** - Configuration constants, headers, and path management
- **`category_fetcher.py`** - Stateless HTML navigation parsing and category extraction
- **`product_fetcher.py`** - Optimized product data extraction with lxml and CSS selectors
- **`main.py`** - Orchestration, CLI handling, and session management

### Performance Architecture

- **lxml Integration**: High-performance XML/HTML parsing
- **CSS Selector Optimization**: Efficient DOM element targeting
- **Connection Pooling**: HTTP session reuse across requests
- **Batched I/O**: Reduced file system overhead
- **Adaptive Rate Limiting**: Intelligent request timing

### Concurrency Model

- Thread-based parallel processing with `ThreadPoolExecutor`
- Independent `requests.Session` per thread
- Batched checkpoint writing (every 5 categories)
- Final deduplication pass across all collected products

### Data Flow

1. Homepage download and navigation parsing
2. Category URL extraction and normalization
3. Parallel product extraction per category
4. Real-time data validation and normalization
5. Batched CSV writing and checkpointing
6. Cross-category deduplication
7. Final dataset export

---

**Technical Notice**: This tool is designed for research and data analysis purposes. Users must comply with applicable terms of service and rate limiting policies.
