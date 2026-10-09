# Happy Center Price Tracker

**AI201 - Intro to Data Science** | Spring 2026 | Ozyegin University

Daily web scraper for [Happy Center](https://www.happycenter.com.tr/) that tracks product prices across all categories.

## Setup

```bash
cd InflationResearchStudy/Codes/Markets/HappyCenter
pip install -r requirements.txt
```

No special dependencies needed. Unlike some Turkish grocery sites, Happy Center does not block Python's `requests` library (no `curl_cffi` required).

## Usage

```bash
python -m scripts.run_scraper
```

Output: `Datas/Markets/HappyCenter/happycenter_YYYY-MM-DD.csv` (+ `.tsv` copy)

Logs: `Datas/Markets/HappyCenter/logs/scraper.log`

## Project Structure

```
src/config.py          - URLs, 15 subcategories, headers, delays
src/utils.py           - parse_price(), fetch_page(), logging setup
src/scraper.py         - Core engine: pagination, extraction, deduplication

scripts/run_scraper.py - Entry point (what you run)
scripts/run_daily.sh   - Shell wrapper for cron automation
```

## Categories Scraped

**Kuru Gida** (5): Cay-Seker-Bakliyat, Icecek, Corba-Yaglar, Konserve-Soslar, Atistirmalik

**Taze Urunler** (5): Yogurt-Dondurma, Sutluk, Manav, Kahvaltilik, Kasap-Sarkuter

**Gida Disi** (5): Temizlik Yardimcilari, Tekstil-Kitap-Pet, Temizlik, Kozmetik, Hijyen-Bebe

## Data Schema

| Column | Type | Description |
|--------|------|-------------|
| product_id | str | URL slug (unique identifier) |
| name | str | Product name (Turkish) |
| current_price | float | Current price (TL) |
| regular_price | float | Always empty (site doesn't show old prices) |
| is_discounted | bool | Always False (no discount info available) |
| discount_pct | float | Always empty |
| category | str | Subcategory name |
| product_url | str | Full product page URL |
| image_url | str | Product thumbnail URL |
| in_stock | bool | True (listed = available) |
| scrape_date | str | YYYY-MM-DD |
| scrape_timestamp | str | ISO 8601 timestamp |

## Site Technical Notes

- **Platform:** Custom PHP site with Cloudflare CDN (not WAF)
- **No anti-bot:** Standard `requests` works, no browser impersonation needed
- **Pagination:** `?page=N`, last page number available in pagination links ("Son" link)
- **Products:** Server-side rendered HTML, no JavaScript needed
- **Images:** Hosted on `static.happycenter.com.tr/Uploads/`, 95x95 thumbnails
- **No numeric IDs:** Products identified by URL slug
- **No discount info:** Site only shows current price, no strikethrough/original price
