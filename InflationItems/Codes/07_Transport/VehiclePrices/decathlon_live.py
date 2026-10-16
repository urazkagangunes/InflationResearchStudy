"""Gorunur tarayici ve kullanicinin tamamlayacagi guvenlik kontrolu ile Decathlon.

Guvenlik kontrolunu otomatik cozmez. Normal ayri Chromium profili kullanir.
"""
from datetime import datetime
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from transport_common import parse_price, profile_dir

URL = 'https://www.decathlon.com.tr/tum-sporlar/bisiklet/bisikletler'


def parse_html(html, stamp, require_records=True):
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.dpb-holder[data-supermodelid]')
    if not cards:
        raise ValueError('Sayfada urun kartlari yok; bos CSV uretilmedi.')
    records, excluded = [], []
    for card in cards:
        title = card.select_one('a.product-title')
        if title is None:
            raise ValueError('Urun basligi bulunamadi; dosya yapisi degismis olabilir.')
        name = re.sub(r'\s+', ' ', title.get_text(' ', strip=True)).strip()
        if 'scooter' in name.casefold() or 'bisiklet' not in name.casefold():
            excluded.append(name)
            continue
        prices = card.select('[aria-label="fiyat"]')
        if len(prices) != 1:
            raise ValueError(f'{name}: tek guncel fiyat bulunamadi.')
        price = parse_price(prices[0].get_text(' ', strip=True))
        if price is None:
            raise ValueError(f'{name}: fiyat bos.')
        url = urljoin('https://www.decathlon.com.tr', title.get('href', ''))
        if urlparse(url).hostname != 'www.decathlon.com.tr' or '/p/' not in url:
            raise ValueError(f'{name}: kaynak urun baglantisi taninamadi.')
        records.append(dict(product_name=name, price=price, campaign_price='', model_year='',
                            collected_at=stamp, price_type='live_page_current',
                            price_label='Canli urun listesinde gorunen fiyat', source_url=url))
    # Marketplace products can share a title; the collector appends the URL's
    # product code before publishing. Reject repeated identities, not titles.
    keys = []
    for row in records:
        match = re.search(r'/R-p-([^/?#]+)', row['source_url'])
        if not match:
            raise ValueError(f"Urun kodu okunamadi: {row['product_name']}")
        keys.append((row['product_name'], match[1]))
    if (require_records and not records) or len(set(keys)) != len(keys):
        raise ValueError('Bos/tekrarlanan urun kimligi; birlestirmeden once kontrol edilmeli.')
    next_link = soup.select_one('link[rel="next"]')
    return sorted(records, key=lambda r: r['product_name']), excluded, next_link.get('href') if next_link else None


def safe_next(value):
    target = urljoin(URL, value)
    parsed = urlparse(target)
    if parsed.scheme != 'https' or parsed.hostname != 'www.decathlon.com.tr' or parsed.path != urlparse(URL).path:
        raise ValueError('Beklenmeyen sonraki sayfa baglantisi; islem durduruldu.')
    return target


def wait_products(page, seconds):
    from playwright.sync_api import TimeoutError as BrowserTimeout
    deadline = time.monotonic() + seconds
    notice = False
    while time.monotonic() < deadline:
        if page.is_closed():
            raise ValueError('Tarayici kapatildi; fiyatlar kaydedilmedi.')
        try:
            page.locator('.dpb-holder[data-supermodelid]').first.wait_for(state='attached', timeout=5000)
            page.wait_for_function('''() => {
                const cards = [...document.querySelectorAll('.dpb-holder[data-supermodelid]')];
                return cards.length > 0 && cards.every(c => c.querySelector('a.product-title') && c.querySelector('[aria-label="fiyat"]'));
            }''', timeout=15000)
            return
        except BrowserTimeout:
            if not notice:
                print('KULLANICI ISLEMI: Acilan tarayicida guvenlik dogrulamasi varsa siz tamamlayin.', flush=True)
                print('Giris yapmak veya dosya kaydetmek gerekmiyor. Urunler acilinca program devam edecek.', flush=True)
                notice = True
    raise ValueError('Urunler bekleme suresinde acilmadi. Guvenlik kontrolu veya baglanti sorunu olabilir.')


def collect(wait_seconds=300, max_pages=30):
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    profile = profile_dir('Decathlon')
    profile.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo('Europe/Istanbul'))
    visited, raw_products, records, exclusions = set(), set(), {}, set()
    total = None
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile), headless=False,
                    locale='tr-TR', timezone_id='Europe/Istanbul', viewport={'width':1280,'height':900})
        try:
            page = context.pages[0] if context.pages else context.new_page()
            target = URL
            while target:
                if target in visited or len(visited) >= max_pages:
                    raise ValueError('Sayfalama dongusu/siniri; eksik sonuc kaydedilmedi.')
                visited.add(target)
                print(f'Sayfa {len(visited)} aciliyor: {target}', flush=True)
                try:
                    page.goto(target, wait_until='domcontentloaded', timeout=45000)
                except BrowserTimeout:
                    print('Sayfa acilisi yavas; urunlerin yuklenmesi bekleniyor.', flush=True)
                wait_products(page, wait_seconds)
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                for text in soup.find_all(string=lambda v: v and v.strip() == 'Ürünler'):
                    if text.parent.name in ('script','style'):
                        continue
                    match = re.fullmatch(r'\s*(\d+)\s+Ürünler\s*', text.parent.parent.get_text(' ',strip=True))
                    if match:
                        current_total = int(match[1])
                        if total is not None and total != current_total:
                            raise ValueError('Kategori urun sayisi toplama sirasinda degisti; tekrar deneyin.')
                        total = current_total
                        break
                page_keys = set()
                for card in soup.select('.dpb-holder[data-supermodelid]'):
                    name = card.select_one('a.product-title').get_text(' ',strip=True)
                    page_keys.add((card['data-supermodelid'], name))
                if not page_keys - raw_products:
                    raise ValueError('Sonraki sayfa onceki urunleri tekrarladi; eksik sonuc kaydedilmedi.')
                raw_products.update(page_keys)
                stamp = datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(timespec='seconds')
                page_rows, excluded, next_url = parse_html(html, stamp, require_records=False)
                for row in page_rows:
                    row['price_type'] = 'live_page_current'
                    row['price_label'] = 'Canli urun listesinde gorunen fiyat'
                    name = row['product_name']
                    # Ayni isimde farkli pazaryeri urunleri bulunabilir.
                    # Renk adini ve kaynak urun kodunu birlikte koru.
                    match = re.search(r'/R-p-([^/?#]+)', row['source_url'])
                    if not match:
                        raise ValueError(f'Urun kodu okunamadi: {name}')
                    identity = f'{name} | {match[1]}'
                    row['product_name'] = identity
                    if identity in records and records[identity]['price'] != row['price']:
                        raise ValueError(f'Ayni urun icin farkli fiyatlar: {name}')
                    records[identity] = row
                exclusions.update(excluded)
                print(f'Okundu: {len(page_keys)} kart; biriken bisiklet: {len(records)}', flush=True)
                target = safe_next(next_url) if next_url else None
            if not total or len(raw_products) != total:
                raise ValueError(f'Tam kapsam dogrulanamadi: {len(raw_products)} kart / beklenen {total}. CSV yazilmadi.')
            if not records:
                raise ValueError('Bisiklet fiyati bulunamadi.')
            print(f'Tum liste kontrolu: {total} kart, {len(records)} bisiklet, {len(exclusions)} haric urun.', flush=True)
        finally:
            context.close()
    return sorted(records.values(), key=lambda r:r['product_name']), now
