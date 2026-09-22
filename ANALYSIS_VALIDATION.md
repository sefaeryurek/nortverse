# Analiz değerini doğrulama planı

## 22 Eylül 2026 durumu

Canlı `/api/analysis-evidence` başlangıç denetiminde, maçtan önce kaydedilmiş ve
sonucu doğrulanmış 49 analiz bulundu. Bunların 5'inde Arşiv 1, 0'ında Arşiv 2
maç sonu eşleşmesi vardı. Bu sayılar isabet veya kârlılık iddiası için yeterli
değil. Önceki lig filtresinin kaçırdığı kupa/turnuva kayıtları bulunabileceğinden
eski kohort ayrıca temizlenmeli. Yeni sürüm bu turnuvaları dışarıda bırakır.

Kupa filtresinden sonra canlı uygun grup 47 maça düştü: Arşiv 1 için 5,
Arşiv 2 için 0 değerlendirilebilir maç var. Maç sonu skor listesi 43 maçın
14'ünde gerçek skoru kapsıyor. Bunlar geçmiş verilerdeki kapsam sayılarıdır;
ileri dönem seçim isabeti olarak yorumlanmaz.

### İlk kronolojik karşılaştırma

43 değerlendirilebilir maçın skor listesinde ortalama 4,3 farklı skor vardı.
Basit karşılaştırma için, her analiz anında sonucu **zaten doğrulanmış** önceki
lig maçlarının en sık görülen skorlarından aynı sayıda seçim yapıldı. Önceki
sonuç sayısı liste boyundan az olan maç çıkarılınca 42 eşleşmiş maç kaldı:
mevcut skor listesi 13, basit geçmiş skor listesi 17 gerçek skoru kapsadı.
Karşılaştırma ligler birlikte ele alınarak ve eşit sıklıkta skorlar sabit
alfabetik sırayla seçilerek yapıldı. Bu küçük, geçmişe dönük grupta mevcut
skor listesinin basit yönteme üstünlüğü gösterilemedi. Fark istatistiksel
kanıt veya bahis getirisi olarak yorumlanmamalı; seçim kuralları ileri dönem
testi görülmeden bu 42 maça göre ayarlanmamalı.

Yeni ölçüm, maç öncesi 3,5+ skor listesinin kesin skoru kapsadığı maç sayısını
gösterir. Bu **skor listesi kapsamıdır**; tahmin olasılığı veya bahis getirisi
değildir. 100 uygun maçtan önce yüzde yayımlanmaz.

`ft-core-v1` ile yeni maçlar için ilk maç öncesi analizden en fazla altı küçük
pazar seçimi saklanır: iki arşivde ayrı ayrı maç sonucu, 2.5 alt/üst ve
karşılıklı gol. Arşivde en az 20 benzer maç ve seçimde en az %65 geçmiş
sıklık gerekir. Hiçbir seçim çıkmasa da boş kayıt tutulur. Aynı maç ve kural
sürümü tekrar analiz edildiğinde ilk kayıt değişmez. `/api/analysis-validation`
yalnızca daha sonra doğrulanmış kesin skorları bu sabit seçimlerle karşılaştırır;
pazar başına 100 sonuçtan önce yüzde göstermez. Bu eşikler ileri dönem takibi
başlatmak içindir; kanıtlanmış değer veya kalibre olasılık anlamına gelmez.

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
