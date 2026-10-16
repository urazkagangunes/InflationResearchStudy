# Alkol ve tütün — kaynak toplama paketi

Bu bağımsız klasör, AlkolFiyatlari.co üzerindeki sekiz içki kategorisini, BirGün'de tarihli
bir sigara/tütün duyurusunu ve iki ikincil kaynağın kalite kontrollerini kapsar.
Normal HTTP isteği kullanır; tarayıcı açmaz. Mevcut ulaştırma PR'ı ve ortak repo değiştirilmedi.

## Hepsini tek seferde çalıştırma

Kurulum tamamlandıktan sonra `TUM_FIYATLARI_CEK.cmd` dosyasına çift tıklayın veya
`python collect_all.py` çalıştırın. Windows başlatıcı yerel `.venv` varsa onu, yoksa
PATH üzerindeki `python` komutunu kullanır. Başka bilgisayarda paket bağımlılıkları kurulmalıdır.

Her çalıştırma `reports/runs/<zaman>/` altında yeni klasör oluşturur. İçinde:

- `combined_alcohol_observations.csv`: yalnızca bu çalıştırmanın sekiz alkol kategorisi.
- `run_summary.json`: kaynak başına başarı/hata, kayıt sayıları ve dosya yolları.
- Kaynak alt klasörleri: orijinal CSV ve gerekçeli JSON inceleme raporları.
- BirGün ve ikincil kontrol raporları: ayrı kalır, birleşik alkol CSV'sine girmez.

Bir kaynak hata verirse diğerleri sürer; eksik koşu `complete=false` ve çıkış kodu 1 ile
işaretlenir. Önceki çalıştırmanın dosyaları bu koşuya katılmaz. Fiyat alanlarının anlamı
ve aşağıdaki sınırlamalar birleşik çıktı için de geçerlidir; çıktı otomatik endeks girdisi değildir.

## Çalıştırma

Python 3.10+ ile bu klasörde:

```powershell
python -m pip install -r requirements-alcohol-pilot.txt
python test_alcohol_pilot.py
python run_alcohol_pilot.py
python run_alcohol_pilot.py --source birgun
python run_alcohol_pilot.py --source raki
python run_alcohol_pilot.py --source votka
python run_alcohol_pilot.py --source bira
python run_alcohol_pilot.py --source sarap
python run_alcohol_pilot.py --source cin
python run_alcohol_pilot.py --source tekila
python run_alcohol_pilot.py --source likor
```

Çıktı `InflationItems/Datas/02_Alcohol_Tobacco/AlkolFiyatlariCo/reports/` altına
zaman damgalı CSV ve JSON olarak yazılır. Farklı klasör için `--output-root <klasör>` kullanın.
JSON, kaynak adresi, sayfa yayın tarihi, metindeki son kontrol tarihi, reddedilen satırlar
ve sayfanın SHA-256 özetini içerir. Sayfa değişir veya belirsizleşirse işlem hata verir.
Eski çıktı üzerine yazılmaz.

## Neden reports klasörü?

Bunlar kaynak gözlemleridir; bağımsız doğrulanmış güncel mağaza fiyatları değildir.
Fiyatın geçerlilik başlangıcı kaynakta açıkça verilmediği için `effective_from` boş bırakılır.
Kaynak metni listeyi tavsiye edilen perakende fiyatı olarak tanımlar.
Mevcut hesaplama okuyucusunda 02 grubu tanımlı değildir; bu pilot hesaplamayı değiştirmez.
Ekip doğrulaması ve kategori entegrasyonu tamamlanmadan otomatik enflasyon girdisi yapılmaz.

## Güncel canlı sonuç — 15 Ekim 2026

- 42 benzersiz ürün/hacim gözlemi: 35 cl 8, 50 cl 8, 70 cl 18, 100 cl 8.
- Üç tablo arasında 8 tekrar tek kayda indirildi. Kaynaktaki Jameson adı, aynı sayfada
  açıkça eşleşen Jameson Irish Whiskey adıyla birleştirildi; farklı ürünler genel isim benzerliğiyle eşleştirilmez.
- Belirsiz 150/175 cl sütunundaki 4 fiyat CSV'ye alınmadı, JSON'da gerekçeleriyle raporlandı.
- Çelişkili fiyat bulunan aynı ürün/hacim tüm tablolardan çıkarılarak inceleme raporuna alınır;
  fiyatlardan biri keyfi seçilmez. İlk canlı genişletilmiş çekimde çelişki bulunmadı.
- Sayfanın yayın zamanı 15 Ekim, metindeki son fiyat kontrolü 13 Ekim 2026.
- 5 test başarılı: fiyat/hacim/tarih, belirsiz hacim ve geçersiz fiyat, tekrar/gelecek tarih,
  tablolar arası tekrarları birleştirme ve çelişkili fiyatları dışlama.
- Paragraf içindeki fiyatlar kapsam dışıdır. Bu, tüm alkol/tütün listesinin tamamlandığı
  anlamına gelmez.
- İlk 9 satırlık pilot çıktısı tarihli geçmiş gözlem olarak korunur; güncel kapsam 42 satırlık son çıktıdır.

