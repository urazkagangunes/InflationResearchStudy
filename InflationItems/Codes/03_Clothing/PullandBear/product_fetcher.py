
import requests
import time
from config import CATALOG_V3_URL, LANGUAGE_ID, APP_ID, HEADERS, BATCH_SIZE


def get_product_ids_for_category(category_id):
    url = (
        f"{CATALOG_V3_URL}/category/{category_id}/product"
        f"?languageId={LANGUAGE_ID}&showProducts=false&priceFilter=true&appId={APP_ID}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [str(pid) for pid in data.get("productIds", [])]
    except Exception as e:
        print(f"  Error fetching product IDs for category {category_id}: {e}")
        return []


def get_products_detail(product_ids, category_id):
    all_products = []
    for i in range(0, len(product_ids), BATCH_SIZE):
        batch = product_ids[i:i + BATCH_SIZE]
        ids_str = ",".join(batch)
        url = (
            f"{CATALOG_V3_URL}/productsArray"
            f"?languageId={LANGUAGE_ID}&productIds={ids_str}&categoryId={category_id}&appId={APP_ID}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            all_products.extend(data.get("products", []))
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error fetching products batch: {e}")
    return all_products


def extract_name_price(product):
    if not product or not isinstance(product, dict):
        return None
    name = (product.get("name") or "").strip()
    try:
        summaries = product.get("bundleProductSummaries") or []
        if not summaries:
            return None
        colors = (summaries[0].get("detail") or {}).get("colors") or []
        for color in colors:
            for size in (color.get("sizes") or []):
                if size.get("isBuyable", False):
                    price_cents = size.get("price")
                    if price_cents is not None:
                        return {"name": name, "price": int(price_cents) / 100}
        for color in colors:
            for size in (color.get("sizes") or []):
                price_cents = size.get("price")
                if price_cents is not None:
                    return {"name": name, "price": int(price_cents) / 100}
    except Exception:
        pass
    return None
