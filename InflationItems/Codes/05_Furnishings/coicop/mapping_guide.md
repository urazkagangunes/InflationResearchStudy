# Mapping guide: products to TÜİK 2026 basket items

This guide defines which basket item a product belongs to. The rules in `rules.py` implement it, and the validation sample is labelled against it. Codes and item names are from TÜİK's 2026 CPI basket (CPI methodological notes, Appendix 1, pp. 40-54); `basket_2026.csv` holds all 428 items.

## Principle

A product gets the basket item that matches it, as long as the match is not far-fetched. When the basket has no item for the exact product type, the closest item in the same COICOP subclass (5 digits) or the same family of products is used. A product gets 0 only when nothing in the basket is a sensible stand-in, for example a vase or a drill. Products outside group 05 get their own group's item: paint is 04, toys are 09, hair dryers are 13.

`sub_category_number` is the 7-digit item code as printed in the PDF, leading zero included. `category_number` is its first two digits. A product with no item gets 0 in both.

## Group 05

### Furniture (05111) and carpets (05114)

| Code | Item | Includes |
|---|---|---|
| 0511102 | Kitchen table | kitchen and dining tables sold on their own, bar and bistro tables, folding tables, table legs and tops; kitchen cabinets, kitchen modules, fitted kitchens, worktops and kitchen cabinet fronts |
| 0511105 | Kitchen chair | chairs, stools, bar stools, benches for the table |
| 0511108 | Bedroom set | bedroom sets, wardrobes and wardrobe parts, chests of drawers (şifonyer), bedside tables (komodin), dressing tables, cabinets sold as "N kapaklı dolap" |
| 0511111 | Bed | mattresses (yatak), bed frames (karyola), divans |
| 0511114 | Bed base | bed bases (baza), headboards, base and headboard sets |
| 0511115 | Youth room set | youth, children's and baby room furniture, bunk beds, cribs, study and office desks and chairs, gaming desks and chairs, drawer units for desks |
| 0511116 | Living room set | sofa sets, corner sofas, sofas, armchairs, berjer, ottomans, coffee and side tables, TV units, bookcases, wall shelves and shelving units, shoe cabinets, hall stands, other cabinets |
| 0511117 | Dining room set | dining room sets, table and chair sets, consoles, sideboards (büfe), display cabinets (vitrin) |
| 0511401 | Carpet (rug) | carpets, rugs, kilims, runners, door mats, sheepskin rugs, floor protectors for chairs |

Garden furniture has no item of its own: garden chairs and loungers go to 0511105, garden tables to 0511102, garden sofas, seating sets, swings, gazebos and garden umbrellas to 0511116. Bathroom cabinets go to 0431108 with sanitary ware.

### Household textiles (052)

| Code | Item | Includes |
|---|---|---|
| 0521101 | Curtains | curtains, blackout curtains, shower curtains, mosquito nets, curtain rails and rods |
| 0521102 | Roller blinds | roller, zebra, pleated, bamboo and vertical blinds, venetian blinds |
| 0521103 | Sheer curtains | tül |
| 0521201 | Bedspread | bedspreads, quilted covers, bedspread sets |
| 0521204 | Duvet | yorgan, duvet and pillow sets |
| 0521206 | Blanket | blankets, fleece and TV blankets, throws sold as örtü |
| 0521207 | Pique set | pike, pique sets, muslin covers |
| 0521208 | Duvet cover set | duvet cover sets, sheets, fitted sheets, pillowcases, mattress protectors, dowry sets |
| 0521209 | Pillow | sleeping pillows, orthopaedic and neck pillows |
| 0521307 | Towel | towels, bath, hand, face and kitchen towels, peshtemal, tea towels, bathrobes |
| 0521904 | Bath mat | bath mats, toilet mat sets |
| 0521905 | Other home textiles | cushions and cushion covers, seat pads, sofa throws and covers, chair and furniture covers, tablecloths, runners, placemats, coasters, fabric napkins, aprons, oven gloves, fabric by the metre |

### Household appliances (053)

