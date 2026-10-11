# Telecom scraper'ları

Bu klasörde dört ayrı scraper var. Hepsi `scraper.py` içindeki ortak `Fetcher` / `run()` kodunu kullanır.

## TÜİK 08 kalemleri

| Kalem | Ürün var mı | Scraper | Kaynaklar |
|---|---|---|---|
| Cep telefonu | — | | |
| Bilgisayar | — | | |
| Bilgisayar çevre birimleri | — | | |
| Ses ve görüntü ekipmanı | — | | |
| Televizyon | — | | |
| Diğer iletişim cihazları | — | | |
| Bilgi ve iletişim aksesuarları | — | | |
| Cep telefonu hizmet ücreti | ✅ | `scraper.py` | Turkcell, Vodafone, Türk Telekom, NetGSM: faturalı / faturasız tarifeler ve ek paketler |
| İnternet hizmet ücreti | ✅ | `internet.py` | Superonline, Vodafone Net, Kablonet, Milleni, TurkNet, Türk Telekom: ev interneti tarifeleri |
| Bilgi ve iletişim ekipmanı bakım / onarım ücreti | ✅ | `repair.py` | Apple (garanti dışı tahmini ücret), Samsung (ekran değişimi), Huawei (yedek parça), Egemek (Apple yetkili servis), GSM İletişim (bağımsız servis) |
| Dijital içerik / streaming platform aboneliği | ✅ | `streaming.py` | Netflix, Disney+, HBO Max, Prime, Apple TV+, YouTube Premium, Spotify, MUBI, TV+, Tivibu, TOD, GAIN, Tabii |

Toplanmayanlar: Exxen ve Hepsiburada Premium (fiyat sadece üyelik/giriş sonrası görünüyor),
Paramount+ (Türkiye'de satılmıyor). Onarım sepeti henüz belirlenmedi; `repair.py` her kaynağın
yayımladığı bütün ücretleri toplar.

## Nasıl çalışır

Tarayıcı neredeyse hiç kullanılmaz: kaynaklar Chrome TLS parmak izli `curl_cffi` istemcisine
cevap verir. İstisnalar: TurkNet (Cloudflare; tek bir headless Chrome ziyaretiyle cookie + UA
alınır, sonra `curl_cffi`) ve Tabii (fiyat istemci tarafında dolduğu için tek bir headless Chrome
ziyareti). Kaynak bazında hangi sayfadan / JSON'dan okunduğu her dosyanın başındaki docstring'de
ve `docs/site-analysis/telecom/NOTES.md` içinde.

Bir kaynak hata verirse diğerleri devam eder; boş sonuç yazılmaz (son iyi snapshot korunur),
herhangi bir kaynak başarısızsa çıkış kodu 1 olur.

## Çalıştırma

```bash
python InflationItems/Codes/08_Communication/Telecom/scraper.py --operator turkcell --limit 5
```

Dört scraper da aynı CLI'yı kullanır: `--operator <kaynak>|all` (varsayılan `all`) ve
`--limit N` (sınırlı test çalıştırması; gerçek günlük dosyanın üzerine yazmamak için
`*_limit.csv` dosyasına yazar).

Sunucuda `bin/run_scraper.sh telecom|internet|streaming|repair` ile her gün sırasıyla
06:00, 07:30, 08:45 ve 09:00'da çalışırlar (`deploy/scraper-server/`, inflationstudymirror reposunda (`vinnipukh/inflationstudymirror`)). Log: `logs/telecom*_YYYY-MM-DD.log`.

## Çıktı

Her retailer için tek klasör, `InflationItems/Datas/08_Communication/<Retailer>/`. Ev interneti ve
onarım dosyaları, mobil tarifeler ve teknoloji ürünleriyle aynı klasörü paylaştıkları için tür
ekiyle ayrılır:

| Scraper | Dosya | Kolonlar |
|---|---|---|
| `scraper.py` | `<Operator>/<operator>_YYYY-MM-DD.csv` | `date, operator, segment, group, product_id, product_name, price, list_price, period, data_gb, minutes, sms, commitment_months, url` |
| `internet.py` | `<Provider>/<provider>_internet_YYYY-MM-DD.csv` | `date, operator, group, product_id, product_name, price, list_price, period, speed_mbps, upload_mbps, infrastructure, commitment_months, url` |
| `streaming.py` | `<Service>/<service>_YYYY-MM-DD.csv` | `date, operator, group, product_id, product_name, price, list_price, period, url` |
| `repair.py` | `<Source>/<source>_repair_YYYY-MM-DD.csv` | `date, operator, group, product_id, product_name, service, price, list_price, url` |
