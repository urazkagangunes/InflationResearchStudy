"""Honda motosiklet tavsiye edilen satis fiyatlari, 2025 ve 2026 model yillari."""
from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from transport_common import parse_price

YEARS = ('2025', '2026')
BASE = 'https://www.honda.com.tr/motosiklet/motosiklet-fiyat-listesi-'


def parse_items(items, year, stamp, url):
    rows = []
    for item in items:
        pack = re.sub(r'\s+', ' ', item.get('pack') or '').strip()
        model = re.sub(r'\s+', ' ', item.get('model') or '').strip()
        if not pack or item.get('label') != 'Tavsiye edilen satış fiyatı':
            raise ValueError(f'{year}: model/versiyon veya fiyat basligi eksik.')
        if not model:
            model, pack = pack, 'Standart'
        price = parse_price(item.get('price') or '')
        if price is None:
            raise ValueError(f'{model} {pack}: fiyat eksik.')
        rows.append(dict(product_name=f'Honda {model} | {year} | {pack}', price=price,
                         campaign_price='', model_year=year, collected_at=stamp,
                         price_type='recommended_retail', price_label=item['label'], source_url=url))
    if not rows or len({r['product_name'] for r in rows}) != len(rows):
        raise ValueError(f'{year}: bos/tekrarlanan fiyat kayitlari.')
    return rows


def collect(headed=False):
    from playwright.sync_api import sync_playwright
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    result = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(locale='tr-TR', timezone_id='Europe/Istanbul')
            for year in YEARS:
                url = BASE + year
                # Tam sayfa gezintisi: istemci sekme gecisinde onceki yilin verisi kalabilir.
                page.goto(url, wait_until='networkidle', timeout=60000)
                page.get_by_role('heading', name=f'Fiyat Listesi - {year} Model Yılı', exact=True).wait_for(timeout=30000)
                page.locator('li.tpl__item').first.wait_for(state='attached', timeout=30000)
                items = page.locator('li.tpl__item').evaluate_all('''es => es.map(e => ({
                    model: e.closest('.tpl__cycle-model-wrapper')?.querySelector('.tpl__model-name')?.textContent.trim() || '',
                    pack: e.querySelector('.tpl__pack-name')?.textContent.trim() || '',
                    label: e.querySelector('.dtl__text p')?.textContent.trim() || '',
                    price: e.querySelector('.dtl__text span')?.textContent.trim() || ''
                }))''')
                rows = parse_items(items, year, now.isoformat(timespec='seconds'), page.url)
                print(f'{year} model yili: {len(rows)} fiyat kaydi', flush=True)
                result.extend(rows)
        finally:
            browser.close()
    return sorted(result, key=lambda r: r['product_name']), now
