# Ulaştırma fiyatları — repo entegrasyon paketi

Bu klasör, mevcut repoya **eklenecek dosyaları** içerir. Tam repo kopyası değildir.
İndirilen ortak repo değiştirilmedi. Mevcut hesaplama kodu ve genel çalıştırıcı değiştirilmedi.
Kod Python 3.10+ içindir; Windows üzerinde denendi.

## Repoya ekleme

1. Ekibin güncel Git reposunda ayrı bir dal açın: `git switch -c feature/vehicle-prices`.
2. Bu paketin içeriğini reponun köküne kopyalayın; `InflationItems` klasörünü mevcut klasörle birleştirin.
   Paket hazırlanırken mevcut dosya adlarıyla çakışma bulunmadı. Güncel repoda bir dosyanın üzerine
   yazma sorusu çıkarsa önce farkı inceleyin.
3. Aşağıdaki kurulumu ve testleri çalıştırın, `git diff` ve yeni dosyaları inceleyin, ekibe PR açın.
   Bu paket otomatik commit/push yapmaz ve mevcut `run_all` akışına kendiliğinden bağlanmaz.

Kodlar: `InflationItems/Codes/07_Transport/VehiclePrices/`

Veriler: `InflationItems/Datas/07_Transport/motor_bicyle_car/<Kaynak>/`

`motor_bicyle_car` yazımı, mevcut okuyucunun beklediği klasör adı olduğu için korunmuştur.
Her kaynak için `toyota_2026-10-15.csv` gibi tek günlük dosya üretilir.
`product_name` ve `price` zorunludur; fiyatlar TL cinsinde `1234.56` biçimindedir.
Ek sütunlar kampanya, model yılı, toplama zamanı, fiyat türü, başlık ve URL bilgisini korur.
Hesaplama okuyucusu `price` sütununu kullanır; kampanya fiyatına otomatik geçmez.

