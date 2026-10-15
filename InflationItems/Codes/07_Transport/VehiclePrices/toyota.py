"""Toyota binek fiyat listesi; kurulum: ARAC_FIYATLARI_README.md."""
from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from transport_common import parse_price

URL = 'https://turkiye.toyota.com.tr/middle/fiyat-listesi/'
MODELS = {
    'Corolla': 'Corolla', 'CorollaHybrid': 'Corolla Hybrid',
    'YeniCorollacrosssHybrid': 'Corolla Cross Hybrid', 'CHRHybrid': 'Toyota C-HR Hybrid',
    'CorollaHBHybrid': 'Corolla Hatchback Hybrid', 'YarisCrossHybrid': 'Yeni Yaris Cross Hybrid',
    'YarisHybrid': 'Yaris Hybrid',
}




def parse_table(cells, model, year, stamp, url):
    headers = [re.sub(r'\s+', ' ', h).lower() for h in cells[0]]
    def column(word):
        return next((i for i, h in enumerate(headers) if word in h), None)
    vi, li, ci = column('versiyon'), column('liste'), column('kampanyal')
    price_type = 'list'
    if li is None:
        li = next((i for i, h in enumerate(headers)
                   if 'hybrid' in h and 'ötv' in h and 'fiyat' in h and 'kampanyal' not in h), None)
        price_type = 'recommended_hybrid'
    if vi is None or li is None:
        raise ValueError(f'{model}: tablo basliklari degisti.')
    records = []
    for row in cells[1:]:
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f'{model}: sutun sayisi uyusmuyor.')
        version = re.sub(r'\s+', ' ', row[vi]).strip()
        price = parse_price(row[li])
        if not version or price is None:
            raise ValueError(f'{model}: eksik versiyon veya fiyat.')
        campaign = parse_price(row[ci]) if ci is not None else None
        records.append(dict(product_name=f"Toyota {model.removeprefix('Toyota ')} | {year} | {version}",
                            price=price, campaign_price=campaign or '', model_year=year,
                            collected_at=stamp, price_type=price_type,
                            price_label=re.sub(r'\s+', ' ', cells[0][li]).strip(), source_url=url))
    if not records:
        raise ValueError(f'{model}: fiyat tablosu bos.')
    return records


def collect(only_model=None, headed=False):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    except ImportError as exc:
        raise RuntimeError('Playwright kurulu degil; ARAC_FIYATLARI_README.md dosyasina bakin.') from exc
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    result = []
    models = {only_model: MODELS[only_model]} if only_model else MODELS
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(locale='tr-TR', timezone_id='Europe/Istanbul')
            page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            reject = page.locator('#onetrust-reject-all-handler')
            try:
                reject.wait_for(state='visible', timeout=5000)
            except BrowserTimeout:
                pass
            else:
                reject.click()
            for key, name in models.items():
                print(f'Okunuyor: {name}', flush=True)
                button = page.locator(f'#btnModel_{key}')
                button.wait_for(state='visible', timeout=20000)
                if button.get_attribute('aria-expanded') != 'true':
                    button.click()
                # Modele ait acik yil paneli; muafiyet ve boya tablolari haric.
                panels = page.locator(f'[id^="content-{key}-"]:visible')
                panels.first.wait_for(state='visible', timeout=20000)
                found = []
                for panel in panels.all():
                    match = re.fullmatch(rf'content-{re.escape(key)}-(\d{{4}})', panel.get_attribute('id') or '')
                    if not match:
                        continue
                    tables = panel.locator('table:visible')
                    tables.first.wait_for(state='visible', timeout=20000)
                    for table in tables.all():
                        cells = table.locator('tr').evaluate_all(
                            "rows => rows.map(r => Array.from(r.querySelectorAll('th,td'), c => c.innerText.trim()))")
                        if cells and any('versiyon' in c.lower() for c in cells[0]):
                            found.extend(parse_table(cells, name, match[1], now.isoformat(timespec='seconds'), page.url))
                if not found:
                    raise ValueError(f'{name}: standart fiyatlar bulunamadi; CSV yazilmadi.')
                result.extend(found)
        finally:
            browser.close()
    names = [r['product_name'] for r in result]
    if len(names) != len(set(names)):
        raise ValueError('Tekrarlanan versiyonlar bulundu; CSV yazilmadi.')
    return sorted(result, key=lambda r: r['product_name']), now.date().isoformat()
