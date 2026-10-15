"""Mondial tam perakende fiyatlari. Pesinat ve taksit tutarlari alinmaz."""
from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from transport_common import parse_price

BASE = 'https://www.mondialmotor.com.tr/fiyat-listesi'
YEARS = ('2025', '2026')
TYPES = {'SCOOTER', 'ELEKTRİKLİ', 'CUB', 'TOURING', 'CROSS', 'E-BIKE'}


def parse_table(headers, cells, year, stamp, url):
    headers = [re.sub(r'\s+', ' ', h).strip() for h in headers]
    if len(headers) != 6 or headers[:3] != ['Araç Tipi', 'Model Adı', 'Renk Seçenekleri']:
        raise ValueError('Tablo basliklari degisti; fiyat kaydedilmedi.')
    if headers[3] != 'Tavsiye Edilen Perakende Satış Fiyatı' or 'Peşinat' not in headers[4] or 'Taksit' not in headers[5]:
        raise ValueError('Satis fiyati/pesinat/taksit sutunlari taninamadi.')
    records = []
    for row in cells:
        # Kategoriler arasindaki tamamen bos ayirici satirlar.
        if not any(v.strip() for v in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f'{year}: fiyat satirinda eksik sutun.')
        category, name = (re.sub(r'\s+', ' ', s).strip() for s in row[:2])
        if category not in TYPES or not name:
            raise ValueError(f'{year}: model adi/arac tipi kontrol edilmeli: {category} {name}')
        price = parse_price(row[3])
        if price is None:
            raise ValueError(f'{name}: tam satis fiyati eksik.')
        records.append(dict(product_name=f'Mondial {name} | {year} | {category}',
                            price=price, campaign_price='', model_year=year, collected_at=stamp,
                            price_type='recommended_retail', price_label=headers[3], source_url=url))
    if not records or len({r['product_name'] for r in records}) != len(records):
        raise ValueError('Bos/tekrarlanan kayit bulundu; fiyatlar kaydedilmedi.')
    return records


def collect(headed=False):
    from playwright.sync_api import sync_playwright
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(locale='tr-TR', timezone_id='Europe/Istanbul')
            for year in YEARS:
                url = BASE + '?y=' + year
                page.goto(url, wait_until='networkidle', timeout=60000)
                page.get_by_role('heading', name='Fiyat Listesi', exact=True).wait_for(timeout=30000)
                table = page.locator('table').filter(has_text='Tavsiye Edilen Perakende')
                if table.count() != 1:
                    raise ValueError('Tek fiyat tablosu bulunamadi.')
                headers = table.locator('thead th').all_text_contents()
                cells = table.locator('tbody tr').evaluate_all(
                    'es=>es.map(e=>Array.from(e.querySelectorAll("td"),c=>c.textContent.trim()))')
                rows = parse_table(headers, cells, year, now.isoformat(timespec='seconds'), page.url)
                print(f'{year} model yili: {len(rows)} fiyat kaydi', flush=True)
                records.extend(rows)
        finally:
            browser.close()
    return sorted(records, key=lambda r: r['product_name']), now