## İlk kurulum (repo kökünde terminal)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-vehicle-prices.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe test_vehicle_prices.py
```

Mevcut reponun hesaplamalarını çalıştıracaksanız ayrıca reponun kendi `requirements.txt`
bağımlılıklarını da kurun. Bu paketin bağımlılık dosyası yalnızca fiyat toplayıcılarını kapsar.
Linux sunucuda tarayıcı sistem bağımlılıkları için `python -m playwright install --with-deps chromium`
gerekebilir. Sunucu kurulumu bu çalışmada denenmedi.

## Kullanım

Windows'ta `ARAC_FIYATLARINI_CEK.cmd` dosyasına çift tıklayabilirsiniz. Python ve Chromium
kurulumunun önce tamamlanmış olması gerekir. Açılan tarayıcıları çekim bitmeden kapatmayın.

Terminalden tüm kaynaklar:

```powershell
.venv\Scripts\python.exe run_vehicle_prices.py
```

Yalnızca seçilen kaynaklar:

```powershell
.venv\Scripts\python.exe run_vehicle_prices.py --sources Toyota Honda Lastikcim
```

Tarayıcı penceresi açılamayan otomatik çalıştırmalar için (Decathlon ve Salcano atlanır):

```powershell
.venv\Scripts\python.exe run_vehicle_prices.py --non-interactive
```

Kaynak listesi: `python run_vehicle_prices.py --list-sources`.
Diğer kaynaklarda pencereyi görmek için `--headed` ekleyin.
Bugünün dosyası varsa kaynak tekrar çekilmeden atlanır. Aynı günü yeniden toplamak için
`--replace-day` kullanın; önceki CSV `archive/` altında saklanır ve repo okuyucusu arşivi atlar.
Paket içindeki 15 Ekim 2026 verileri nedeniyle aynı gün normal çalıştırma bunları atlar.
Bağımsız deneme için `--data-root deneme-verileri` kullanabilirsiniz.

Decathlon ve Salcano görünür tarayıcı kullanır. Güvenlik kontrolü çıkarsa kullanıcı normal
tarayıcıda tamamlar; kod CAPTCHA çözmez. Decathlon en fazla 300 saniye bekler.
Ayrı profiller `.cache/vehicle_prices/` altında oluşturulur; profil içeriği yerel `.gitignore`
ile Git dışında tutulur. `INFLATION_BROWSER_PROFILE_ROOT` ortam değişkeniyle yeri değiştirilebilir.
Kişisel tarayıcı profiliniz kullanılmaz.

Bir kaynak hata verirse diğerleri sürer; işlem sonunda hata varsa çıkış kodu 1 olur.
Kaynak başına kilit eşzamanlı çekimi önler. İşlem zorla kapatılırsa `.collect.lock` veya
`.publish.lock` kalabilir; çalışan başka çekim olmadığını doğruladıktan sonra ilgili kilit silinebilir.

## Kapsam ve veri notları

| Kaynak | Çekilen kapsam | 15.10.2026 kayıt |
|---|---|---:|
| Toyota | Tanımlı 7 binek modelin açık model yılı sekmesi; liste/tavsiye fiyatı | 23 |
| Renault | Binek, dizel hariç; opsiyonlar hariç | 23 |
| Hyundai | Benzinli, hibrit ve elektrikli; azami liste fiyatı, dizel hariç | 35 |
| Honda | 2025 ve 2026 motosiklet tavsiye fiyatları | 44 |
| Mondial | 2025 ve 2026 peşin perakende fiyatları; 9 E-BIKE dahil | 48 |
| Decathlon | Bisiklet kategorisi; scooter hariç, ürün kimliği korunur | 87 |
| Salcano | Bisiklet kategorisi, tüm liste sayfaları | 194 |
| Lastikcim | Sabit 48 ürünlük örnek: lastik, yağ, aksesuar, silecek | 37 |
| Euromaster | KDV dahil işçilik tablosunun 5 grubu | 90 |
| **Toplam** | | **581** |

Bu sayılar önceki canlı çekimin gözlemidir; sonraki çekimlerde değişebilir.
CSV'ler orijinal toplama zamanlarıyla taşınmıştır, yeniden toplanmış gibi tarihlenmemiştir.
Lastikcim'de stokta olmayan 11 ürün ve Euromaster'daki 1 boş fiyat sıfır olarak yazılmaz;
yan JSON dosyalarında raporlanır. Lastikcim örneği tüm site değildir ve istatistiksel
temsiliyet iddiası taşımaz. Örnek ürün URL'leri bitişik `lastikcim_urun_listesi.json` içindedir.
Sepet içi ek indirim uygulanmaz. Lastik üretim yılı araç model yılına yazılmaz.
Honda/Mondial yıl listeleri şu an 2025/2026 olarak tanımlıdır; yeni yıl çıktığında güncellenmelidir.
Toyota'nın bütün ticari/dizel/elektrikli ürünlerini kapsadığı varsayılmamalıdır.
Pazar yeri satıcıları ve bütün stok/renk varyantları ayrıca doğrulanmış değildir.

Mevcut repo klasör üzerinden bu verileri **07 Ulaştırma ana grubunda** okur.
Bu teknik uyumluluk, TÜİK alt madde sepetinin tamamlandığı anlamına gelmez. Alt madde kodları
ve ağırlıkları bu pakette atanmaz. Mondial E-BIKE, Lastikcim temizlik/aksesuar ürünleri ve
Euromaster ticari araç gruplarının araştırma sepetine dahil edilmesini ekip metodolojiye göre
incelemelidir. Farklı kaynaklarda ürün adı aynı biçimde değilse mevcut okuyucu bunları aynı
ürün saymayabilir. Gerçek enflasyon hesabı için farklı tarihlerde eşleşen fiyat gözlemleri gerekir.

## Yapılan doğrulamalar

- Dokuz toplayıcı modülünün yeni konumdan içe aktarılması.
- Gerçek `turkey_inflation.py` okuyucu fonksiyonlarıyla 9 mağaza ve 581 fiyatın kayıpsız okunması.
- Günlük dosya koruma, arşivleme, geçersiz veri reddi ve eşzamanlı yazma kilidi testleri.
- İndirilen repodaki mevcut dosya adlarıyla çakışma kontrolü.
- Yeni çalıştırıcıyla Toyota canlı çekimi: 23 fiyat; ikinci çalıştırmada aynı günlük dosyanın korunması.

Altı yerel test başarılıdır. Dokuz sitenin tamamı bu uyarlama sonrasında yeniden canlı çekilmedi;
diğer kaynakların mevcut doğrulanmış gözlemleri korundu.

Mevcut hesaplama formülleri, kategori ağırlıkları ve ekip otomasyonları değiştirilmedi.
