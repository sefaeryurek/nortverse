# Backend ve frontend denetimi — 14 Eylül 2026

Kaynak kod, testler, API sınırları, veri yazma işlemleri, scraper kaynak yönetimi ve frontend derlemesi incelendi. Aşağıdaki düzeltmeler yerel çalışma alanına uygulandı. Bu rapor bütün olası hataların ortadan kalktığı anlamına gelmez; canlı servis doğrulamasının sınırları en alttadır.

## Backend

| Bulgu | Uygulanan düzeltme |
| --- | --- |
| Yeniden analiz, mevcut kesin skorları ve başlama saatini NULL ile silebiliyordu. | Upsert güncellemesi bu alanlarda mevcut değeri koruyor; sorgu regresyon testi eklendi. |
| Yazma doğrulaması başarısız olsa bile pipeline başarı sayabiliyordu. | Reddedilen yazma hata üretir ve pipeline hata sayacına girer. |
| Canlı maçın ekrandaki skoru kesin sonuç gibi kaydedilebiliyordu. | Ana maç skorları için bitiş işareti aranıyor. |
| İkinci yarı skoru HTML'de bulunmadığında hesaplanmıyordu. | FT−HT ile hesaplanıyor; HT>FT gibi tutarsız yarı skorları kullanılmıyor. |
| Başlama saati saat dilimsizdi; ana maç saati yoksa geçmiş maç tarihi alınabiliyordu. | UTC bilgisi ekleniyor; geçmiş maç tarihi fallback'i kaldırıldı. |
| Sunucu UTC gününü, arayüz İstanbul gününü kullanıyordu. | API varsayılan günleri İstanbul'a göre hesaplıyor. |
| Gün sonunun kesirli saniyeleri sonuç sorgusunun dışında kalıyordu. | Sonuç/pipeline sorguları ertesi gün başlangıcını hariç üst sınır olarak kullanıyor. |
| Aktif maç kilidi LRU tahliyesinde silinip aynı maç tekrar scrape edilebiliyordu. | Kilit ömrü aktif kullanımına bağlandı; POST yenileme de aynı kilidi kullanıyor. |
| Analiz belleği süresiz eski sonuç döndürebiliyordu. | 10 dakika TTL eklendi. Bu süre sonunda DB tekrar okunur. |
| Hatalı API cevapları CDN tarafından önbelleğe alınabiliyordu. | Yalnızca başarılı ve tam yolu eşleşen cevaplar cache edilir; hatalar no-store döner. |
| Negatif limit ve geçersiz maç ID'leri pahalı işlemlere ulaşabiliyordu. | API giriş doğrulaması eklendi. |
| DB okuma hatası analiz fallback'ini engelliyordu. | Analiz DB okuması hata verdiğinde scrape yolu kullanılabiliyor. |
| Bazı PostgreSQL URL biçimleri async engine ile uyumsuzdu. | postgres/postgresql şemaları asyncpg için normalize ediliyor; URL yoksa modül importu çökmüyor. |
| URL içindeki yüzde kodlu parola Alembic interpolation hatası üretebiliyordu. | ConfigParser için yüzde karakteri kaçırılıyor. |
| Scraper sayfaları hata olduğunda açık kalıyordu. | Fixture ve detay sayfaları finally ile kapatılıyor. |
| API kapanışı sırasında kuyruk durumu temizlenmiyordu. | Worker iptali ve kuyruk temizliği finally bloğuna alındı. |
| Tek tarafın skoru olan kayıtlar pattern örneklem eşiğine dahil olabiliyordu. | İki tarafın skoru da sorguda zorunlu; geçersiz Pattern B periyodu reddediliyor. |
| Kalite raporu iki pattern kolonunu ve deplasman skoru eksikliğini kontrol etmiyordu. | Eksik alan kontrolleri tamamlandı; aktif maç yoksa kalite puanı sıfır. |
| Analiz zamanı naive UTC üretiliyordu. | Saat dilimli UTC kullanılıyor. |

## Frontend

