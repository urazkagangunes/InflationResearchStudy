# Home goods (COICOP 05)

This category covers TÜİK COICOP 2026 group 05, "Mobilya, ev aletleri ve rutin ev bakımı" (furnishings, household equipment and routine household maintenance), which has a weight of 7.9201% in the 2026 basket. The index script counts every store in this folder under group 05, together with `ConstructionSuppliesMarkets`.

The basket lists 54 items for group 05. This page shows which stores we scrape, which of the 54 items they cover and where the remaining items are collected. Last updated 2026-10-07.

## Stores

| Store | Site | What is collected | Products on 2026-10-07 |
|---|---|---|---|
| Bellona | bellona.com.tr | Whole catalogue: furniture, beds, home textiles | 1,391 |
| Chakra | chakra.com.tr | Home textiles and tableware | 1,500 |
| EnglishHome | englishhome.com | Home textiles, kitchen, small appliances | 4,248 |
| Ikea | ikea.com.tr | Whole catalogue except food | 19,724 |
| Istikbal | istikbal.com.tr | Whole catalogue: furniture, beds | 1,262 |
| jysk | jysk.com.tr | Whole catalogue: furniture, bedding, textiles | 3,621 |
| Karaca | karaca.com | Whole catalogue except the food group | 20,485 |
| LCW Home | lcw.com (LCW HOME brand) | Home textiles and decor | 2,009 |
| MadameCoco | madamecoco.com | Home textiles, tableware, decor | 3,887 |
| Tchibo | tchibo.com.tr | "Ev, Yaşam & Mobilya" section | 521 |
| Vivense | vivense.com | Whole catalogue: furniture, carpets, textiles | 23,388 |
| Vestel | vestel.com.tr | White goods, ovens and hobs, air conditioners, heaters | 254 |
| MediaMarkt | mediamarkt.com.tr | Same appliance categories and batteries, only products sold by MediaMarkt itself | 541 |
| OnlineKombi | onlinekombi.com | Combi boilers, all brands on the site | 85 |
| Armut | armut.com | Monthly average quotes for five household services in İstanbul, Ankara and İzmir | 15 rows |

Vestel, MediaMarkt, OnlineKombi and Armut were added on 2026-10-07 to bring white goods, heating and cooling appliances, batteries and household services into the category, so their series start that day. EnglishHome is collected daily but the index script leaves it out (`_SKIP_STORES` in `Inflations/Codes/turkey_inflation.py`).

## Coverage of the 54 basket items

"Covered" means products for the item appear in the files of the stores listed. Products are not tagged with item codes; the table comes from searching the product names of the 2026-10-07 files and checking the matches by hand.

