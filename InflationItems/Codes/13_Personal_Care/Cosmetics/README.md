# Cosmetics Scrapers Documentation

This directory contains automated daily scrapers designed to collect product price data from leading cosmetics and personal care retailers in Turkey for inflation research studies.

---

## 📋 Overview of Scrapers

| Retailer | Source Code | Architecture / Protocol | Target / Technique |
| :--- | :--- | :--- | :--- |
| **Avon** | `Avon/avon.py` | Playwright (Async Firefox) | Dynamic SPA, headful/headless browser crawler with product categorization |
| **Beymen Beauty** | `Beymen Beauty/cosmetic.py` | Direct REST API (requests) | Multi-facet catalog pagination through internal product filtering API |
| **Dermoeczanem** | `Dermoeczanem/dermoeczanem_scraper.py` | HTTP / BeautifulSoup | Multi-category pagination crawler (`?pg=N`) |
| **Dermomarket** | `Dermomarket/dermomarket_scraper.py` | Selenium WebDriver (Chrome) | Headless browser pagination across 10 major dermocosmetics categories |
| **Eveshop** | `Eveshop/eveshop_scraper.py` | Shopify Public JSON API (Async) | Paginated product queries (`/products.json?limit=250&page=N`) |
| **Flormar** | `Flormar/flormar_scraper.py` | Async HTTP + Schema.org | XML Sitemap discovery (`sitemap-products-1.xml.gz`) + JSON-LD metadata parsing |
| **Golden Rose** | `GoldenRose/scripts/main.py` | HTTP / BeautifulSoup | Multi-worker parallel category & product parsing |
| **Gratis** | `Gratis/gratis_scraper.py` | Async HTTP + Schema.org | Official XML sitemap catalog (`Product-tr-TRY.xml`) + JSON-LD extraction with exponential backoff rate limiting |
| **Kozmela** | `Kozmela/kozmela_scraper.py` | HTTP / BeautifulSoup | Multi-category pagination crawler across beauty & care catalogs |
| **L'Occitane** | `Loccitane/loccitane_scraper.py` | Shopify Public JSON API (Async) | Direct collection pagination (`/collections/all/products.json`) |
| **Marks & Spencer** | `M&S/m&s.py` | Undetected Chromedriver | Infinite scroll & JS pagination on cosmetics listings |
| **Pazarium** | `Pazarium/pazarium_scraper.py` | HTTP / BeautifulSoup | Category-based cosmetics catalog crawler |
| **Rossmann** | `Rossmann/scripts/main.py` | GraphQL API | Direct GraphQL queries with multithreaded pagination & inflation delta tracking |
| **Watsons** | `Watsons/scraper.py` | Camoufox (Anti-bot Firefox) + curl_cffi | Sitemap caching, Akamai bypass, and incremental master database updates |

---

## 🛠️ Execution & Orchestration

All scrapers are executed sequentially every night via the root bash orchestrator:

```bash
./run_cosmetics.sh
```

### Key Orchestrator Features:
- **Timeout Protection:** Imposes a 2-hour hard limit (`timeout 7200`) per retailer to prevent hangs.
- **Unbuffered Logging:** Runs scripts with `python3 -u` and writes individual logs to `logs/cosmetics/<Retailer>_<Date>.log`.
- **Automated Cron Schedule:** Runs at `03:00` UTC/local daily via server cron.

---

## 📂 Data Output Format

Output CSV files are standardized and exported to:
```
InflationItems/Datas/Cosmetics/<Retailer>/<retailer>_YYYY-MM-DD.csv
```

### Standard Schema:
- `product_name`: Title of the product
- `price`: Numeric price in Turkish Lira (TRY / ₺)
- Additional metadata (such as `category`, `variant`, or `url`) is included where provided by the respective platform.