| Bulgu | Uygulanan düzeltme |
| --- | --- |
| Ortam değişkeni olmadan SSR göreli API URL'siyle fetch yapıyordu. | Sunucuda mutlak localhost URL'si, tarayıcıda aynı origin proxy kullanılıyor. |
| URL sonundaki slash ve public/proxy hedefleri tutarsızdı. | Adresler normalize edildi; proxy public URL fallback'ini destekliyor. |
| Sepet eksik veya geçersiz yüzde içeren kayıtları kabul ediyordu. | Tüm gerekli alanlar, arşiv/periyot ve yüzde aralığı doğrulanıyor. |
| localStorage yazma hatasında sepet bileşenleri ayrışabiliyordu. | Ortak bellek fallback'i ve useSyncExternalStore aboneliği eklendi. |
| Maç değişiminde effect içi state sıfırlama ek render üretiyordu. | Maç ID'sine bağlı component kimliği ile state sıfırlanıyor. |
| Detay paneli başlangıç state'i lint hatası üretiyordu. | Saklı tercih hydration uyumlu external store üzerinden okunuyor. |
| Gün sekmesi İstanbul tarihiyle kullanıcının yerel haftanın gününü karıştırıyordu. | Gün hesaplaması İstanbul takvim tarihi üzerinde yapılıyor. |
| Bir seçeneğin yüzdesi sıfırsa geçerli pazar bütünüyle gizleniyordu. | Pazar seçeneklerinin tamamına bakılıyor; detay panelindeki benzer kontroller düzeltildi. |
| İlk arşivde yarı verisi yoksa ikinci arşivdeki geçerli pazar gizleniyordu. | Arşivlerin veri uygunluğu ayrı kontrol ediliyor. |
| Yetersiz arşiv mesajı iki arşiv için de 5 eşleşme diyordu. | Arşiv 1: 5, Arşiv 2: 1 şartı doğru gösteriliyor. |

## Doğrulama

- Backend: 160 pytest testi; uygulama ve testlerde Ruff kontrolü; pip bağımlılık tutarlılığı; CLI --help.
- Frontend: 146 Vitest testi; ESLint; TypeScript --noEmit; Next.js üretim derlemesi.
- Git diff whitespace kontrolü.
- Testlerde gerçek DB hesabı yerine yerel test URL'si kullanılıyor. API ve yazma testlerinde DB/scraper mock'ları kullanıldı; gerçek veritabanına yazılmadı.

## Canlı ortamda ayrıca doğrulanması gerekenler

- Günlük pipeline ve pattern recompute zamanlamaları mevcut workflow dosyalarında kapalı. Dosyalardaki açıklama önceki Supabase kotası sorununu belirtiyor. Güncel servis durumu doğrulanmadan bunlar açılmadı.
- Gerçek PostgreSQL bağlantısı, migration uygulaması ve canlı Nowgoal HTML'siyle uçtan uca scrape bu çalışmada doğrulanmadı. Özellikle bitiş işareti ve kaynak saat dilimi, canlı örneklerle tekrar kontrol edilmeli.
- Eski kayıtların olası yanlış saatleri/skorları otomatik düzeltilmedi. Kod düzeltmesi geçmiş veriyi geriye dönük onarmaz.
- Pattern sonuçları DB'de saklanıyor; yeni arşiv verisinin tahminlere yansıması recompute görevine bağlı. Bellek TTL'si DB'de saklanan pattern'leri yeniden hesaplamaz.
- Farklı maçların birleşik yüzdesi bağımsızlık varsayımıyla gösteriliyor. Aynı maçın birden çok seçimi için birleşik yüzde/oran artık hesaplanmıyor. İstatistiksel kalibrasyon ve Excel referansıyla doğruluk karşılaştırması yapılmadı.
- Yerel örnek API ile gerçek tarayıcıda 390×844 mobil görünüm, Bülten → Sonuçlar → Analiz gezinmesi, sepete ekleme/çıkarma ve 404 sonrası yeniden deneme kontrol edildi. Bu testler gerçek servis entegrasyonunu doğrulamaz.
- Dört BeautifulSoup/lxml deprecation uyarısı ve Vitest'in tsconfig-paths eklentisi uyarısı var; test başarısızlığı oluşturmuyor.
- Değişiklikler dağıtıma alınmadı; commit/push yapılmadı.

## İkinci inceleme: veri doğruluğu ve kullanım akışları

### Backend

- Ortak geçmiş temizleme katmanı eklendi. Yanlış takım, lig dışı kayıt, tekrar, analiz edilen maçın kendisi ve bilinen başlama tarihinden sonraki kayıtlar filtreleniyor; geçmiş kronolojik sıralanıyor. Filtreler, analiz ve trendler aynı kuralları kullanıyor.
- Eksik takım adları analize uygun kabul edilmiyor. Tutarsız devre skorları ikinci yarıda sıfır gole çevrilmiyor.
- Arşiv oluşturulurken belirtilen sezon analize aktarılıyor; geçmiş maçlar bugünün sezonuyla etiketlenmiyor.
- Analiz isteğine 90 saniye zaman aşımı eklendi. Kesin skoru bulunmayan geçmiş maçlar `pending` olarak dönüyor; başlama saatinden canlılık tahmin edilmiyor.