| Code | Item | Covered by |
|---|---|---|
| 511102 | Kitchen table | Ikea, Vivense, Bellona, jysk, Istikbal |
| 511105 | Kitchen chair | Ikea, Vivense, jysk, Istikbal, Bellona |
| 511108 | Bedroom set | Vivense, Bellona, Istikbal |
| 511111 | Bed | Vivense, Ikea, jysk, Bellona |
| 511114 | Bed base | Vivense, Bellona, Istikbal |
| 511115 | Youth room set | Vivense, Istikbal, Bellona |
| 511116 | Living room set | Ikea, Vivense, jysk, Istikbal, Bellona |
| 511117 | Dining room set | Vivense, Bellona, Istikbal |
| 511401 | Carpet (rug) | Vivense, Karaca, MadameCoco, EnglishHome, Ikea |
| 521101 | Curtains | Ikea, Vivense, jysk |
| 521102 | Roller blinds | Ikea, jysk |
| 521103 | Sheer curtains | Vivense, Ikea |
| 521201 | Bedspread | Karaca, MadameCoco, LCW Home, Ikea, jysk |
| 521204 | Duvet | jysk, Karaca, Ikea, Chakra, EnglishHome |
| 521206 | Blanket | LCW Home, MadameCoco, EnglishHome, Karaca |
| 521207 | Pique set | MadameCoco, Karaca, EnglishHome, Chakra |
| 521208 | Duvet cover set | Karaca, MadameCoco, EnglishHome, Ikea, Chakra |
| 521209 | Pillow | Karaca, jysk, MadameCoco, Vivense, Ikea |
| 521307 | Towel | MadameCoco, Karaca, EnglishHome, Chakra, jysk |
| 521904 | Bath mat | Vivense, LCW Home, MadameCoco, Ikea, Karaca |
| 521905 | Other home textiles | Karaca, Vivense, MadameCoco, LCW Home, Ikea |
| 531101 | Refrigerator | Vestel, MediaMarkt |
| 531103 | Deep freezer | Vestel, MediaMarkt |
| 531106 | Dishwasher | Vestel, MediaMarkt |
| 531108 | Ovens and cookers | Vestel, MediaMarkt |
| 531201 | Washing machine | Vestel, MediaMarkt |
| 531202 | Dryer | Vestel, MediaMarkt |
| 531301 | Air conditioner | Vestel, MediaMarkt |
| 531303 | Stove heater | Vestel, MediaMarkt (electric heaters only) |
| 531306 | Combi boiler | OnlineKombi |
| 531401 | Vacuum cleaner | Karaca |
| 532101 | Food processors and blenders | Karaca, EnglishHome |
| 532102 | Small electric appliances | Karaca, EnglishHome |
| 532201 | Electric tea maker | Karaca, EnglishHome |
| 532901 | Iron | Karaca, EnglishHome |
| 533001 | Repair of household appliances | Armut (washing machine repair, combi boiler repair) |
| 540102 | Glass household utensils | Karaca, Vivense, EnglishHome, Ikea, LCW Home |
| 540104 | Porcelain household utensils | Karaca, EnglishHome, MadameCoco, LCW Home, Ikea |
| 540201 | Steel cutlery set | Karaca, EnglishHome, Ikea |
| 540301 | Steel kitchenware | Karaca, EnglishHome, MadameCoco, Ikea |
| 540314 | Non-stick kitchenware | Karaca, EnglishHome |
| 540316 | Thermos | Karaca, EnglishHome, Ikea |
| 552201 | Battery | MediaMarkt, Ikea |
| 552203 | Light bulb | Ikea |
| 561101 | Laundry cleaning and care products | `Markets` (supermarket scrapers) |
| 561102 | Dishwashing cleaning and care products | `Markets` (supermarket scrapers) |
| 561103 | Floor hygiene cleaning and care products | `Markets` (supermarket scrapers) |
| 561106 | Cleaning cloths | Ikea, Tchibo, Karaca |
| 561198 | Surface cleaning towel and wipes | `Markets` (supermarket scrapers) |
| 561902 | Storage and preservation materials | `Markets` (supermarket scrapers) |
| 561903 | Paper tableware | EnglishHome, LCW Home, Karaca, jysk |
| 561915 | Other non-durable household goods | `Markets` (supermarket scrapers) |
| 562901 | Household maintenance and repair services | Armut (sofa cleaning, carpet cleaning) |
| 562902 | Maid and cleaners' fee | Armut (house cleaning) |

All 54 items have a source in the repository: 48 are collected by the stores in this folder, and the remaining six, household cleaning products and similar consumables, by the supermarket scrapers in `Markets`.

## Notes on the data

The six items collected under `Markets` are supermarket goods. The index script assigns each folder to one group as a whole, so in the current index these products count towards group 01; counting them under 05 would need a product-level mapping in the index script.

The stove heater item is represented by electric heaters from Vestel and MediaMarkt.

No retailer or official tariff publishes prices for the three service items on the web, so they come from Armut's price pages, which report the average quote that service providers gave in each month. The scraper takes the month two months before the run date, because the newest month shown on a page can differ between requests; the service series therefore change once a month. Only services with hundreds of quotes a month are used, so that the averages are stable.

From MediaMarkt only products sold by MediaMarkt itself are kept, so that the series follows one retailer's own prices rather than changing third-party offers (541 of 1,763 listed products on 2026-10-07). Battery chargers and camera battery packs are left out of the battery category.

## How the data is produced

All stores are scraped every night on a dedicated server, except MadameCoco, whose site refuses the server's IP address and which therefore runs from a team member's computer. If the night run of Vivense finds the site's lists incomplete, it is repeated at noon. Any scraper can also be run on its own:

```bash
python "InflationItems/Codes/HomeGoods/<Store>/<scraper>.py"
```

Each scraper writes one file per day to `InflationItems/Datas/HomeGoods/<Store>/`, with the date in the file name as `YYYY-MM-DD` and two columns, `product_name` and `price`. The price is the one a buyer pays that day, without membership or campaign codes. Each scraper compares what it collected with the product count the site itself shows and writes no file when too much is missing: most require 98%, Bellona and Istikbal every product, Vivense 90% per category, MediaMarkt 90% per category and 98% overall (its category pages disagree on their own counts from one page to the next). Armut shows no such count, so its scraper writes no file if any of its pages fails. A missing file therefore means the day failed, not that prices were unchanged. The scrapers added in October read `robots.txt` and follow its rules.
