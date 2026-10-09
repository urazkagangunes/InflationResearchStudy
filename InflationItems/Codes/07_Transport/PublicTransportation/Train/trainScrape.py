import requests
import json
import csv
import time
from datetime import datetime, date

BASE_URL = "https://ebilet.tcddtasimacilik.gov.tr"
STATIONS_URL = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json?environment=dev&userId=1"   
SEARCH_URL = f"https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1"               

TODAY = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'tr',
    'Authorization': 'eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0.eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiMDAzNDI3MmMtNTc2Yi00OTBlLWJhOTgtNTFkMzc1NWNhYjA3IiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidG1zIiwic2Vzc2lvbl9zdGF0ZSI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1tYXN0ZXIiLCJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJvcGVuaWQgZW1haWwgcHJvZmlsZSIsInNpZCI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoid2ViIiwiZ2l2ZW5fbmFtZSI6IiIsImZhbWlseV9uYW1lIjoiIn0.AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://ebilet.tcddtasimacilik.gov.tr',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1',
    'sec-ch-ua': '"Opera GX";v="131", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"iOS"',
    'unit-id': '3895',
}


session = requests.Session()
session.headers.update(headers)

print("Fetching station list...")
resp = session.get(STATIONS_URL)
resp.raise_for_status()
stations = resp.json()

station_by_id = {st["id"]: st["name"] for st in stations}
station_data_by_id = {st["id"]: st for st in stations}

print(f"Loaded {len(stations)} stations.")


valid_pairs = []

for dep_id, dep_data in station_data_by_id.items():
    dep_name = dep_data["name"]
    if "pairs" not in dep_data or not dep_data["pairs"]:
        continue
    for arr_id in dep_data["pairs"]:
        if arr_id in station_by_id:
            arr_name = station_by_id[arr_id]
            valid_pairs.append((dep_id, arr_id, dep_name, arr_name))

print(f"Total unique pair connections: {len(valid_pairs)}")

results = []

for dep_id, arr_id, dep_name, arr_name in valid_pairs:
    print(f"Searching: {dep_name} -> {arr_name}")

    payload = {
        "searchRoutes": [
            {
                "departureStationId": dep_id,
                "departureStationName": dep_name,
                "arrivalStationId": arr_id,
                "departureDate": TODAY
            }
        ],
        "passengerTypeCounts": [{"id": 0, "count": 1}],
        "searchReservation": False,
        "searchType": "DOMESTIC"
    }

    try:
        resp = session.post(SEARCH_URL, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            train_list = data.get("trainLegs") or data.get("trains") or data.get("seferListesi")
            if not train_list:
                train_list = data.get("data", {}).get("trainLegs", [])

            if train_list:
                for train in train_list:
                    fares = train.get("trainAvailabilities") or train.get("fareList") or []
                    min_price = None
                    for fare in fares:
                        price = fare.get("minPrice") or fare.get("amount")
                        if price and (min_price is None or price < min_price):
                            min_price = price

                    results.append({
                        "Departure // Arrival": dep_name+" // "+arr_name,
                        "MinimumPrice (TL)": min_price if min_price is not None else "N/A"
                    })
            else:
                print(f"  No trains found.")
        elif resp.status_code == 404:
            print(f"  Route not found (404).")
        else:
            print(f"  HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"  Error: {e}")

    time.sleep(0.3)

if results:
    filename = f"Datas\\tcdd_trains_{date.today().month}-{date.today().day}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Departure // Arrival","MinimumPrice (TL)"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved {len(results)} train options to {filename}")
else:
    print("No results collected.")