Kaynak: https://alkolfiyatlari.co/viski-fiyatlari/

## BirGün sigara/tütün pilotu

`python run_alcohol_pilot.py --source birgun` komutu, sabit ve tarihli bir Philip Morris
haber listesini normal HTTP ile okur. Bütün haberleri taramaz ve en yeni listeyi bulduğunu
iddia etmez. Çıktı `InflationItems/Datas/02_Alcohol_Tobacco/BirGun/reports/` altındadır.

15 Ekim 2026 canlı çekimi: 13 sigara satırı ve 1 kıyılmış tütün satırı, toplam 14 kaynak
gözlemi. Haber yayını 6 Ağustos, açık fiyat geçerlilik başlangıcı 6 Ağustos 2026'dır.
Bu tarihten bugüne geçerlilik doğrulanmadığı için bitiş tarihi boş bırakılır ve gözlemler
tarihsel olarak işaretlenir; bugün geçerli fiyat yerine kullanılmaz.

14 satırda da miktar bilgisi eksiktir. Sigara için paket içi adet varsayılmaz; ürün adındaki
`Roll 50` ifadesi açıkça gram yazmadığı için 50 gram kabul edilmez. Altı satır birden çok
varyantı birlikte verir; bunlar ayrı ürünlere çoğaltılmadan kaynakta göründüğü gibi korunur.
Sonuç olarak endeks hesabına hazır kayıt sayısı 0'dır. Kaynak gözlemlerindeki fiyatlar
CSV'de bulunur, eksiklik gerekçeleri ayrı sütundadır.

Haberde kapanmamış HTML liste ve paragraf etiketleri bulunduğu için ayrıştırıcı her liste
maddesinin yalnızca kendi metnini okur; iç içe etiketlerin fiyatları birleştirmesini önler.
Toplam 9 test geçti. Hepsini çalıştırmak için:

```powershell
python -m unittest discover -s . -p "test_*pilot.py"
```

Kaynak: https://www.birgun.net/haber/bir-sigara-grubuna-daha-zam-geldi-727813

## Rakı ve votka tabloları

`--source raki` ve `--source votka` normal HTTP ile ürün/hacim tablolarını toplar.
Çıktıları AlkolFiyatlariCo `reports/` klasörüne ayrı CSV/JSON çiftleri olarak kaydedilir.

15 Ekim 2026 canlı sonuçları:

- Rakı: 66 benzersiz ürün/hacim kaydı. 4 tekrar birleştirildi; 16 boş hücre sıfır yazılmadı.
  Açık hacimler 35/50/70/100/150 cl. Yeni Rakı (Yeni Seri) ile Yeni Rakı Yeni Seri adı
  sayfaya özgü açık eşleştirmeyle birleştirilir. Pus/Giz adındaki 50 cl hacim bilgisi sütunla karşılaştırılır.
- Votka: 34 benzersiz ürün/hacim kaydı. Absolut Vodka başlıklı ek tablodaki 4 fiyat,
  ürün serisi açıkça belirtilmediği için incelemeye ayrıldı; Absolut Blue sayılmadı.
- İki sayfanın yayın tarihi 26 Eylül 2026. Açık fiyat geçerlilik veya son kontrol tarihi
  çıkarılmadı; ilgili alanlar boş bırakıldı. Yayın tarihi, bugünkü raf fiyatı kanıtı değildir.
- Toplam 12 test başarılıdır. Viski/rakı/votka güncel çekimlerinde toplam 142 kaynak
  gözlemi vardır; BirGün'ün 14 tarihsel ve miktarı belirsiz satırı bu sayıya dahil değildir.

Kaynaklar: https://alkolfiyatlari.co/raki-fiyatlari/ ve https://alkolfiyatlari.co/votka-fiyatlari/

## Bira ve şarap

`--source bira`: 27 benzersiz ürün/hacim/ambalaj/depozito gözlemi. 24 belirsiz satır
incelemeye ayrıldı. Hacim yalnızca açık cl ifadesinden alınır; küçük/büyük şişe varsayılmaz.
23,7 cl 237 ml olarak korunur. Depozitolu ve depozitosuz şişeler ayrı kimliktir; depozito
tutarı veya fiyatın depozitoyu içerip içermediği bilinmiyorsa boş bırakılır. Kutu ile şişe
birleştirilmez. İki özel seri tekrarı birleştirildi. Altı satırlık litre fiyatı karşılaştırma
tablosu yeni ürün fiyatı gibi tekrar toplanmadı.

`--source sarap`: 16 açık hacimli ürün gözlemi, 19 belirsiz satır incelemeye ayrıldı.
Birlikte verilen kırmızı/beyaz/roze çeşitleri ayrı ürünlere çoğaltılmaz. Hacmi başka bir
bölümden tahmin edilmez. Ekim 2026 tablolarında önceki fiyat yerine Ekim fiyatı alınır;
`price_period=2026-10` saklanır, açık başlangıç günü verilmediği için `effective_from`
boş kalır. Bu aylık tablo başlığı değiştiğinde parser güncellenmeden çalışmaya devam etmez.

