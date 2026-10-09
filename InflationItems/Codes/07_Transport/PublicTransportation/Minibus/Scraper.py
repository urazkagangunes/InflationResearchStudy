import requests
from bs4 import BeautifulSoup
import csv
import time
import datetime

BASE_URL = "https://application2.ibb.gov.tr/tulasim/ucrettarife.aspx?ARACTUR=1"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
})

print("Fetching initial page...")
resp = session.get(BASE_URL)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")

def get_hidden_fields(soup):
    return {tag["name"]: tag.get("value", "")
            for tag in soup.find_all("input", type="hidden")}

hidden = get_hidden_fields(soup)

dropdown = soup.find("select", {"name": lambda n: n and "UcretSelect" in n})
if not dropdown:

    all_selects = soup.find_all("select")
    for s in all_selects:
        if any(o.get("value", "").strip().isdigit() for o in s.find_all("option")):
            dropdown = s
            break
if not dropdown:
    raise ValueError("Could not find the route dropdown. Inspect the page and set its name manually.")

dropdown_name = dropdown["name"]
options = dropdown.find_all("option")

submit_name = "Search"
submit_value = "Arama"

all_prices = []

for opt in options:
    opt_val = opt.get("value", "").strip()
    opt_text = opt.get_text(strip=True)
    if not opt_val or opt_text.lower() in ["seçiniz", "seçiniz...", "lütfen seçiniz"]:
        continue

    print(f"Processing: {opt_text} (value={opt_val})")
    post_data = hidden.copy()
    post_data[dropdown_name] = opt_val
    post_data[submit_name] = submit_value
    post_data["__EVENTTARGET"] = ""
    post_data["__EVENTARGUMENT"] = ""

    headers = {}
    if "__ASYNCPOST" in hidden:
        post_data["__ASYNCPOST"] = "true"
        headers["X-MicrosoftAjax"] = "Delta=true"

    resp = session.post(BASE_URL, data=post_data, headers=headers)
    resp.raise_for_status()
    soup_resp = BeautifulSoup(resp.text, "html.parser")

    hidden = get_hidden_fields(soup_resp)

    table = soup_resp.find("table", {"id": lambda x: x and "GridView1" in x})
    if not table:
        tables = soup_resp.find_all("table")
        for t in tables:
            rows = t.find_all("tr")
            if len(rows) > 2 and all(len(row.find_all("td")) >= 2 for row in rows if row.find("td")):
                table = t
                break

    if not table:
        print(f"  Warning: no price table for {opt_text}")
        continue

    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        if len(cols) == 2:
            binis_inis = cols[0].get_text(strip=True)
            ucret = cols[1].get_text(strip=True)
        elif len(cols) >= 3:
            binis = cols[0].get_text(strip=True)
            inis = cols[1].get_text(strip=True)
            binis_inis = f"{binis}  //  {inis}"
            ucret = cols[2].get_text(strip=True)
        else:
            continue

        ucret = ucret.replace("\xa0", " ").strip()
        all_prices.append([opt_text, ucret])

    time.sleep(0.5)

if all_prices:
    filename = f"Datas/minibus_prices{datetime.date.today().month}-{datetime.date.today().day}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Güzergah", "Ücret"])
        writer.writerows(all_prices)
    print(f"Saved {len(all_prices)} rows to {filename}")
else:
    print("No data collected.")