# Vivense Türkiye Product Scraper

Daily product scraper for [Vivense](https://www.vivense.com) — a Turkish online
furniture and home-goods retailer. The scraper walks every top-level navigation
category, paginates through `?page=N` until an empty page is returned, parses the
embedded `data-*` attributes from each product card, and writes a daily CSV.

## Why HTML scraping (not an API)?

Unlike Migros (REST) or Rossmann (GraphQL), Vivense does **not** expose a public
product API. All product cards are server-rendered into category HTML with the
relevant metadata embedded as `data-*` attributes on a
`<div class="product-card product-content parent">` element, so a plain
`requests` + `BeautifulSoup` pipeline is sufficient — Selenium is **not**
required.

## Layout

```
InflationItems/Codes/HomeGoods/Vivense/
├── README.md
├── requirements.txt
├── checkpoints/                 # daily resume state
└── scripts/
    ├── config.py                # base URL, headers, paths, top-level categories
    ├── category_fetcher.py      # returns the curated category list
    ├── product_fetcher.py       # paginated HTML scraper (BeautifulSoup)
    └── main.py                  # CLI orchestrator + ThreadPoolExecutor
```

CSV output is written to `InflationItems/Datas/HomeGoods/Vivense/vivense_YYYY-MM-DD.csv`.

## Output Schema

The first two columns are the ones every HomeGoods store shares and the only
ones the inflation calculator reads; the rest are appended after them.

| Column          | Type  | Notes                                                              |
| --------------- | ----- | ------------------------------------------------------------------ |
| `product_name`  | str   | Product display name (`data-product-name`)                         |
| `price`         | float | Price the customer pays now, in TRY (post-discount)                |
| `url`           | str   | Product page URL                                                   |
| `id`            | str   | SKU (`data-product-sku`); key of the final deduplication           |
| `regular_price` | float | List price in TRY (`psf-price`; equals `price` when not discounted) |

## Pricing & Discount Extraction

Vivense embeds **two** prices per product card:

| Source                                        | Meaning                        | When present                   |
| --------------------------------------------- | ------------------------------ | ------------------------------ |
| `data-product-price` _(or `span.last-price`)_ | Final price the customer pays  | Always                         |
| `span.psf-price`                              | Original / list price          | Only when a discount is active |
| `data-discount-rate`                          | Discount percentage (`""` → 0) | Always                         |

The mapping the scraper uses:

- `price` ← `data-product-price` (fallback: `last-price` text)
- `regular_price` ← `psf-price` (fallback: `price` when not discounted)

When a product has no discount, `regular_price == price`. When a product is
discounted, the inflation calculator treats `price` as the authoritative
current price (matching the convention used for Migros, Rossmann and Bauhaus).

## Pagination & End-of-Catalogue Detection

Vivense uses 1-indexed `?page=N` pagination, returning ~60 products per page.
Pages are requested with `&sort=price_asc` (`config.SORT_ORDER`): the default
order repeats some products on adjacent pages and never shows others.
A page number past the end redirects to page 1 of the category.
The scraper terminates a category on the **first** of these conditions:

1. The page contains zero `product-card.product-content.parent` elements,
   or its cards carry a `data-page-id` other than the requested page
   (the redirect above).
2. The set of SKUs on the current page is identical to the previous page
   (defensive guard against the site silently clamping `page` to the last
   valid value).
3. Every card on the page is already in the running SKU set (no new
   products contributed → end of catalogue reached).
4. The `--limit` CLI flag is exceeded.
5. The `PAGE_HARD_LIMIT` constant (200) is hit — final safety net.

## Usage

```bash
# List all available categories
python main.py --list-categories

# Scrape a single category (for testing)
python main.py --category oturma-odasi-mobilyalari --limit 1

# Full daily catalogue extraction (default 3 workers)
python main.py

# Resume an interrupted run
python main.py --resume

# Tune throughput / politeness
python main.py --workers 4 --delay 0.7
```

After a successful scrape the runner automatically invokes the inflation
calculator at `Inflations/Codes/HomeGoods/Vivense/inflation.py`.

A category that fails (page fetch error, or fewer than 90 % of the site's own
"N Ürün" count collected) is retried once from page 1. Between 90 % and 98 %
the category is kept and logged as a warning, because some listings stay a few
percent below their own count for hours. If a category fails again the
run writes no CSV, skips the inflation step and exits with code 1, because the
daily runner counts any CSV as success. Rows of the finished categories stay
in `checkpoints/vivense_partial_YYYY-MM-DD.part` for `--resume`.

## Categories

The scraper first walks the 19 curated top-level buckets of the header menu
(`config.TOP_LEVEL_CATEGORIES`), then every listing of the category sitemap
`category_sitemap1.php` (listed in robots.txt). The sub-category listings are
needed because a top-level listing shows only one member of many product
families: on 2026-09-28 they added 495 goods (wardrobes by door count,
king-size mattresses, three-seat sofas, ...) to the 24,501 found in the
top-level listings. Showroom pages and service / fee listings (installation,
shipping, gift cards; `config.NON_GOODS_SLUG_PATTERN`) are skipped. Products
listed in several categories are written once (dedup on `id`). If the sitemap
cannot be read, the run falls back to the curated list and logs a warning.

Colour and size variants that no listing shows are only reachable from product
pages and are not collected: the product sitemap had 67,839 product URLs on
2026-09-28, about 2.7 times the listed products.

## TUIK Mapping

Every Vivense top-level category maps to TUIK group **05** —
_Mobilya, ev aletleri ve ev bakım hizmetleri_ (weight 7.92 % in the 2026
TÜFE basket). See `Inflations/Codes/HomeGoods/Vivense/tuik_config.py`.
