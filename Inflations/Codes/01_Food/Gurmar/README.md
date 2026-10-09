# Gürmar Enflasyon Hesaplayıcı (CLI)

Gürmar süpermarketlerinden çekilen (scraped) günlük fiyat verilerini kullanarak 1, 7, 15 ve 30 günlük enflasyon metriklerini hesaplayan komut satırı aracıdır. Hesaplamalarda TÜİK 2026 ana harcama grubu ağırlıkları kullanılır.

## Gereksinimler

- Python 3.8+
- `pandas` kütüphanesi (`pip install pandas`)
- Aynı dizinde bulunması gereken dosyalar:
  - `gurmar_inflation.py` (Ana CLI aracı)
  - `gurmar_tuik_config.py` (TÜİK ağırlıkları ve Gürmar kategori eşleştirmeleri)

## Veri Formatı

Hesaplayıcının çalışabilmesi için günlük CSV dosyalarının şu kolonları içermesi gerekir:
- `kategori` (Örn: "Meyve ve Sebze", "Deterjan ve Temizlik")
- `product_name` (Benzersiz ID olarak kullanılır)
- `product_price` (Örn: "64,95" veya 64.95)

Dosya isminde mutlaka `YYYY-MM-DD` formatında bir tarih bulunmalıdır (Örn: `gurmar_2026-02-24.csv`).

## Kullanım

Terminali açıp aşağıdaki komutları kullanabilirsiniz.

### 1. Standart Kullanım
Verilen tarihteki dosyayı alır ve otomatik olarak 1, 7, 15 ve 30 gün öncesinin dosyalarını aynı klasörde arayıp hesaplama yapar:

```bash
python gurmar_inflation.py -i gurmar_2026-02-24.cs
```

### 2. Çıktıları Farklı Klasöre Kaydetme (-o)

Oluşan enflasyon dosyalarını bulunduğunuz dizine değil, belirttiğiniz bir klasöre kaydetmek için:

```bash
python gurmar_inflation.py -i data/gurmar_2026-02-24.csv -o sonuclar/
```
### 3. Özel Tarih Karşılaştırması (-c)

Sadece belirlediğiniz iki dosya (bugün ve geçmiş bir tarih) arasında enflasyon hesaplamak için:
```bash
python gurmar_inflation.py -i gurmar_2026-02-24.csv -c gurmar_2026-02-10.csv
```
### 4. Yardım Menüsü

Komutların listesini ve kullanım detaylarını görmek için:
```bash
python gurmar_inflation.py -h
```
