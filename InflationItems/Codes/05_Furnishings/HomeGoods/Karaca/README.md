# Karaca Scraper

Scrapes Karaca's catalog from `https://www.karaca.com/` by:

- reading every listing category of the web navigation menu from its JSON
  (`/api/frontend-service/v1/menus/categories`)
- paging through each category listing (`/<category>?page=N`, 40 products per
  page) and reading the product search result that the Next.js page embeds
- writing a dated CSV snapshot under `InflationItems/Datas/HomeGoods/Karaca/`
  only when every category completed; a failed or incomplete category is
  retried once, and if it still fails the run exits with code 1 without a CSV
- checkpointing completed categories and their rows (`checkpoints/`) for
  safe resume support

The site's search returns only the products assigned to the requested category
itself, so a group listing (e.g. Sofra) misses products that are assigned to
its sub-categories only, and the other way round. All menu levels of the five
groups (Sofra, Mutfak, Küçük Ev Aletleri, Ev ve Yaşam, Hobi Eğlence) are
therefore scraped and products are deduplicated by `Product ID`. Listings
contain in-stock products only.

`Main Category` is the menu group, `Top Category` the product's own
second-level category in the site taxonomy. `price` is the price the customer
pays (including "sepette" cart discounts) and `Product Original Cost` the list
price.

## Usage

From this directory:

```bash
uv run python -m scripts.run_scraper --list-categories
uv run python -m scripts.run_scraper
uv run python -m scripts.run_scraper --category yemek-takimlari
uv run python -m scripts.run_scraper --category Sofra
uv run python -m scripts.run_scraper --resume
uv run python -m scripts.run_scraper --include-promotions
uv run python -m scripts.run_scraper --workers 1
```

`--category` accepts a category slug, a category name or a menu group name.
The CSV output always writes `product_name` as column 1 and `price` as column 2.

## Performance

Categories are scraped in parallel with a conservative worker pool and a random
1-3 s pause between pages; a full run takes about 30-40 minutes. Use
`--workers 1` for the gentlest request pattern.
