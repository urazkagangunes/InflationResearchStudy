# Istanbul Avrupa Rent Scraper

A Python-based web scraping system that systematically extracts residential rental listings for **Istanbul's European side** from [sahibinden.com](https://www.sahibinden.com) using Selenium-based browser automation and adaptive price bracket splitting.

## Architecture Overview

The scraper implements a modular architecture with three core components:

- **`main.py`** - CLI interface and orchestration controller
- **`scraper.py`** - Core scraping logic with bracket splitting and page parsing
- **`config.py`** - Centralized configuration and constants management

## Core Functionality

### Adaptive Bracket Discovery

Implements an intelligent algorithm to overcome sahibinden.com's 1,000 listing limit per query:

- **Initial Range Definition**: 5 wide seed price ranges (0-20,000 TL)
- **Recursive Splitting**: Automatically divides ranges exceeding 1,000 listings
- **Optimal Bracket Generation**: Creates "safe" leaf brackets under the limit
- **Efficient Caching**: Stores resolved boundaries for faster restart

### Browser Automation

- **Selenium Integration**: Full browser automation with undetected-chromedriver
- **CAPTCHA Handling**: Interactive prompts for manual CAPTCHA resolution
- **Persistent Profiles**: Saves browser state and cookies between sessions
- **Anti-Detection**: Stealth mode to avoid bot detection mechanisms

### Data Extraction

- **Real-time Parsing**: BeautifulSoup-based HTML parsing from live browser content
- **Listing Normalization**: Structured data extraction from rental listings
- **Incremental Saving**: Progressive CSV writing during scraping process
- **Session Persistence**: Checkpoint-based resume capability

## Project Structure

```
InflationItems/Codes/HousesRent/IstanbulAvrupa/
├── scripts/
│   ├── main.py       # CLI entry point & run orchestration
│   ├── scraper.py    # Scraping logic (bracket splitting, page parsing, CSV output)
│   └── config.py     # All settings, paths, seed ranges
├── checkpoints/
│   └── checkpoint_<DATE>.json   # Resume state (auto-generated)
├── SeleniumProfile/  # Persistent browser profile (saves login state, cookies)
├── requirements.txt
└── README.md

InflationItems/Datas/HousesRent/IstanbulAvrupa/           ← output lives here
├── IstanbulAvrupa_<DATE>.csv
└── InflationData/
    └── IstanbulAvrupa_inflation_<DATE>.csv

Inflations/Codes/HousesRent/IstanbulAvrupa/
└── inflation.py      # Inflation calculation script triggered by main.py

Inflations/Datas/HousesRent/IstanbulAvrupa/
└── inflation_summary.csv # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. Load / initialise checkpoint
  │
  ├─ 2. Adaptive bracket discovery       ← scraper.scrape_and_resolve()
  │       Recursively splits large price ranges if listings > 1,000.
  │       Produces "safe" leaf brackets.
  │
  ├─ 3. Page scraping                    ← scraper.scrape_leaf_bracket()
  │       Paginates through safe brackets and normalizes records.
  │       Results saved to CSV incrementally.
  │
  └─ 4. Caching & Checkpointing
          Records completed brackets to allow quick resume.
          Caches resolved bounds for faster restart.
```

## Data Schema

The scraper extracts rental listing information with the following structure:

| Field      | Type   | Description                                 |
| ---------- | ------ | ------------------------------------------- |
| `District` | string | District or neighborhood name               |
| `Rooms`    | string | Room count specification (raw from listing) |
| `Price`    | string | Monthly rent amount (raw from site)         |

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)
- Chrome browser (required for Selenium)

### Installation Steps

```bash
# Navigate to project root
cd InflationResearchStudy

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r InflationItems/Codes/HousesRent/IstanbulAvrupa/requirements.txt
```

### Dependencies

- `beautifulsoup4` - HTML parsing library
- `lxml` - XML parser for efficient HTML processing
- `undetected-chromedriver` - Stealth Chrome driver for anti-detection
- `selenium` - Browser automation framework
- `tqdm` - Progress bar visualization

### Browser Requirements

- Chrome browser must be installed on the system
- `undetected-chromedriver` automatically manages ChromeDriver compatibility
- SeleniumProfile directory stores persistent browser state

## Operation Guide

### Execution Requirements

All commands must be executed from the `scripts/` directory:

```bash
cd InflationItems/Codes/HousesRent/IstanbulAvrupa/scripts
```

### Command Line Interface

#### Full Dataset Extraction

```bash
# Complete scrape with default settings
python main.py

# Custom page load delay
python main.py --delay 4.0
```

#### Testing & Development

```bash
# Limited scrape for testing (3 brackets only)
python main.py --limit-brackets 3

# Verbose logging for debugging
python main.py -v
```

#### Session Management

```bash
# Resume interrupted scraping session
python main.py --resume
```

### CLI Parameters

| Parameter            | Default         | Description                              |
| -------------------- | --------------- | ---------------------------------------- |
| `--delay SECONDS`    | `2.5`           | Per-page wait time (±50% jittered)       |
| `--limit-brackets N` | `0` (unlimited) | Stop after N leaf brackets (for testing) |
| `--resume`           | N/A             | Skip completed brackets from checkpoint  |
| `-v, --verbose`      | N/A             | Enable debug-level logging               |

### Output Files

