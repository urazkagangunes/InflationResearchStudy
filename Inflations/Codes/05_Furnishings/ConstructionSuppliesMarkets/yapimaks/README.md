Bu araç, Yapımaks mağazasından çekilen günlük fiyat verilerini kullanarak, ürünleri TÜİK (Türkiye İstatistik Kurumu) harcam gruplarına göre sınıflandırır ve enflasyon oranlarını hesaplar.
## 1. Sistemin Çalışma Mantığı

Kod, kategori_haritasi.json dosyasındaki eşleştirmeleri kullanarak her ürünü üç ana TÜİK grubundan birine atar:

  Grup 05 (Ev Bakım ve Hırdavat): Vidalar, borular, el aletleri, boyalar, banyo ve mutfak malzemeleri. (Mağazanın %90'ı)

  Grup 07 (Ulaştırma): Oto bakım ürünleri (Autokit), krikolar, antifriz, akü ve lastik ekipmanları.

  Grup 09 (Eğlence ve Kültür): Yapay ağaçlar, çiçekler, kamp malzemeleri, spor aletleri ve evcil hayvan ürünleri.

# 2. Gereksinimler

Hesaplama yapabilmek için şu dosyaların yerinde olması gerekir:

   Günlük CSV Verileri: InflationItems/Datas/ConstructionSuppliesMarkets/Yapimaks/ içinde yapimaks_YYYY-MM-DD.csv formatında.

   Kategori Haritası: kategori_haritasi.json (Scraper tarafından oluşturulan dosya).

## 3. Kullanım

Terminalden hedef tarihi belirterek çalıştırabilirsin:
Bash

python inflation.py

Not: Kodun içindeki run_inflation_report("2026-03-24") kısmını istediğin tarihe göre güncelleyebilirsin.
## 4. Çıktılar (Output)

Inflations/Datas/ConstructionSuppliesMarkets/Yapimaks/ klasöründe iki ana rapor oluşur:
# A. Detaylı Ürün Raporu (yapimaks_detailed_inf_TARİH.csv)

Her bir ürün için şu bilgileri içerir:

  Ürün ID, Fiyat ve Kategori bilgisi.

  tuik_code: Ürünün hangi TÜİK grubuna dahil olduğu.

  change_1d/7d/15d/30d: Ürünün ilgili gün sayısındaki yüzde değişim oranı.

# B. Özet Rapor (inflation_summary.csv)

Bu dosya projenin "Dashboard" kısmıdır. Şunları içerir:

  genel_30d: Mağaza genelindeki 30 günlük toplam enflasyon.

  grup_05_30d: Sadece hırdavat/ev bakım grubundaki aylık artış.

  grup_07_30d: Sadece ulaştırma/oto grubundaki aylık artış.

## 5. Teknik Detaylar

  Encoding: Dosyalar utf-8-sig formatında kaydedilir, böylece Türkçe karakterler Excel'de bozulmadan görünür.

  Fiyat Dönüştürme: CSV'deki virgüllü fiyatlar (150,50) otomatik olarak sayısal formata (150.50) çekilir.

  Mapping: Yeni bir kategori eklendiğinde kod bunu otomatik olarak "05" grubuna atar (Default).