### Frontend ve geliştirme süreci

- API hata işleme ortaklaştırıldı: anlaşılır hata metinleri, zaman aşımı, iptal edilen istekler ve geçersiz JSON yanıtları ele alınıyor. Analiz ekranı yeniden denemede isteği tekrar başlatıyor; sayfadan ayrılınca isteği iptal ediyor.
- Bülten ve sonuç hata ekranlarına yeniden deneme eklendi. Mobil ana menü, dar ekran yerleşimi, uzun takım adları, kaydırma çubuğu, klavye odağı ve azaltılmış hareket tercihi iyileştirildi.
- Aynı maçın birkaç tahminine “birkaç maç” denilen etiketler “seçim” olarak düzeltildi.
- Taşınmış projeden kalan `.next/dev` önbelleği eski klasöre yazmaya çalışıyordu. Önbellek `.next/dev-before-audit` altında korundu ve geliştirme önizlemesi yeniden oluşturuldu. Turbopack ve Tailwind kaynak kökü çalışma projesine bağlandı.
- `.github/workflows/quality.yml` eklendi: backend test/lint ve frontend test/lint/typecheck/build kontrolleri. Yerel karşılıkları geçti; GitHub üzerinde workflow çalışması henüz doğrulanmadı.
- `tools/preview_backend.py` canlı servise bağlanmadan arayüz kontrolü için örnek API sağlar. Üretim verisi veya tahmin doğruluğu ölçümü değildir.

### Açık kalan mühendislik konuları

1. Üçüncü turda aynı maçın birleşik olasılık gösterimi kaldırıldı ve otomatik seçimler skor uyumluluğuyla sınırlandı. Gerçek ortak olasılık için ortak maç gözlemleri ve kalibrasyon hâlâ gerekli. Kullanıcının farklı pazarlardan elle topladığı seçimler uyumlu olmak zorunda değil; sepet bu durumda sayı üretmeden açıklama gösteriyor.
2. Tarihi veya maç kimliği olmayan eski geçmiş kayıtlarında gelecek veri sızıntısı tam olarak dışlanamaz. Kaynak veri kalitesi ve geçmiş kayıt onarımı ayrı çalışma gerektirir.
3. Pattern hesaplama zamanı/sürümü ve hesaplama başarısızlığı ayrı saklanmalı. Böylece “eşleşme yok”, “hesaplanmadı” ve “hesaplama başarısız” durumları ayrılabilir.
4. Canlı PostgreSQL, migration ve Nowgoal doğrulaması; kapalı günlük görevlerin kota ve hata izleme düzeniyle yeniden ele alınması tamamlanmadan üretim hazır kabul edilmemeli.

## Üçüncü inceleme: seçim tutarlılığı ve arşiv istatistikleri

- Aynı maçın marjinal yüzdeleri bağımsızmış gibi çarpılmıyor. Otomatik seçim kartlarından birleşik yüzde/oran kaldırıldı; sepette aynı maç birden fazla kez varsa hesap sonucu yerine açıklama gösteriliyor. Farklı maçlar için bağımsızlık varsayımı görünür hale getirildi.
- Otomatik grupların tüm seçimlerini karşılayan bir skor senaryosu aranıyor. KG Var + 1.5 Alt, birbiriyle çelişen sonuç/hibrit pazarlar ve ikili olarak mümkün olsa bile üçlü olarak imkânsız gruplar eleniyor. Arama 0–10 takım golüyle sınırlı; tanınmayan pazarlar otomatik gruba alınmıyor. Bu yöntem bir olasılık modeli değildir ve bazı mümkün grupları da dışarıda bırakabilir.
- Süper kombo için her seçimin kullanılan arşivinde en az 20 kayıt zorunlu. İki arşivli seçimde ikisi de eşiği geçmeli; başka bir tahminin yüksek örneklemi yeterli sayılmıyor.
- Aynı maç/periyot/pazarda yeni seçim öncekini değiştiriyor. Eski localStorage kayıtları otomatik silinmiyor; ilişkili eski seçimler de birleşik hesaplamayı kapatıyor.
- Sıfır yüzdeye karşılık yapay 1.000.000.000 oran üretilmesi kaldırıldı; sonlu oran gösterilmiyor.
- Backend handikap hesabı arayüzde gösterilen başlangıç skorunu ekliyor. Örnek: gerçek 1:0, handikap 0:1 → 1:1; önceki kod deplasmandan gol çıkarıyordu.
- Negatif, 30 üstü veya eksik dönem skorları istatistik örnekleminden çıkarılıyor. Devre skoru kesin skoru aşamaz; kayıtlı ikinci yarı, ilk yarı ve kesin skorla uyuşmalı. Geçersiz periyot sessizce maç sonuna dönüştürülmüyor.
- Yeni regresyon ve bileşen testleriyle toplam 101 backend / 115 frontend testi geçti. Ruff, ESLint ve TypeScript içeren üretim derlemesi başarılı. Bu turdaki arayüz metinleri bileşen testleriyle doğrulandı; önceki turun tarayıcı kontrolü yeni akışlar için tekrarlanmadı.

