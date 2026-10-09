"""
category_fetcher.py — Discovers and lists Nalburadam categories.

This module parses the main Nalburadam homepage to locate all valid
category URLs (/kategori/*).
"""

import requests
from bs4 import BeautifulSoup
import logging
import config

logger = logging.getLogger(__name__)

def fetch_categories(session=None):
    req_session = session or requests.Session()
    req_session.headers.update(config.DEFAULT_HEADERS)

    logger.info(f"Fetching categories from {config.BASE_URL}...")
    try:
        response = req_session.get(config.BASE_URL, timeout=15)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch homepage for categories: {e}")
        return []

    soup = BeautifulSoup(response.text, 'lxml')
    categories = {}
    
    # Nalburadam uses href="/kategori/NAME"
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/kategori/') and len(href.split('/')) == 3:
            slug = href.split('/')[-1]
            full_url = config.BASE_URL + href
            name = a.text.strip() or slug.replace('-', ' ').title()
            
            # Avoid duplicate or weirdly empty names
            if not categories.get(slug) or len(name) > len(categories[slug]['name']):
                categories[slug] = {
                    "id": slug,
                    "url": full_url,
                    "name": name
                }

    cat_list = list(categories.values())
    logger.info(f"Discovered {len(cat_list)} unique categories.")
    return cat_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cats = fetch_categories()
    for c in cats[:5]:
        print(c)
