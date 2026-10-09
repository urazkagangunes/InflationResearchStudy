import requests
from config import CATALOG_V2_URL, LANGUAGE_ID, APP_ID, HEADERS


def get_all_category_ids():
    url = f"{CATALOG_V2_URL}/category?languageId={LANGUAGE_ID}&typeCatalog=1&appId={APP_ID}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return []

    categories = []

    def walk(items):
        if not items:
            return
        for item in items:
            sub = item.get("subcategories") or item.get("subCategories") or []
            if sub:
                walk(sub)
            else:
                cid = item.get("id") or item.get("categoryId")
                if cid:
                    categories.append(str(cid))

    if isinstance(data, list):
        walk(data)
    elif isinstance(data, dict):
        walk(data.get("categories") or data.get("items") or [data])

    print(f"Found {len(categories)} categories")
    return list(set(categories))
