# Travel & Tourism Price Scrapers

**Student:** Batu Onlukus
**Assigned categories:** Holiday / vacation fees · Hajj and Umrah fees · Hotel prices
**Course:** AI 201 – Introduction to Data Science (Inflation Project)

This folder collects daily price data for three travel-related categories. Each
scraper is **runnable on demand** and **ready to be run daily**, but — as stated
in the task brief — it is not required to actually run every day. Running a
scraper writes one CSV for the current date.

---

## 1. Scrapers at a glance

| Category | Script | Source | Method | Output folder |
|---|---|---|---|---|
| Hotel prices | `Hotels/hotels_scraper.py` | tatilsepeti.com | Listing HTML + JSON price API | `Datas/TravelTourism/Hotels/` |
| Holiday / vacation fees | `HolidayPackages/holiday_scraper.py` | tatilsepeti.com (tours) | Server-rendered HTML | `Datas/TravelTourism/HolidayPackages/` |
| Hajj & Umrah fees | `HajjUmrah/hajj_umrah_scraper.py` | semersahturizm.com | Server-rendered HTML tables | `Datas/TravelTourism/HajjUmrah/` |

All three depend only on `requests` and `beautifulsoup4` (see `requirements.txt`).
No browser / Selenium is needed.

```bash
pip install -r requirements.txt
python Hotels/hotels_scraper.py
python HolidayPackages/holiday_scraper.py
python HajjUmrah/hajj_umrah_scraper.py
```

---

## 2. Output format

Every scraper writes a single file named `YYYY-MM-DD.csv` (today's date) into its
data folder, using **exactly the project-wide schema** — two columns, UTF-8 (BOM):

```csv
product_name,price
Adalya Elite Lara | Antalya | +30g 1gece 2yetiskin,21322.95
```

No columns are added or removed. If a scraper is run twice on the same day it
detects the existing file and exits without touching it (no duplicate data).

---

## 3. Why this is harder than a normal store — the "same basket" problem

For an inflation study we must measure the price of the **same item over time**.
For a supermarket this is trivial: "Burcu Olive Oil 200 g" is the same product
today and tomorrow. Travel prices are different — the **same** hotel room costs a
different amount depending on the check-in date, how far in advance you look, and
who is staying. If we naively scraped "hotel prices" on two days we would be
comparing two *different things* and the resulting "inflation" would be noise.

The whole design below exists to keep the basket **fixed and repeatable** so that
a day-to-day price change reflects a real price movement, not a change in what we
asked for.

---

## 4. How each scraper works

### 4.1 Hotels (`Hotels/hotels_scraper.py`)
Hotel prices are date-dependent, so the scraper queries a **fixed rolling
window** every run:

- **check-in = today + 30 days, 1 night, 2 adults** (configurable constants).

Flow:
1. `GET` each city listing page (Antalya, İstanbul, İzmir, Muğla, Nevşehir,
   Bursa). The page gives us each hotel's `data-hotelid` and `data-hotelname`
   (and the session cookies we need).
2. `POST` to the site's price endpoint `/hotel/GetHotelListPrice/` with the fixed
   basket and the hotel ids. It returns clean JSON containing `Price` and
   `DiscountPrice` per hotel.
3. We record the price actually paid (`DiscountPrice`, falling back to `Price`).

The fixed basket is encoded into `product_name`, e.g.
`Adalya Elite Lara | Antalya | +30g 1gece 2yetiskin`, so each run measures the
same thing. We deliberately **do not** put the room type in the name: the item we
track is "cheapest bookable price for this hotel on the fixed basket", and the
room type is just metadata that may vary day to day.

### 4.2 Holiday / vacation packages (`HolidayPackages/holiday_scraper.py`)
A "holiday fee" is the advertised starting price of a **named tour package**
(e.g. *Bursa Çıkışlı Karadeniz Rüyası ve Batum Turu*). Each named package is one
trackable item. The tour-listing pages render prices server-side, so a plain
`GET` + HTML parse is enough:

- each package is a `[data-tourname]` element (stable id: `data-tourid`),
- its price sits in a nearby `.discount-price` element.

We read several tour categories (culture, abroad, GAP, Black Sea, Eastern Express,
day trips), de-duplicate by tour id, and write `product_name,price`. Missing
categories (HTTP 404) are skipped gracefully.

### 4.3 Hajj & Umrah (`HajjUmrah/hajj_umrah_scraper.py`)
Umrah operators publish a **price matrix**: package duration (10 / 14 / 20 / 35
days, and seasonal variants such as *Sömestir* and *Ramazan*) × room occupancy
(4 / 3 / 2-person room). We flatten this matrix into one `product_name,price` row
per (section, duration, room) combination, so each combination is an
independently trackable item. Child/infant supplement fees are captured too.

The parser tracks the section sub-headers inside the table and ignores non-price
rows (e.g. a "%16 İndirimli" discount-rate row), keeping every item unique.

**Currency note:** Umrah packages are quoted by operators in **US dollars**, so
the `price` value here is in USD and the `product_name` carries a `(USD)` marker.
This is intentional — inflation is computed as a *within-item* percentage change,
which is currency-agnostic, and keeping the native USD quote avoids introducing
FX-conversion noise. (All other project stores are in Turkish Lira.)

---

## 5. About the "last 3 months of history" requirement

The task brief asks for the last three months of price changes **if available**,
otherwise current-price collection is sufficient. For travel categories,
historical prices are **not publicly queryable** (you cannot ask a site "what did
this hotel cost on 1 March?"). Therefore, per the brief, these scrapers collect
**current prices** and build the time series forward from the first run.

---

## 6. Folder layout

```
InflationItems/
├── Codes/TravelTourism/
│   ├── README.md                ← this file
│   ├── requirements.txt
│   ├── Hotels/hotels_scraper.py
│   ├── HolidayPackages/holiday_scraper.py
│   └── HajjUmrah/hajj_umrah_scraper.py
└── Datas/TravelTourism/
    ├── Hotels/YYYY-MM-DD.csv
    ├── HolidayPackages/YYYY-MM-DD.csv
    └── HajjUmrah/YYYY-MM-DD.csv
```

---

## 7. Typical run sizes (2026-05-30)

| Category | Items collected |
|---|---|
| Hotels (6 cities) | ~177 |
| Holiday / tour packages | ~109 |
| Hajj & Umrah packages | ~27 |
