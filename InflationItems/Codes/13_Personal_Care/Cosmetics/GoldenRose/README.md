# Golden Rose Scraper

Scrapes the public product catalog from `https://shop.goldenrose.com.tr/`.

The site runs on T-Soft and embeds rich per-product JSON records inline on
category pages via `PRODUCT_DATA.push(JSON.parse(...))`. This scraper uses
those payloads directly instead of crawling every product detail page, which
makes it faster and less fragile.

## Output

Daily CSV files are written to:

`InflationItems/Datas/Cosmetics/GoldenRose/goldenrose_YYYY-MM-DD.csv`

Checkpoint files are written to:

`InflationItems/Codes/Cosmetics/GoldenRose/checkpoints/goldenrose_checkpoint_YYYY-MM-DD.json`

## Usage

From this directory:

```bash
uv run python -m scripts.run_scraper
```

Useful options:

```bash
uv run python -m scripts.run_scraper --list-categories
uv run python -m scripts.run_scraper --category yuz
uv run python -m scripts.run_scraper --resume
uv run python -m scripts.run_scraper --limit 2
uv run python -m scripts.run_scraper --include-promotions
```

## Notes

- By default, the scraper skips the promotional top-level pages
  `Yeni Ürünler` and `Kampanyalar` because they are subsets of the main
  catalog and create heavy duplication.
- Products are deduplicated by Golden Rose product ID.
- The first two CSV columns follow the project convention:
  `Product Name`, `Product Cost`.
