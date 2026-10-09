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

def get_hidden_fields(soup):
    return {tag["name"]: tag.get("value", "")
            for tag in soup.find_all("input", type="hidden")}

def fetch_page_with_vehicle_type(vehicle_type):
    if vehicle_type == "MİNİBÜS":
        resp = session.get(BASE_URL)
    else:
        resp = session.get(BASE_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        hidden = get_hidden_fields(soup)

        post_data = hidden.copy()
        post_data["__EVENTTARGET"] = "CarTypeSelect"
        post_data["__EVENTARGUMENT"] = ""
        post_data["CarTypeSelect"] = vehicle_type

        headers = {}
        if "__ASYNCPOST" in hidden:
            post_data["__ASYNCPOST"] = "true"
            headers["X-MicrosoftAjax"] = "Delta=true"

        resp = session.post(BASE_URL, data=post_data, headers=headers)

    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    hidden = get_hidden_fields(soup)
    return soup, hidden

def scrape_routes(soup, hidden, vehicle_type):

    dropdown = soup.find("select", {"name": lambda n: n and "UcretSelect" in n})
    if not dropdown:
        for s in soup.find_all("select"):
            if any(o.get("value", "").strip().isdigit() for o in s.find_all("option")):
                dropdown = s
                break
    if not dropdown:
        raise ValueError("Route dropdown not found.")
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

        print(f"  [{vehicle_type}] Processing route: {opt_text} (value={opt_val})")

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
            print(f"    Warning: no price table for {opt_text}")
            continue

        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            if len(cols) == 2:
                binis_inis = cols[0].get_text(strip=True)
                ucret = cols[1].get_text(strip=True)
            else:
                binis = cols[0].get_text(strip=True)
                inis = cols[1].get_text(strip=True)
                binis_inis = f"{binis}  //  {inis}"
                ucret = cols[2].get_text(strip=True)

            ucret = ucret.replace("\xa0", " ").strip()
            all_prices.append([opt_text, ucret])

        time.sleep(0.5)

    return all_prices
all_rows = []

soup, hidden = fetch_page_with_vehicle_type("TAKSİ DOLMUŞ")
taxi_data = scrape_routes(soup, hidden, "TAKSİ DOLMUŞ")
all_rows.extend(taxi_data)

if all_rows:
    filename = f"Datas\\taxi_prices_{datetime.date.today().month}-{datetime.date.today().day}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Güzergah","Ücret"])
        writer.writerows(all_rows)
    print(f"Saved {len(all_rows)} rows to {filename}")
else:
    print("No data collected.")