**Mevcut veriye etkisi:** Saklanmış pattern JSON verileri otomatik değiştirilmedi. Yeni handikap ve skor doğrulama kurallarının eski analizlere yansıması için kontrollü pattern recompute gerekir. Canlı veriye bu turda yazılmadı.

## Dördüncü inceleme: örneklem eşikleri ve hata kurtarma

- Pattern B minimum eşleşme eşiği artık skor doğrulamasından sonraki örnekleme uygulanıyor. Örneğin 5 kayıttan biri geçersizse minimum 5 şartı sağlanmış sayılmıyor.
- Pattern C aynı aday arşivi kullanırken ilk yarı, ikinci yarı ve maç sonu için geçerli örneklem eşiğini ayrı kontrol ediyor. Yeterli FT verisi olması eksik devre verisini yeterli hale getirmiyor.
- Minimum örneklem pozitif tamsayı olmak zorunda. Negatif/sonsuz/NaN toleranslar ve geçersiz oran değerleri sorgudan önce reddediliyor. Boş oran kümesi fuzzy modda tüm arşivle eşleşmiyor; karşılaştırılan skor anahtarları da aynı olmak zorunda.
- Bozuk bülten önbelleği biçimi veya kayıtları yeniden veri çekme yoluna düşüyor. Saat dilimsiz eski cache zamanları UTC kabul ediliyor; gelecekte görünen cache zamanı taze sayılmıyor. Kaynak erişimi de başarısızsa normal hata davranışı geçerli; veri uydurulmuyor.
- POST analiz yenilemede hem kilit bekleme hem scrape işlemi ortak 90 saniyelik süreye dahil. Süre aşımında 504 dönüyor; mevcut geçerli bellek önbelleği korunuyor ve istek iptal edilirken kilit bırakılıyor.
- 124 backend testi ve Ruff geçti. Yeni testler mock DB/scraper kullanıyor; canlı DB/cache veya dış kaynak üzerinde doğrulama yapılmadı. Frontend bu turda değişmedi; önceki 115 test ve derleme sonuçları geçerli.

## Beşinci inceleme: başarısız hesaplama ve eşzamanlı güncelleme

- Pattern hesaplama hataları artık başarılı “eşleşme yok” sonuçlarından ayrılıyor. B veya C hesaplarından biri hata verirse alt işlemlerin bitmesi bekleniyor ve tüm hesaplama başarısız sayılıyor; altı kolon için eksik sonuç paketi dönülmüyor. Böylece bağlantı hatası nedeniyle eski pattern'lerin NULL ile ezilmesi önleniyor.
- API bu hesaplama hatasında iç hata ayrıntılarını açığa çıkarmayan, önbelleğe alınmayan 503 yanıtı veriyor. Başarısız manuel yenileme önceki bellek sonucunu değiştirmiyor. Başarılı hesaplamanın gerçekten boş çıkması hâlâ None olarak saklanabilir.
- Pattern yazma hataları yeniden deneme yapan CLI çağrısına iletiliyor; başarısız yazma sessizce başarılı sayılmıyor. API lazy backfill yolunda ise hesaplama başarılı olup yalnızca cache yazımı başarısızsa, hesaplanan yanıt log kaydıyla birlikte kullanıcıya sunuluyor.
- Arka plan DB analizleri manuel/ön plan analizlerle aynı maç kilidini kullanıyor. Bu kilit tek API süreci içinde geçerli; ayrı worker veya pipeline süreçleri için dağıtık kilit ya da sürüm kontrollü yazma henüz uygulanmadı.
- 132 backend testi, Ruff ve diff whitespace kontrolü geçti. Yeni testler dört hesaplama kolunun hatalarını, gerçek boş sonucu, yazma hatasının iletilmesini, 503 yanıtını ve arka plan kilit beklemesini kapsıyor. Canlı veriye yazılmadı; frontend bu turda değişmedi.

