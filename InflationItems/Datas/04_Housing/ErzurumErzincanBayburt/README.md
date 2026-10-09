# Erzurum / Erzincan / Bayburt - Rental Housing Data

Daily rental listing data scraped from [sahibinden.com](https://www.sahibinden.com) for the **AI 201.A Inflation Research Study** project.

**Assigned to:** Batu Koray Masak

**Category:** Emlak > Konut > Kiralık

## Folder Structure

```
ErzurumErzincanBayburt/
├── Erzurum/
│   └── Erzurum_YYYY-MM-DD.csv
├── Erzincan/
│   └── Erzincan_YYYY-MM-DD.csv
├── Bayburt/
│   └── Bayburt_YYYY-MM-DD.csv
└── README.md
```

Each city has its own subfolder. A new CSV is generated per city per day.

## CSV Format

| Column     | Example                     | Description                        |
| ---------- | --------------------------- | ---------------------------------- |
| `District` | `Palandöken / Yıldızkent`  | District / neighbourhood           |
| `Rooms`    | `3+1`                       | Room count (raw from listing)      |
| `Price`    | `16.500 TL`                 | Monthly rent in TL (raw from site) |

## Scraper

The scraper code lives at:

```
Codes/HousesRent/ErzurumErzincanBayburt/
```

See that folder's README for setup and usage instructions.

## Notes

- Data is collected daily as required by the project guidelines.
- Duplicate-looking rows (same district, rooms, price) represent distinct listings that share those attributes, not scraping errors.
- The scraper uses adaptive price bracketing to ensure all listings are captured regardless of volume.