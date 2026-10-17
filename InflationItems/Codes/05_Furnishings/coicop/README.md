# TÜİK basket codes for group 05

Since October 2026 every scraper in `05_Furnishings/HomeGoods` and `05_Furnishings/ConstructionSuppliesMarkets` writes four columns:

```
product_name,price,category_number,sub_category_number
Anton Tv Sehpası,8190.0,05,0511116
"Polisan Narin Beyaz - Cİ-6900 12,5 Litre Perla Mat Silikonlu İç Cephe Boyası (28800012010)",2349.9,04,0431101
"Adalia Mdf Masa Saati 15x17x5,5 cm Naturel",1199.99,13,1321105
Adele Biblo - Gold,4759.99,0,0
```

(Bellona, Afeks, EnglishHome and MadameCoco, 2026-10-17 test run.)

`sub_category_number` is the product's item in TÜİK's 2026 CPI basket (CPI methodological notes, Appendix 1, pp. 40-54), written with its leading zero. `category_number` is the item's main group, its first two digits. A product the basket has no item for gets 0 in both. Products of other groups keep their own group: paint is 04, toys 09, hair dryers 13.

## How a code is chosen

`coicop.codes(name, category, store)` returns the pair. The scraper passes the site category the product was listed under (a breadcrumb, a menu name or a URL slug), which settles names that are ambiguous on their own. `rules.py` holds the rules as an ordered list; the first one that matches wins, so specific phrases ("bulaşık makinesi deterjanı") come before general ones ("bulaşık makinesi"). Rules with code 0 stop the search for product types without a basket item, such as drill bits. `mapping_guide.md` says which products belong to which item; the rules implement it.

Scrapers find this folder by walking up from their own path:

```python
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "coicop").is_dir())))
import coicop  # noqa: E402

writer.writerow(coicop.FIELDS)
writer.writerow(coicop.row(name, price, category, "Ikea"))
```

On a machine that still has the old layout (`InflationItems/Codes/HomeGoods/<store>`), the folder goes to `InflationItems/Codes/coicop`.

## Changing the rules

Add or move a rule in `rules.py`, then check that nothing else moved:

```bash
python InflationItems/Codes/05_Furnishings/coicop/validation/validate.py <gold.csv>
```

Setting `COICOP_AUDIT=<folder>` while a scraper runs keeps every call's inputs in `audit_<store>.tsv`; `validation/sample.py` draws a fresh stratified sample from such a run.

## Validation

See `validation/README.md`.
