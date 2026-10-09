# Multi-City Rent Inflation Calculator 📈🏠

Bu proje; Kayseri, Sivas ve Tokat illerindeki günlük kiralık konut ilan fiyatlarını analiz ederek, bölgesel enflasyon metriklerini hesaplayan otomatik bir veri işleme aracıdır. Python ve Pandas kullanılarak vektörize edilmiş işlemlerle yüksek performanslı çalışacak şekilde tasarlanmıştır.

## 🚀 Özellikler

- **Çoklu Şehir Desteği:** Tek bir çalıştırmada `Kayseri`, `Sivas` ve `Tokat` için ayrı ayrı hesaplama yapar.
- **Dinamik Zaman Aralıkları:** Varsayılan olarak bugünün verisini alıp geriye dönük **1, 7, 15 ve 30 günlük** enflasyon değişimlerini tek seferde hesaplar.
- **İsteğe Bağlı Tarih Karşılaştırması:** Belirli bir tarihi hedef alabilir veya iki spesifik tarih arasındaki değişimi hesaplayabilir.
- **TÜİK Entegrasyonu:** Tüm hesaplamalar TÜFE sepetindeki `04 - Konut, su, elektrik, gaz ve diğer yakıtlar` ana harcama grubuna göre ağırlıklandırılır.
- **Zaman Serisi (Time-Series) Çıktısı:** Her gün çalıştığında sonuçları bir özet (summary) dosyasına ekleyerek tarihsel bir trend oluşturur.

## 📁 Klasör Yapısı (Beklenen)

Kodun doğru çalışması için ham verilerin (CSV) belirli bir hiyerarşide olması gerekir:

```text
inflationstudymirror/
├── Datas/
│   └── HousesRent/
│       ├── Kayseri/
│       │   ├── 2026-03-27.csv
│       │   └── 2026-03-28.csv
│       ├── Sivas/
│       └── Tokat/
└── Inflations/
    ├── Codes/
    │   └── HousesRent/
    │       └── sahibinden_inflation.py   <-- Bu betik
    └── Datas/
        └── HousesRent/                   <-- Çıktılar buraya kaydedilir
            ├── Kayseri/
            ├── Sivas/
            └── Tokat/
```
# ⚙️ Kurulum ve Gereksinimler

Sistemin çalışması için Python ortamında pandas kütüphanesinin yüklü olması gerekir.
Bash

pip install pandas

# 💻 Kullanım Senaryoları

Terminal veya komut istemcisi üzerinden scripti farklı argümanlarla çalıştırabilirsiniz.

# 1. Standart Çalıştırma (Bugünün verisi):
Bugünün tarihini baz alır ve geriye dönük (1d, 7d, 15d, 30d) verilerle karşılaştırıp hesaplar.
Bash

python sahibinden_inflation.py

# 2. Belirli Bir Tarihi Hedef Alma:
Geçmiş bir tarihe ait rapor üretmek isterseniz --date parametresini kullanabilirsiniz.
Bash

python sahibinden_inflation.py --date 2026-03-28

# 3. İki Spesifik Tarihi Karşılaştırma:
Özel bir tarih aralığındaki değişimi görmek için hem --date hem de --compare parametrelerini kullanın.
Bash

python sahibinden_inflation.py --date 2026-03-28 --compare 2026-03-01

# 📊 Çıktı Dosyaları

Betik çalıştığında her şehir için kendi klasöründe (örn: Inflations/Datas/HousesRent/Kayseri/) iki farklı dosya üretir/günceller:

    {City}_inflation_YYYY-MM-DD.csv (Detaylı Veri):

        O güne ait tüm ilçe ve oda tipleri (Segment) için hesaplanmış medyan fiyatlar.

        Her segmentin geçmiş dönemlere (1, 7, 15, 30 gün) göre yüzde kaç değiştiğini (basic_inflation) gösterir.

    {City}_inflation_summary.csv (Özet / Zaman Serisi):

        Şehrin genel sepet bazlı enflasyon ortalamalarını içerir.

        Dosya her çalıştırmada güncellenir ve yeni bir satır (tarih) eklenir. Trend analizi ve görselleştirme yapmak için idealdir.

# 🧠 Metodoloji

    Aykırı Değer (Outlier) Kontrolü: İlan platformlarındaki hatalı veya manipülatif veri girişlerinden etkilenmemek adına ortalama (mean) yerine medyan (median) fiyatlar kullanılır.

    Segmentasyon: Konutlar (İlçe, Oda Sayısı) kırılımında gruplanır. Böylece elma ile armut karşılaştırılmaz (Örn: Sadece Melikgazi'deki 3+1 evlerin kendi içindeki fiyat değişimi izlenir).

    Vektörizasyon: Fiyat verilerindeki "TL" ve "." gibi string ifadelerin temizlenmesi döngüler yerine Pandas'ın C tabanlı vektörize operasyonları ile yapılarak maksimum performans sağlanır.


---