## Altıncı inceleme: frontend tarihleri ve API sınırı

- Bülten/sonuç URL tarihleri gerçek takvim tarihi olarak doğrulanıyor; tekrarlanan date parametreleri kabul edilmiyor. Geçersiz değerlerde temiz sayfa adresine yönlendirme yapılıyor. Bülten için backend ile aynı -30/+14 gün sınırı uygulanıyor; sonuç arşivi bu sınıra tabi değil.
- Gün sekmelerinin ilk render tarihi sunucudan aktarılıyor. Gece yarısında SSR ile hydration arasında takvim günü değişmesi nedeniyle farklı sekmeler üretilmesi önleniyor. Açık sayfanın gece yarısı otomatik yenilenmesi bu değişikliğin kapsamında değil.
- Bülten ve sonuç yanıtları liste/alan türleri, maç kimlikleri, tekrar eden kimlikler, başlama zamanı ve skor alanları açısından kontrol ediliyor. Bozuk veri sessizce boş bülten gibi gösterilmiyor; mevcut hata/yeniden deneme ekranı kullanılıyor. Bitmiş maç için iki kesin skor da zorunlu.
- Yanıt gövdesi okunurken iptal veya zaman aşımı olması artık geçersiz JSON hatası olarak raporlanmıyor.
- 133 frontend testi, ESLint ve TypeScript kontrolünü içeren üretim derlemesi geçti. Backend bu turda değişmedi; son doğrulama 132 test. Yeni akışlar birim testleriyle doğrulandı; bu turda canlı API ve tarayıcı kontrolü tekrarlanmadı. Ayrıntılı analiz ve maç özeti doğrulaması bir sonraki (yedinci) turda tamamlandı.

## Yedinci inceleme: analiz ve maç özeti yanıtları

- Analiz yanıtı artık runtime doğrulamasından geçiyor. Dönen maç kimliği istenen kimlikle eşleşmeli; üç periyodun skor listeleri, altı pattern alanı ve trend blokları beklenen yapıda olmalı.
- Tüm frontend pattern yüzdeleri sonlu ve 0–100 aralığında olmalı. Eksik yüzdeler, geçersiz örneklem sayıları, bozuk skor histogramı ve trend alanları hata olarak ele alınıyor. Yüzde alanları listesi TypeScript modeliyle derleme sırasında eksiksizlik kontrolünden geçiyor; alanların backend modelinde bulunduğu da kontrol edildi.
- Başarılı ancak eşleşmesiz null pattern'ler ve atlanan maç yanıtları kabul edilmeye devam ediyor. Geçersiz veri mevcut hata/yeniden deneme akışına yönleniyor; sayısal tahmin bileşenlerine aktarılmıyor.
- Maç özeti uç noktasında kimlik, takım, skor ve skor listesi doğrulaması eklendi; tekrar eden maç kimlikleri reddediliyor.
- 146 frontend testi, ESLint ve TypeScript içeren üretim derlemesi geçti. Yeni testler geçerli/bozuk analiz ve özet yanıtlarını, yanlış maç kimliğini, eksik yüzdeleri ve atlanan maç durumunu kapsıyor. Kontroller API mock'larıyla yapıldı; canlı servis ve tarayıcı testi bu turda tekrarlanmadı. Bu şema kontrolleri istatistiksel kalibrasyonun yerine geçmez.

## Sekizinci inceleme: scraper skor ve tarih ayrıştırması

