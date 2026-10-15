"""Salcano bisiklet kategorisi, tum sayfalar. Normal gorunur tarayici."""
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import urlparse, urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from transport_common import parse_price, profile_dir

URL = 'https://www.salcano.com/urun-kategori/bisiklet/'


def parse_page(html, stamp):
    soup = BeautifulSoup(html, 'html.parser')
    count = soup.select_one('.woocommerce-result-count')
    match = re.search(r'(\d+)\s+sonuçtan', count.get_text(' ',strip=True) if count else '')
    if not match:
        raise ValueError('Kategori urun sayisi okunamadi; eksik sonuc kaydedilmedi.')
    cards = soup.select('li.product')
    if not cards:
        raise ValueError('Urun kartlari bulunamadi; site erisimi engellemis olabilir.')
    rows = []
    for card in cards:
        title = card.select_one('.woocommerce-loop-product__title')
        link = title.select_one('a[href]') if title else None
        name = re.sub(r'\s+', ' ', title.get_text(' ',strip=True)).strip() if title else ''
        amounts = card.select('.price ins .amount') or card.select('.price .amount')
        if not name or not link or len(amounts) != 1:
            raise ValueError(f'{name}: tek urun fiyati bulunamadi; fiyat araligi/eksik veri olabilir.')
        price = parse_price(amounts[0].get_text(' ',strip=True))
        source = urljoin(URL, link['href'])
        if not price or urlparse(source).hostname != 'www.salcano.com' or not urlparse(source).path.startswith('/urun/'):
            raise ValueError(f'{name}: gecersiz fiyat/urun baglantisi.')
        rows.append(dict(product_name=f'Salcano {name}', price=price, campaign_price='', model_year='',
                         collected_at=stamp, price_type='live_page_current',
                         price_label='Resmi urun listesinde gorunen satis fiyati', source_url=source))
    next_link = soup.select_one('a.next.page-numbers')
    next_url = urljoin(URL,next_link['href']) if next_link else None
    if next_url and (urlparse(next_url).hostname != 'www.salcano.com' or not re.fullmatch(r'/urun-kategori/bisiklet/page/\d+/', urlparse(next_url).path)):
        raise ValueError('Beklenmeyen sayfalama adresi.')
    return rows, int(match[1]), next_url


def collect(hidden=False):
    from playwright.sync_api import sync_playwright
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    profile = profile_dir('Salcano')
    records, visited, total = {}, set(), None
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile),headless=hidden,locale='tr-TR',timezone_id='Europe/Istanbul')
        try:
            page = context.pages[0] if context.pages else context.new_page()
            target = URL
            while target:
                if target in visited or len(visited) >= 30:
                    raise ValueError('Sayfalama siniri/dongusu; eksik sonuc kaydedilmedi.')
                visited.add(target)
                print(f'Sayfa {len(visited)} okunuyor: {target}',flush=True)
                page.goto(target,wait_until='domcontentloaded',timeout=60000)
                page.locator('li.product .price').first.wait_for(state='attached',timeout=20000)
                rows, expected, target = parse_page(page.content(),datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='seconds'))
                if total is not None and total != expected:
                    raise ValueError('Toplama sirasinda kategori urun sayisi degisti.')
                total = expected
                for row in rows:
                    key = row['source_url']
                    if key in records:
                        raise ValueError('Sayfalar arasinda tekrarlanan urun; kapsam dogrulanamadi.')
                    records[key] = row
                print(f'Biriken urun: {len(records)} / {total}',flush=True)
            if len(records) != total or len({r['product_name'] for r in records.values()}) != total:
                raise ValueError('Eksik veya ayni isimli farkli urunler var; kaydetmeden once kontrol gerekli.')
        finally:
            context.close()
    return sorted(records.values(),key=lambda r:r['product_name']),now