| Code | Item | Includes |
|---|---|---|
| 0531101 | Refrigerator | refrigerators, mini fridges, wine and drink coolers |
| 0531103 | Deep freezer | upright and chest freezers |
| 0531106 | Dishwasher | dishwashers |
| 0531108 | Ovens and cookers | ovens, built-in ovens, hobs, cookers, mini ovens, microwaves, cooker hoods, barbecues and grills |
| 0531201 | Washing machine | washing machines, washer dryers |
| 0531202 | Dryer | tumble dryers |
| 0531301 | Air conditioner | air conditioners, fans, air coolers, dehumidifiers, humidifiers, air purifiers, ventilation fans |
| 0531303 | Stove heater | stoves, electric heaters, oil radiators, convectors, infrared and patio heaters, fireplaces |
| 0531306 | Combi boiler | combi boilers, water heaters (şofben, termosifon), panel radiators, heat pumps |
| 0531401 | Vacuum cleaner | vacuum cleaners of every kind, robot vacuums and their parts, steam cleaners, carpet washers, window vacuums, pressure washers |
| 0532101 | Food processors and blenders | blenders, food processors, choppers, mixers, juicers, meat mincers |
| 0532102 | Small electric appliances | toasters, air fryers, deep fryers, waffle and crêpe makers, multicookers, rice and egg cookers, yoghurt and bread makers, electric grills, kitchen scales, vacuum sealers |
| 0532201 | Electric tea maker | tea makers, coffee machines, kettles, milk frothers |
| 0532901 | Iron | irons, steam stations, garment steamers, ironing boards and their covers, lint removers, iron spare parts |
| 0533001 | Repair of household appliances | appliance and boiler repair services |

### Glassware, tableware and utensils (054)

| Code | Item | Includes |
|---|---|---|
| 0540102 | Glass household utensils | glasses, stemware, jugs, carafes, glass bowls, plates, jars and storage containers, French presses, glass bottles |
| 0540104 | Porcelain household utensils | porcelain, ceramic, stoneware and melamine tableware: plates, bowls, cups, mugs, dinner and breakfast sets, tea and coffee sets, serving plates, teapots, cake stands |
| 0540201 | Steel cutlery set | cutlery sets, forks, spoons, kitchen knives and knife blocks |
| 0540301 | Steel kitchenware | steel pots and pans, pressure cookers, Turkish coffee pots, teapots, and the rest of the kitchen utensils: ladles, graters, strainers, chopping boards, trays, storage containers, spice racks, bread bins, lunch boxes; household storage and organisers: storage boxes, baskets, laundry baskets, drying racks, hangers, organisers, waste bins |
| 0540314 | Non-stick kitchenware | non-stick, granite, ceramic-coated, titanium and cast iron pans and pots, woks, baking moulds; frying pans of unstated material |
| 0540316 | Thermos | vacuum flasks, travel mugs, water bottles |

### Tools and accessories (055)

| Code | Item | Includes |
|---|---|---|
| 0552201 | Battery | household batteries (AA, AAA, button cells), rechargeable batteries and their chargers; power-tool batteries and chargers are tools (0) |
| 0552203 | Light bulb | light bulbs, LED lamps, fluorescent tubes; and lighting: chandeliers, floor, table and wall lamps, spotlights, LED panels, floodlights, LED strips, string lights, torches |

Hand tools, power tools and their accessories (drill bits, discs, blades, batteries, chargers), garden tools, water pumps, generators and ladders are 0: COICOP puts them in 05.5.1 and 05.5.2.1, which have no basket item.

### Routine household maintenance (056)

| Code | Item | Includes |
|---|---|---|
| 0561101 | Laundry cleaning and care products | detergents, softeners, stain removers |
| 0561102 | Dishwashing cleaning and care products | washing-up liquid, dishwasher tablets, rinse aid, salt |
| 0561103 | Floor hygiene cleaning and care products | surface, floor, bathroom, kitchen, glass and toilet cleaners, bleach (çamaşır suyu), descalers, drain openers, furniture polish, disinfectants |
| 0561106 | Cleaning cloths | cleaning cloths, microfibre cloths, sponges, scourers, mops, squeegees, dusters |
| 0561198 | Surface cleaning towel and wipes | surface cleaning wipes |
| 0561902 | Storage and preservation materials | cling film, foil, freezer and storage bags, baking paper |
| 0561903 | Paper tableware | paper towels, paper napkins, disposable plates and cups |
| 0561915 | Other non-durable household goods | bin bags, candles, matches, lighters, room fragrances and diffusers, insect repellents, shoe care, vacuum bags, clothes pegs, brooms, dustpans, toilet and dish brushes, household gloves, coffee filter paper |
| 0562901 | Household maintenance and repair services | carpet and sofa cleaning services |
| 0562902 | Maid and cleaners' fee | house cleaning services |

## Group 04: dwelling maintenance and repair

COICOP 04.3.1 covers "paints and varnishes, renderings, wallpapers, fabric wall coverings, windowpanes, plaster, cement, putty, wallpaper pastes", "small plumbing items (pipes, taps, joints, etc.), surfacing materials (floorboards, ceramic tiles, etc.) and brushes and scrapers for paint", fitted carpets, "door fittings, power sockets and wiring flex", small security equipment and fire extinguishers; hand tools and lamp bulbs are outside it.