İki sayfanın yayın tarihi 26 Eylül 2026'dır; şarap tablosundaki Ekim dönem etiketi bu yayın
tarihinden ayrı tutulur. Güncel mağaza fiyatı bağımsız doğrulanmış değildir.

15 test başarılıdır. Son çekimlerde viski 42 + rakı 66 + votka 34 + bira 27 + şarap 16 =
**185 alkol kaynak gözlemi** vardır. BirGün'deki 14 tarihsel/miktarı belirsiz satır ayrı kalır.
Geçmiş çekimleri toplama ekleyerek aynı ürünler yeniden sayılmamalıdır.

Kaynaklar: https://alkolfiyatlari.co/bira-fiyatlari/ ve https://alkolfiyatlari.co/sarap-fiyatlari/

## Cin, tekila ve likör

15 Ekim 2026 canlı sonuçları:

- Cin: 28 benzersiz ürün/hacim kaydı; 2 tekrar birleştirildi. Bar/kokteyl ve yabancı şehir
  karşılaştırmaları ürün fiyatı olarak alınmadı.
- Tekila: 21 benzersiz kayıt; tablolardaki 10 tekrar birleştirildi. Yabancı ülke fiyatları alınmadı.
- Likör: 99 kayıt; 52 inceleme girdisi. Birlikte yazılan çeşitler, üretici/serisi belirsiz
  genel meyve ve klasik likör tabloları ile satır hacmi başlıkla çelişen kayıtlar dışarıda tutuldu.
  Captain Morgan ve Zacapa rom kayıtları likör kategorisine otomatik dahil edilmedi.
- Nazen 35 cl nane ve vişne adları sayfa içindeki açık ad eşleştirmeleriyle karşılaştırıldı:
  her iki ürün için de 775 ve 310 TL çelişkisi bulundu. İki kimlik de CSV dışında bırakıldı,
  her iki fiyat JSON inceleme raporunda saklandı. Diğer aromalar arasında genel ad benzerliğiyle eşleştirme yapılmadı.
- Likörde önceki fiyat yerine Ekim sütunu kullanılır; `price_period` saklanır. Açık başlangıç
  günü ve bağımsız fiyat kontrol tarihi olmadığı için bu alanlar boş kalır.

Toplam 18 test başarılıdır. Son çekimler: viski 42 + rakı 66 + votka 34 + bira 27 + şarap 16
+ cin 28 + tekila 21 + likör 99 = **333 alkol kaynak gözlemi**. Bu sayıya BirGün'ün 14
tarihsel/miktarı belirsiz satırı dahil değildir. Bütün alkol/tütün kapsamının tamamlandığı
veya güncel mağaza fiyatlarının doğrulandığı anlamına gelmez. Ortak repo/PR değiştirilmedi.

Kaynaklar: https://alkolfiyatlari.co/cin-fiyatlari/ , https://alkolfiyatlari.co/tekila-fiyatlari/
ve https://alkolfiyatlari.co/likor-fiyatlari/

## WOWTURKEY ve EnUcuzFiyatlari kontrolü

```powershell
python audit_secondary_sources.py
```

İki sayfa normal HTTP ile okunur; sonuçlar `secondary-source-reports/` altında JSON'a
yazılır. Kaynakların fiyatları otomatik olarak enflasyon girdisine aktarılmaz.

- WOWTURKEY: yalnızca ilk gönderi incelenir, yanıtlar hariçtir. 20 tablo satırı ve 39
  madde okunur. Açık etiket karşılaştırmalarında Camel Slender, Deep Blue, Black & White
  ve Yellow & Brown için 4 fiyat çelişkisi bulundu. Bu kontrol bütün olası çelişkileri
  kapsamaz; kaynakta miktar ve geçerlilik tarihi de doğrulanmış değildir.
- EnUcuzFiyatlari: tekrarlanan 20 ürünlük bira tabloları tek sayılır. Düz ve tipografik
  apostrof farkı aynı ürün kabul edilir. Başlık 2024–2025, gövde 2024; görünür güncelleme
  8 Ekim 2026 iken metadata güncellemesi 31 Ocak 2026'dır. Bu tutarsızlıklar çözülmeden
  güncel raf fiyatı kabul edilmez.
- Denetim raporunda adres, toplama zamanı, tarih kanıtları ve sayfanın SHA-256 özeti bulunur.

Toplam 20 test başarılıdır. Kabul edilen alkol kaynak gözlemi sayısı 333 olarak kalır;
bu iki kontrol kaynağı ve BirGün'ün inceleme satırları toplama eklenmez.

## Son toplu doğrulama

15 Ekim 2026'da sekiz alkol kategorisi, BirGün ve ikincil kaynak denetimi tek komutla
yeniden canlı çalıştırıldı. Çalıştırma dosyalarını doğrulama ve eksik koşuyu bildirme
testleriyle toplam test sayısı **22** oldu. Ulaştırma PR'ına yeni dosya eklenmedi;
bu paket için push/PR henüz yapılmadı.