- Sadece devre skoru bulunan `(1-0)` gibi hücrelerin bitmiş maç skoru sayılması engellendi. Skor metni artık tam eşleşmeyle okunuyor; negatif skorun içinden pozitif bir parça alınmıyor. Açıklamalı/bozuk metinler kesin sonuç olarak yorumlanmıyor.
- Geçmiş skorlarında 0–30 sınırı uygulanıyor; devre skoru kesin sonucu aşıyorsa devre bilgisi dışlanıyor. Ana maçın kesin skoru eksik, negatif veya sınır dışıysa kısmi devre skorlarıyla birlikte reddediliyor.
- Geçmiş ve ana maç tarihleri ortak ayrıştırıcı kullanıyor. ISO ve mevcut slash/AM-PM biçimleri destekleniyor; açık saat dilimi UTC'ye çevriliyor. Saat dilimsiz kaynak tarihlerinde önceki UTC varsayımı korunuyor. Bu varsayım canlı kaynakla ayrıca doğrulanmalı.
- 145 backend testi, Ruff ve diff whitespace kontrolü geçti. Yeni HTML fixture testleri yalnızca devre skorunu, negatif/aşırı skorları, düz metin final+devre skorunu ve tarih biçimlerini kapsıyor. Canlı HTML doğrulaması yapılmadı; sıkı ayrıştırıcının yeni sağlayıcı biçimlerini reddetmesi durumunda örnek HTML üzerinden kontrollü destek eklenmeli.
- Frontend bu turda değişmedi; önceki 146 test ve üretim derlemesi sonuçları geçerli. BeautifulSoup/lxml uyarıları yeni scraper testlerinde de görülüyor; test başarısızlığı oluşturmuyor.

## Dokuzuncu inceleme: sonuç güncellemede veri bütünlüğü

- Kesin skor değişmemiş ve yeni devre bilgisi gelmemişse mevcut tutarlı devre bilgisi korunuyor. Kesin skor düzeltilmişse eski devre bilgisi doğrulanmadan taşınmıyor. Yeni geçerli devre skorundan diğer yarı hesaplanıyor; çelişkili veya kısmi skor güncellemesi reddediliyor.
- Sonuç güncellemesi mevcut aktif satırı işlem içinde `FOR UPDATE` ile kilitleyip skorları birleştiriyor. Başlangıç listesinden sonra silinen kayıtlar güncellenmiş sayılmıyor; atlanan kayıt sayısı CLI ve log çıktısına ekleniyor. Kaynaktan dönen maç kimliği de hedef kayıtla karşılaştırılıyor.
- İşlenecek maç yoksa tarayıcı açılmıyor. Veri doğrulama hatası aynı girdilerle üç kez denenmiyor; diğer işlem hataları mevcut yeniden deneme yolunu kullanıyor.
- 155 backend testi ve Ruff geçti. Testler skor birleştirme, değişmiş kesin sonuç, çelişkili devreler, yeniden deneme ve silinmiş/boş kayıt davranışlarını kapsıyor. Satır kilidinin gerçek PostgreSQL altında eşzamanlı çalışma testi yapılmadı; testlerde DB ve scraper mock'ları kullanıldı. Analiz upsert ve pattern güncelleme akışlarında süreçler arası sürüm kontrolü hâlâ ayrı konu.

## Onuncu inceleme: eski işlemlerin yeni analizi ezmesi

- Analiz upsert sorgusu aktif kayıt ve `analyzed_at` sıralaması koşulu taşıyor. Daha eski analiz yeni kaydı değiştiremiyor; silinmiş kayıtlar da güncellenmiyor. Koşul nedeniyle yazılmayan sonuç başarı sayılmıyor ve aynı veriyle tekrar denenmiyor.
- Lazy backfill ve CLI pattern recompute yazımları, hesaplamada okunan `analyzed_at` değeri hâlâ aynıysa uygulanıyor. Tarihi olmayan eski kayıtlarda `IS NULL` koşulu kullanılıyor. Bu sırada değişen veya silinen kayıt için yazma reddediliyor.
- API eski analiz/pattern yazma çakışmasında 409 yanıtı veriyor; eski hesaplamayı başarılı yanıt olarak bellek önbelleğine aktarmıyor. Genel bağlantı hataları için önceki hata davranışı korunuyor.
- 160 backend testi, Ruff ve diff whitespace kontrolü geçti. Testler PostgreSQL sorgu derlemesini, sıfır satırlı yazma sonucunu, tekrar denememe ve API backfill çakışmasını kapsıyor. Canlı PostgreSQL eşzamanlılık testi yapılmadı; migration gerekmiyor.
- Sürüm belirteci mevcut analiz zamanı. Aynı analiz üzerinden paralel iki pattern recompute işlemini veya analiz zamanı değişmeden arşive eklenen sonuçların sürümünü ayırt etmez. Ayrı monotonic kayıt/arşiv sürümü ve hesaplama zamanı alanları daha kapsamlı çözüm için açık kalıyor.