| Code | Item | Includes |
|---|---|---|
| 0431101 | Paint and coating materials | wall, wood and metal paints, primers, varnishes, thinners, spray paints, anti-rust; paint brushes, rollers, trays, extension poles, masking tape, protective sheets for painting (spray guns and paint mixers are tools, 0) |
| 0431102 | Floor and wall covering materials | ceramic and porcelain tiles, parquet, laminate, vinyl flooring, wallpaper, wall panels, skirting, mosaics, fitted carpet, ceiling tiles, mouldings |
| 0431106 | PVC door and window materials | doors, windows, PVC joinery, insect screens, shutters |
| 0431108 | Plumbing materials | taps, mixers, pipes and fittings, valves, siphons, drains, showers and shower cabins, toilets, cisterns, basins, sinks, bathtubs, water filters; bathroom cabinets and bathroom accessories (soap dishes, towel rails, toilet roll holders, shelves) |
| 0431109 | Other materials for maintenance and repair of household | cement, plaster, mortar, render, adhesives, silicone, sealants, foam, insulation, membranes, boards (MDF, OSB, plywood), timber, profiles, roofing, glass; door and furniture fittings (handles, hinges, locks, drawer runners), screws, bolts, dowels, nails, chains, brackets; power sockets, switches, cables, fuses, junction boxes and other electrical fittings; smoke and gas detectors, alarms, cameras, door phones, fire extinguishers |
| 0452201 | LPG cylinders | camping gas, gas cartridges |
| 0454101 | Coal | coal, charcoal |
| 0454201 | Firewood | firewood, pellets, kindling |

## Other groups

| Group | Items used | Examples |
|---|---|---|
| 01 | 0122011 Coffee, 0122012 Instant coffee, 0123021 Tea | coffee beans, ground and capsule coffee, tea |
| 03 | pyjamas, socks, slippers, work clothing and boots, scarves, belts | women's items when the gender is not stated; work jackets 0312105, work trousers 0312110, safety shoes and boots 0321102 |
| 07 | 0713001 Bicycle, 0721101 Vehicle tyres, 0721201 Vehicle spare parts, 0721302 Vehicle accessories, 0722401 Motor oils | wipers, car batteries, car care products, snow chains, antifreeze |
| 08 | 0814001 Audio-video equipment, 0814007 Television, 0813209 Computer peripherals, 0819201 Info-communication accessories | speakers, phone chargers and cases, USB hubs |
| 09 | 0921204 Other toys, 0921207 Ride-on toys, 0922102 Home fitness, 0922103 Sports equipment, 0932201 Pet food, 0932204 Other pet products, 0974xxx stationery | toys and Christmas decorations, camping and picnic gear, cool bags, pet beds and bowls, art and hobby paints (0974004), gift bags and wrapping (0974009) |
| 13 | personal care appliances and products, 1321105 Wristwatch, 1329101 Travel goods, 1329104 Women's handbag, 1329106 School bag, 1329114 Baby stroller, 1329129 Baby diapers | hair dryers, bathroom scales, soap, shampoo, toilet paper, personal wet wipes, wall and table clocks, suitcases, travel pillows and umbrellas (garden umbrellas are 0511116) |

## Products that get 0

- Decor: vases, frames, pictures, posters, figurines, artificial flowers, candle holders, mirrors (the only item in their subclass 05114 is carpet).
- Hand tools, power tools and their accessories, garden tools, ladders, welding equipment, measuring tools.
- Garden products: plants, seeds, soil, fertiliser, pots, hoses, irrigation.
- Work safety equipment other than clothing and footwear: gloves, helmets, goggles, masks, ear protection.
- Industrial parts with no household use, such as V-belts.
- Products whose type cannot be told from the name and the site category.

## Cases settled by the first validation

The two labellers of the 2026-10-17 run split on these; the codes below are the ones the adjudication and the rules use.

| Product | Code |
|---|---|
| Raincoats and work rainwear | 0312105 |
| Socks sold under work-safety categories | 0312131 |
| Robes and ponchos sold under bathrobe categories | 0521307 |
| Lunch boxes and lunch bags | 0540301 |
| Dresser consoles (dresuar), coffee corners | 0511117 |
| High chairs, changing tables | 0511115 |
| Laptop stands and supports | 0819201 |
| Staples sold by hardware stores; office staplers and staples elsewhere | 0431109; 0974009 |
| Lubricating and rust-removing sprays (WD-40, grease) | 0431109 |
| Self-adhesive decorative film (D-C Fix) | 0431102 |
| Two-stroke engine oil | 0722401 |
| Lamp shades | 0552203 |
