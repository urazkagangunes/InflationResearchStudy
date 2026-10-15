import csv
import re
import requests
from bs4 import BeautifulSoup

URL = "https://aydinhavadisleri.com/alkol-fiyatlari/"

response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

rows = []

for table in soup.find_all("table"):

    heading = table.find_previous(["h2", "h3"])
    category = heading.get_text(strip=True) if heading else ""

    if "lik Alkol" in category:
        continue

    trs = table.find_all("tr")
    if len(trs) < 2:
        continue

    header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]

    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        name = cells[0]

        if len(cells) == 3 and header[1].lower().startswith("hacim"):
            rows.append([name, cells[2], cells[1], category])

        elif len(cells) == 2:
            m = re.search(r"\d+[,.]?\d*\s*cl", header[1])
            volume = m.group(0) if m else ""
            rows.append([name, cells[1], volume, category])

        # Tip 3: ürün | 35 cl | 50 cl | 70 cl ...  (matris)
        else:
            for vol, price in zip(header[1:], cells[1:]):
                if price not in ("–", "-", ""):
                    rows.append([name, price, vol, category])

with open("alkol_fiyatlari.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["product_name", "product_price", "volume", "category"])
    writer.writerows(rows)

print(f"Bitti! {len(rows)} ürün alkol_fiyatlari.csv dosyasına yazıldı.")
