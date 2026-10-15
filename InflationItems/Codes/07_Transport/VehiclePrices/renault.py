"""Renault resmi binek fiyat tablolari; opsiyonlar ve dizel haric."""
from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from transport_common import parse_price

PARENT_URL = 'https://www.renault.com.tr/renault-fiyat-listeleri/binek-arac-fiyat-listesi.html'
URL = 'https://best.renault.com.tr/fiyat-listesi/?kat=Binek'


def parse_tables(tables, stamp):
    records = []
    for table in tables:
        model, headers, rows = table['model'], table['headers'], table['rows']
        if not model or not headers or not rows:
            raise ValueError('Model adi veya fiyat tablosu eksik.')
        columns = []
        for i, text in enumerate(headers[1:], 1):
            year = re.search(r'\b(20\d{2})\s+Model', text)
            if not year or ('Liste' not in text and 'Kampanyal' not in text):
                raise ValueError(f'{model}: taninmayan fiyat basligi: {text}')
            columns.append((i, year[1], 'campaign' if 'Kampanyal' in text else 'list', text))
        years = sorted({year for _, year, kind, _ in columns if kind == 'list'})
        if not years:
            raise ValueError(f'{model}: liste fiyati sutunu yok.')
        for cells in rows:
            if len(cells) != len(headers) or not cells[0].strip():
                raise ValueError(f'{model}: fiyat satiri yapisi degisti.')
            version = re.sub(r'\s+', ' ', cells[0]).strip()
            if re.search(r'\bdci\b', version, flags=re.I):
                continue
            for year in years:
                indexes = [(i, kind, label) for i, y, kind, label in columns if y == year]
                list_cols = [(i, label) for i, kind, label in indexes if kind == 'list']
                campaign_cols = [i for i, kind, _ in indexes if kind == 'campaign']
                if len(list_cols) != 1 or len(campaign_cols) > 1:
                    raise ValueError(f'{model}: belirsiz fiyat sutunlari.')
                price = parse_price(cells[list_cols[0][0]])
                if price is None:
                    raise ValueError(f'{model} {version}: liste fiyati yok; kaydedilmedi.')
                campaign = parse_price(cells[campaign_cols[0]]) if campaign_cols else None
                records.append(dict(product_name=f'Renault {model} | {year} | {version}',
                                    price=price, campaign_price=campaign or '', model_year=year,
                                    collected_at=stamp, price_type='list',
                                    price_label=re.sub(r'\s+', ' ', list_cols[0][1]).strip(), source_url=URL))
    if not records or len({r['product_name'] for r in records}) != len(records):
        raise ValueError('Bos veya tekrarlanan fiyat kayitlari; kaydedilmedi.')
    return sorted(records, key=lambda r: r['product_name'])


def collect(headed=False):
    from playwright.sync_api import sync_playwright
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(locale='tr-TR', timezone_id='Europe/Istanbul')
            page.goto(URL, wait_until='networkidle', timeout=60000)
            page.locator('table.price-table').first.wait_for(state='visible', timeout=30000)
            # H2 model basligini izleyen fiyat tablosu; options-table okunmaz.
            tables = page.locator('h2.model-title, table.price-table').evaluate_all('''elements => {
                let model = ''; const result = [];
                for (const el of elements) {
                    if (el.matches('h2.model-title')) { model = el.innerText.trim(); continue; }
                    result.push({model,
                        headers: Array.from(el.querySelectorAll('thead th'), c => c.innerText.trim()),
                        rows: Array.from(el.querySelectorAll('tbody tr'),
                            r => Array.from(r.querySelectorAll('td'), c => c.innerText.trim()))});
                }
                return result;
            }''')
            titles = page.locator('h2.model-title').all_inner_texts()
            if len(tables) != len(titles) or {t['model'] for t in tables} != set(titles):
                raise ValueError('Bazi modellerin fiyat tablosu eksik; kaydedilmedi.')
            print(f'Okunan model tablosu: {len(tables)}', flush=True)
            records = parse_tables(tables, now.isoformat(timespec='seconds'))
        finally:
            browser.close()
    return records, now
