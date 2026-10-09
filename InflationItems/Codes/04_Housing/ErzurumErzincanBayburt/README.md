# Erzurum / Erzincan / Bayburt - Rent Scraper

A Python tool to scrape residential rental listings for **Erzurum**, **Erzincan**, and **Bayburt** from [sahibinden.com](https://www.sahibinden.com) for the **AI 201.A Inflation Research Study** project.

**Developed by:** Batu Koray Masak

**Category:** Emlak > Konut > Kiralık

Adapted from the **IstanbulAvrupa** scraper architecture, rewritten to use **SeleniumBase** (UC mode) for native Apple Silicon support.

## Project Structure

```
Codes/HousesRent/ErzurumErzincanBayburt/
├── scripts/
│   ├── main.py       # CLI entry point & orchestrator
│   ├── scraper.py    # Core scraping logic (driver, parsing, CSV saving)
│   └── config.py     # All settings, paths, city definitions, seed ranges
├── checkpoints/
│   └── checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md
```

Output is saved to:

```
Datas/HousesRent/ErzurumErzincanBayburt/
├── Erzurum/
│   └── Erzurum_<DATE>.csv
├── Erzincan/
│   └── Erzincan_<DATE>.csv
└── Bayburt/
    └── Bayburt_<DATE>.csv
```

## Output CSV Format

| Column     | Example                    | Description                        |
| ---------- | -------------------------- | ---------------------------------- |
| `District` | `Palandöken / Yıldızkent` | District / neighbourhood           |
| `Rooms`    | `3+1`                      | Room count (raw from listing)      |
| `Price`    | `16.500 TL`                | Monthly rent in TL (raw from site) |

## Setup

```bash
cd Codes/HousesRent/ErzurumErzincanBayburt
uv pip install -r requirements.txt
```

> Chrome must be installed. SeleniumBase automatically downloads the correct chromedriver for your architecture (including Apple Silicon ARM64).
>
> On first run on Apple Silicon, you may need to install Rosetta 2: `softwareupdate --install-rosetta`

## Usage

```bash
cd Codes/HousesRent/ErzurumErzincanBayburt/scripts

# Full scrape - all 3 cities
uv run python main.py

# Resume an interrupted run
uv run python main.py --resume

# Scrape only a specific city
uv run python main.py --city erzurum
uv run python main.py --city erzincan
uv run python main.py --city bayburt

# Verbose debug output
uv run python main.py -v
```

## How It Works

### Adaptive Price Brackets

sahibinden.com caps results at ~1,000 listings per query. The scraper uses **Smart Adaptive Brackets with Early Peek**: on the first page of any seed range, it reads the total listing count.

- If <= 1000: scrapes all pages normally.
- If > 1000: splits the range in half and recurses.

Since Erzurum, Erzincan, and Bayburt are smaller cities, most ranges won't need splitting, but the mechanism is kept as a safety net.

### Multi-City Support

The scraper iterates over all three cities sequentially, with configurable delays between cities to be polite to the server. Each city's data is saved to its own subfolder with separate daily CSV files.

### Resume Support

After each price bracket the scraper writes a checkpoint file:

```
Codes/HousesRent/ErzurumErzincanBayburt/checkpoints/checkpoint_<DATE>.json
```

Pass `--resume` to pick up from where a previous interrupted run left off. A new run (without `--resume`) always starts fresh.

### CAPTCHA Handling

If sahibinden blocks a request, the scraper:

1. Detects the missing listings and prints a warning.
2. Pauses and prompts you to solve the CAPTCHA in the Chrome window.
3. Resumes automatically once you press **ENTER** in the terminal.

## Configuration

Edit `scripts/config.py` to change:

| Setting                      | Default       | Description                       |
| ---------------------------- | ------------- | --------------------------------- |
| `CITIES`                     | 3 cities      | City definitions and seed ranges  |
| `PAGE_LOAD_DELAY`            | `2.5` s       | Wait after each page loads        |
| `PAGE_TURN_DELAY_MIN/MAX`    | `2.0 - 4.0` s | Random delay between page turns   |
| `BETWEEN_BRACKET_DELAY`      | `1.0 - 2.0` s | Random delay between brackets     |
| `BETWEEN_CITY_DELAY`         | `3.0 - 6.0` s | Random delay between cities       |
| `PAGE_SIZE`                  | `50`          | Listings per page                 |

## Notes

- Data is collected daily as required by the project guidelines.
- Duplicate-looking rows (same district, rooms, price) represent distinct listings that share those attributes, not scraping errors.
- This tool is for academic / research purposes only. Always respect `robots.txt` and the site's Terms of Service.