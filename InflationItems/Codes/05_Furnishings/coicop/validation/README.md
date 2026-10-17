# Validating the basket codes

The question is how often a product gets the wrong code, and how often a product that belongs to a basket item gets 0. Both are measured on a sample coded independently against `../mapping_guide.md`, weighted back to the whole catalogue.

## Method

1. Population. Every product of one full scrape of the 30 stores, with the site category each was listed under: the scrapers ran with `COICOP_AUDIT` set and the audit files were collected. In the 2026-10-17 run Koçtaş and Nalburcuk come from their 2026-10-16 files (Koçtaş's site blocks the machine the run was made on, Nalburcuk takes hours). The first round also took Karaca and Bauhaus from their audit shortly before their runs ended (about 90% of their products) and Yapıyoz from its first 296 products; the second round has all three complete.
2. Sample. `sample.py` splits the population by the code the rules give: each non-zero code is a stratum, and the products given 0 form one stratum per store, because that is where missed products hide. A fixed number of products is drawn from each stratum, so rare items are checked as well as common ones; with `--scale`, large strata get more, one per `--scale` products up to `--cap`.
3. Gold codes. Two labellers code every sampled product independently, from the product name, site category and store only. They see the mapping guide and the basket list, not the rules or the rules' answers. Where they disagree, a third labeller picks between their codes or gives another one. The gold code is the agreed or the decided code. In the 2026-10-17 runs the three labellers were language-model passes working from these instructions; no person checked the gold codes.
4. Measurement. `validate.py` compares the rules with the gold codes. Each product counts with weight stratum size / products drawn, so the figures are estimates for the whole catalogue rather than for the sample, and the 95% intervals come from a bootstrap within strata.

## Measures

- accuracy: share of products whose code is the gold code.
- false match: among products the rules gave a code, the share whose code is wrong (another item, or a code where the gold is 0).
- missed: among products that have a gold code, the share the rules gave 0.
- group: share with the right `category_number`.

## Results (2026-10-17)

Two rounds. The first measured the rules as first written; its disagreements were then used to correct the rules, so the second round measures the corrected rules on a fresh sample that leaves out every first-round product (`--exclude`). Before the second round the guide gained a table of the cases the first-round labellers had split on ("Cases settled by the first validation").

| Round | Sample | Strata | Population | Labellers agreed | Kappa |
|---|---|---|---|---|---|
| 1 | 1,224; 8 per code, 12 per store's zero products | 149 | 156,755 | 1,137 (92.9%) | 0.92 |
| 2 | 1,215; 6 to 40 per code, 12 to 40 per store's zero products (`--scale 250`) | 144 | 162,685 | 1,160 (95.5%) | 0.95 |

| | Round | Accuracy | False match | Missed | Group | Zero share, rules / gold |
|---|---|---|---|---|---|---|
| All stores | 1 | 84.4% (79.7-88.7) | 16.9% (11.1-23.2) | 5.1% (3.2-7.3) | 90.0% (85.6-93.6) | 29.4% / 28.8% |
| | 2 | 87.1% (84.8-89.3) | 14.4% (11.7-17.2) | 3.6% (2.3-5.0) | 92.3% (90.6-94.0) | 28.6% / 27.1% |
| HomeGoods | 1 | 87.9% (83.1-92.2) | 10.9% (6.3-16.2) | 2.1% (1.3-2.9) | 96.5% (95.1-97.6) | 7.4% / 6.4% |
| | 2 | 86.7% (83.6-89.7) | 12.9% (9.7-16.3) | 1.5% (0.8-2.4) | 95.1% (93.5-96.6) | 8.1% / 7.5% |
| ConstructionSuppliesMarkets | 1 | 81.2% (72.5-88.3) | 27.0% (14.1-42.8) | 10.3% (5.4-15.6) | 84.1% (76.0-91.0) | 49.6% / 49.5% |
| | 2 | 87.4% (84.6-90.0) | 16.4% (12.6-20.6) | 6.2% (3.7-9.1) | 90.1% (87.5-92.5) | 44.9% / 42.6% |

The corrections helped where the first round was weak: Construction's false match fell from 27% to 16%. Home goods did not move; its two rounds are within each other's intervals. In both rounds the rules give 0 to about as many products as the gold does, and few products with an item are missed; most errors are a product given the wrong item. The larger second-round sample in big strata narrows the intervals to about ±2 points overall.

First-round errors were mostly words shared across groups ("kemer" in "akü kemeri" read as a belt, "jant" in rim paint read as tyres, "Minnie Mouse" read as a computer mouse) and door hardware caught by the doors rule. The second round's remaining errors gather in a few patterns: table and chair sets coded as tables (0511102) where the guide puts sets in 0511117, non-stick and stone-coated pots coded as steel (0540301) instead of 0540314, decorative cat figures coded as pet products, brand words such as "Kitchenaid" pulling toasters and kettles into 0532101, and Ikea's kitchen category catching sink taps. These were not corrected after the second round, so the second-round figures hold for the rules as committed.
