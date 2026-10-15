"""Hyundai resmi azami liste/kampanya fiyatlari; dizel ve opsiyonlar haric."""
from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from transport_common import parse_price

URL = 'https://www.hyundai.com/tr/tr/satis/fiyat-listesi.html'


def parse_tables(tables, stamp):
    result = []
    for table in tables:
        headers, rows = table['headers'], table['rows']
        if len(headers) != 6 or not rows:
            raise ValueError('Fiyat tablosu bos veya sutun yapisi degisti.')
        expected = ['Model Yılı', 'Yakıt Tipi', 'Şanzıman Tipi',
                    'Azami / Maksimum Liste Fiyatı', 'Azami / Maksimum Kampanyalı Satış Fiyatı']
        normalized = [re.sub(r'\s+', ' ', h).strip() for h in headers]
        if normalized[1:] != expected or not normalized[0]:
            raise ValueError(f'Taninmayan fiyat tablosu basligi: {headers}')
        model = normalized[0]
        for row in rows:
            if len(row) != 6:
                raise ValueError(f'{model}: eksik fiyat satiri.')
            version, year, fuel, transmission, raw_price, raw_campaign = [v.strip() for v in row]
            if fuel == 'Dizel':
                continue
            if fuel not in ('Benzin', 'Elektrik', 'Hibrit', 'Benzin/Elektrik'):
                raise ValueError(f'{model}: yeni yakit tipi kontrol edilmeli: {fuel}')
            if not version or not transmission or not re.fullmatch(r'20\d{2}', year):
                raise ValueError(f'{model}: versiyon/model yili/sanziman eksik.')
            price, campaign = parse_price(raw_price), parse_price(raw_campaign)
            if price is None:
                raise ValueError(f'{model} {version}: liste fiyati eksik.')
            result.append(dict(product_name=f'Hyundai {model} | {year} | {version}',
                               price=price, campaign_price=campaign or '', model_year=year,
                               collected_at=stamp, price_type='maximum_list',
                               price_label=normalized[4], source_url=URL))
    if not result or len({r['product_name'] for r in result}) != len(result):
        raise ValueError('Bos/tekrarlanan kayit bulundu; CSV yazilmadi.')
    return sorted(result, key=lambda r: r['product_name'])


def collect(headed=False):
    from playwright.sync_api import sync_playwright
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(locale='tr-TR', timezone_id='Europe/Istanbul')
            page.goto(URL, wait_until='networkidle', timeout=60000)
            page.locator('tbody.rc-ModelPriceTable__body tr').first.wait_for(state='attached', timeout=30000)
            # Sadece model fiyat tablolari: acik/gizli satirlarin hepsi, yil ayri.
            tables = page.locator('table').filter(has=page.locator('tbody.rc-ModelPriceTable__body')).evaluate_all('''es => es.map(e => ({
                headers: Array.from(e.querySelectorAll('thead th'), c => c.textContent.trim()),
                rows: Array.from(e.querySelectorAll('tbody.rc-ModelPriceTable__body tr'),
                    r => Array.from(r.querySelectorAll('td'), c => c.textContent.trim()))
            }))''')
            if not tables:
                raise ValueError('Model fiyat tablosu bulunamadi.')
            print(f'Okunan model tablosu: {len(tables)}', flush=True)
            result = parse_tables(tables, now.isoformat(timespec='seconds'))
        finally:
            browser.close()
    return result, now