| File Path                                                                           | Description           |
| ----------------------------------------------------------------------------------- | --------------------- |
| `InflationItems/Datas/HousesRent/IstanbulAvrupa/IstanbulAvrupa_<DATE>.csv`          | CSV dataset (UTF-8)   |
| `InflationItems/Codes/HousesRent/IstanbulAvrupa/checkpoints/checkpoint_<DATE>.json` | Resume state tracking |

File paths are automatically resolved relative to the script location.

## Configuration Management

### Core Settings

Configuration parameters are centralized in `scripts/config.py`:

| Parameter                | Default           | Function                                         |
| ------------------------ | ----------------- | ------------------------------------------------ |
| `SEED_RANGES`            | 5 wide ranges     | Initial price ranges for adaptive splitting      |
| `MAX_LISTINGS_PER_QUERY` | `1000`            | Threshold triggering bracket division            |
| `MIN_BRACKET_WIDTH`      | `50` TL           | Minimum bracket width to prevent infinite splits |
| `PAGE_LOAD_DELAY`        | `2.5` seconds     | Base wait time after page loads                  |
| `BETWEEN_BRACKET_DELAY`  | `1.0-2.0` seconds | Random delay between bracket operations          |

### City Configuration

- **City URL Name**: `istanbul-avrupa` for URL construction
- **Folder Name**: `IstanbulAvrupa` for file path generation
- **Target Area**: European side of Istanbul

### Path Configuration

All file paths are computed relative to the config file location:

- `OUTPUT_DIR`: Target directory for CSV exports
- `CHECKPOINT_DIR`: Location for session checkpoint files
- `SELENIUM_PROFILE_DIR`: Persistent browser profile storage

## Adaptive Bracket Algorithm

### Algorithm Overview

The scraper implements a sophisticated algorithm to overcome sahibinden.com's query limitations:

1. **Initial Seed Ranges**: Five wide price ranges covering the market spectrum
2. **Listing Count Detection**: Analyzes total listings per range from page 1
3. **Recursive Splitting**: Divides ranges exceeding 1,000 listings
4. **Optimal Bracket Generation**: Creates safe brackets under the threshold
5. **Efficient Scraping**: Uses already-loaded page 1 for immediate scraping

### Seed Range Configuration

Default seed ranges cover the full price spectrum:

- Range 1: 0 - 19,999 TL (High density, will trigger multiple splits)
- Range 2: 20,000 - 39,999 TL (High density)
- Range 3: 40,000 - 59,999 TL
- Range 4: 60,000 - 99,999 TL
- Range 5: 100,000 - 9,999,999 TL (Low density, likely won't split at all)

### Splitting Logic

- **Threshold**: 1,000 listings per query
- **Strategy**: Binary splitting (divide range in half)
- **Termination**: When range falls below threshold
- **Safety Margin**: Prevents infinite splitting with minimum width

## Browser Automation & CAPTCHA Handling

### Selenium Configuration

- **Driver**: undetected-chromedriver for stealth operation
- **Profile Persistence**: Saves cookies and session state
- **Version Management**: Automatic ChromeDriver version matching
- **Headless Mode**: Optional for server operation

### CAPTCHA Resolution Process

When anti-bot measures are triggered:

1. **Detection**: Scraper identifies CAPTCHA or login walls
2. **Pause**: Automated pause with user notification
3. **Manual Resolution**: User solves CAPTCHA in Chrome window
4. **Resume**: User presses ENTER to continue scraping
5. **Verification**: Scraper confirms page load before proceeding

### Anti-Detection Measures

- **Random Delays**: Jittered timing between requests
- **Human-like Behavior**: Realistic browsing patterns
- **Session Persistence**: Maintains login state across sessions
- **Stealth Mode**: Undetectable Chrome driver configuration

## Error Handling & Troubleshooting

### Common Issues

| Symptom              | Cause                        | Resolution                                           |
| -------------------- | ---------------------------- | ---------------------------------------------------- |
| CAPTCHA频繁出现      | Aggressive scraping patterns | Increase `--delay`; reduce concurrent operations     |
| Chrome driver errors | Browser version mismatch     | Update Chrome; verify undetected-chromedriver        |
| Empty output files   | Page structure changes       | Verify CSS selectors in scraper.py                   |
| Resume failure       | Checkpoint file corruption   | Delete checkpoint; restart fresh                     |
| Browser crashes      | Memory/resource issues       | Reduce concurrent operations; check system resources |

### Debug Mode

Enable verbose logging with `-v` flag for detailed execution information:

```bash
python main.py -v
```

### Performance Optimization

- **Memory Management**: Monitor browser memory usage
- **Network Stability**: Ensure consistent internet connectivity
- **Resource Allocation**: Sufficient system resources for Chrome
- **Timing Optimization**: Adjust delays based on server response

## Technical Architecture

### Module Separation

The scraper follows a modular design pattern:

- **`config.py`** - Configuration constants, paths, and algorithm parameters
- **`scraper.py`** - Core scraping logic with bracket splitting and browser automation
- **`main.py`** - CLI orchestration and session management

### Browser Integration

- **Selenium WebDriver**: Full browser automation capabilities
- **BeautifulSoup Integration**: HTML parsing from rendered content
- **Profile Management**: Persistent browser state storage
- **Error Recovery**: Automatic browser restart on crashes

### Data Flow

1. Adaptive bracket discovery and resolution
2. Browser initialization and profile loading
3. Sequential bracket processing with page scraping
4. Real-time data extraction and normalization
5. Incremental CSV writing and checkpointing
6. Final dataset export and validation

---

**Technical Notice**: This tool is designed for research and data analysis purposes. Users must comply with applicable terms of service and rate limiting policies.
