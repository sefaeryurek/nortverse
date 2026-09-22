# Analiz değerini doğrulama planı

## 22 Eylül 2026 durumu

Canlı `/api/analysis-evidence` başlangıç denetiminde, maçtan önce kaydedilmiş ve
sonucu doğrulanmış 49 analiz bulundu. Bunların 5'inde Arşiv 1, 0'ında Arşiv 2
maç sonu eşleşmesi vardı. Bu sayılar isabet veya kârlılık iddiası için yeterli
değil. Önceki lig filtresinin kaçırdığı kupa/turnuva kayıtları bulunabileceğinden
eski kohort ayrıca temizlenmeli. Yeni sürüm bu turnuvaları dışarıda bırakır.

Yeni ölçüm, maç öncesi 3,5+ skor listesinin kesin skoru kapsadığı maç sayısını
gösterir. Bu **skor listesi kapsamıdır**; tahmin olasılığı veya bahis getirisi
değildir. 100 uygun maçtan önce yüzde yayımlanmaz.

## Sonraki uygulama adımları

1. Her maç başlamadan önce analiz sürümünü, üretim zamanını, seçilen pazarları,
   seçim yüzdesini, karşılaştırma sayısını ve o anda erişilebilir oranı küçük,
   değiştirilemez bir tahmin kaydı olarak sakla. Sonradan yeniden hesaplanan
   desenler geçmiş tahmin yerine geçmemeli.
2. Kesin sonuç geldikten sonra yalnızca maç öncesi kayıtları değerlendir.
   Zamanı veya sonucu eksik, kupa/turnuva ya da maçtan sonra üretilmiş kayıtları
   ayrı say ve başarı paydasına katma.
3. Her pazar ve analiz sürümü için kapsamı, seçim isabetini ve belirsizlik
   aralığını raporla. Gerçek olasılık modeli üretildiğinde kalibrasyon grafiği,
   Brier skoru ve log loss hesapla. Mevcut arşiv sıklığını kalibre olasılık gibi
   adlandırma.
4. Maçları kronolojik olarak ayır: eski maçlarda kural geliştir, sonraki
   maçlarda hiç dokunulmamış testi yap. Lig ve sezon kırılımlarını izle;
   aynı maçın sonucunu arşiv eşleşmesine veya kendi tahminine sızdırma.
5. Değer iddiası için seçimin yapıldığı andaki gerçek oranı sakla; marj, iade,
   iptal ve komisyonu hesaba katarak sabit bahis tutarıyla getiriyi ve piyasaya
   göre farkı ölç. Oran kaydı yoksa yalnızca tahmin kalitesi konuşulabilir.
6. Yayın eşiğini toplam maç sayısıyla değil, **her pazarın** bağımsız ileri dönem
   örneklemi ve belirsizlik aralığıyla belirle. Başlangıç hedefi pazar başına
   en az 100 sonuçlu tahmin; bu asgari sayı tek başına başarı kanıtı değildir.

Kalibrasyon ve Brier/log loss için [scikit-learn kalibrasyon kılavuzu](https://scikit-learn.org/stable/modules/calibration.html),
geleceğe bilgi sızdırmayan kronolojik değerlendirme için
[TimeSeriesSplit belgeleri](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
temel alınır.
