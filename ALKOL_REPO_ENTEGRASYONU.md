# Alkol ve tütün: incelemeye sunulan entegrasyon

Bu ekleme mevcut master dalına yeni dosyalar ekler. Var olan toplayıcılar, genel
çalıştırıcılar, enflasyon formülleri ve kategori ağırlıkları değiştirilmez.

## Kullanım

Repo kökünde Python 3.10+ ile:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-alcohol-pilot.txt
.venv\Scripts\python.exe -m unittest discover -s . -p "test_*pilot.py"
.venv\Scripts\python.exe collect_all.py
```

Windows'ta kurulumdan sonra `TUM_FIYATLARI_CEK.cmd` de kullanılabilir. Hiçbir kaynak
tarayıcı penceresi açmayı gerektirmez. Detaylar `ALKOL_PILOT_README.md` dosyasındadır.

Toplayıcılar `InflationItems/Codes/02_Alcohol_Tobacco/AlkolFiyatlariCo/` altında ortak
yardımcıları paylaşır. BirGün ve ikincil kaynak denetim modülleri de şu an aynı paket
klasöründedir; kaynakları adları ve çıktı klasörleriyle ayrılır.

## İnceleme çıktısı ve hesaplama ayrımı

Her koşu `reports/runs/<zaman>/` altında izole edilir. Başarısız bir kaynak diğerlerini
durdurmaz; koşu özeti eksikliği bildirir ve program 1 çıkış koduyla sonlanır.
Birleştirilmiş alkol CSV'si yalnızca aynı koşunun sekiz alkol kategorisini kapsar.
BirGün sigara/tütün duyurusu ve ikincil kalite raporları bu CSV'ye katılmaz.

Bu ekleme **02 grubunu mevcut enflasyon hesaplayıcısına bağlamaz**. Gözlemler kaynak
listelerinden alınır; güncel mağaza fiyatları bağımsız doğrulanmış değildir. Ana grup
ve alt madde ağırlığı atanmaz. Hesaplamaya geçiş, kaynak doğrulaması ve ekip metodoloji
incelemesinden sonra ayrı değişiklik olarak ele alınmalıdır.

## Örnek koşu

15 Ekim 2026 örneği 333 alkol gözlemi, 14 ayrı tarihsel sigara/tütün satırı ve iki kaynak
kalite denetimi içerir. Sigara paket içi adet/gramajı ve bugünkü geçerliliği belirsizdir.
WOWTURKEY'de iç fiyat çelişkileri, EnUcuzFiyatlari'nda tarih tutarsızlıkları vardır.
Bu durumlar JSON raporlarında korunur; fiyatlar varsayımla tamamlanmaz.

22 yerel test ve tüm kaynakların tek komutla canlı çekimi başarılıdır. Kaynak sayfa yapısı,
başlıklar veya aylık fiyat dönemleri değişince kodun güncellenmesi gerekebilir.
Zamanlanmış sunucu görevi, üretim dağıtımı ve bütün tütün ürünlerini kapsama dahil değildir.
