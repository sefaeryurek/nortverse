# 04 Strateji performansı (28 Ekim) — özet kayıt
Scriptler: scratchpad\agents\strategy\ (dbro.py, common.py, t1..t9). Sayım uygulamanın dedupe/summarize fonksiyonlarıyla.

KARNELER (ana lig, tekil karar):
- live-poisson-v1.1 EKRANDA: 2/2 (veri toplanıyor).
- live-poisson-v1 gölge bitti: 68 karar %97,1 (gösterilen 91,8) [89,9-99,2]; gölge lig 23 %95,7.
- live-arch-v2: 56 %89,3 (gös 92,6); gölge 19 %89,5.
- live-arch-v1: 123 %75,6 (gös 98) BEKLENTİNİN ALTINDA (emekli).
- live-ms-v1 gölge: 198 %65,7 (gös 66,1) yolunda, tabana göre −2,7; medium kademe 15 karar %40 (gös 64) bozuk; Serie A 31 %45. Gölge lig 70 %74,3.
- live-2h-v1: 17 %88,2 (gös 81,8); MS dep 1.5 alt 12 %91,7; 2Y ev gol 7 %85,7.
- ft-display-v5 EKRANDA: 29 çözülmüş %58,6 (gös 55,7), lig favorisi %44,8 (+13,8); bilgi Ü/A-KG 116 %57,8 yolunda (+9,5 taban); v5 high kademe 29'un 27'si → ayırt edici değil.
- ft-display-v4.1 gölge: 34 %55,9; bilgi 108 %52,8.
- market-summary-v2 EKRANDA (Ana Pazar Özeti): 1.460 tekil (sayım 1.349 ana) %48,1, gös 54,5, üst sınır 50,8 → BEKLENTİNİN ALTINDA; gölge lig 1.028 %47,7 gös 52,9 aynı. Kovalar: 50-60 gös 54,5 gerçek 41,1; 70-80 75,2/68,2; 80-90 83,8/76,6; 90-100 93,9/83,3. En kötü: MS fark %24 (gös 31,8), MS+2.5 %26,7 (36,1), İY/MS %25,9 (32,8), 2Y sonuç %37,1 (46,2), 2Y ÇŞ %67 (78). En iyi: İY KG %85,5 (77,8). Arşiv: A3 901 %53,1 (55,5), A2 266 %36,8 (51,7), A1 182 %40,1 (54). Backtest koşusu YOK.
- market-summary-v1: 258 %38,8 (gös 57,8) altında (emekli).
- ht-display-v1: 29 satır, 0 çözülmüş.
Lig kırılımı yorumlanamaz (<15/lig).

BACKTEST UYUMU: Poisson #11 %91,8 vs canlı 97,1 aralık içi; v2 #13 92,2 vs 89,3 içi; v5 #12 62,7 vs 58,6 içi; live-2h #14 84,7 vs 88,2; live-ms #3 59,3 vs 61,6. Tek ayrışan Ana Pazar Özeti (arşiv frekansı olasılık gibi sunuluyor). Geçmiş isabet çipi #15'in %38'i gölge lig (etki ~0,2 puan). COND tablosu bugün kurulursa #13'ten 420 karar farkı (tekrar üretilebilirlik).

KAFA KAFAYA canlı: ortak 65 pazar Poisson %95,4 = v2 %95,4 (63'ünde aynı seçim); sadece Poisson 28 → %100; sadece v2 10 → %50.
TRIVIAL: canlıda Poisson kararlarının %96'sında COND ≥%80; backtest'te %89. Değerli kararlar %87,9-88,4 (kalibre). v2 tamamen COND tekrarı.
COND-only temel (3 yıl sızıntısız, ana lig 6.080 maç): COND-only 7.024 karar %91,1 (gös 91,8); Poisson #15 7.563 %92,3; v2 #13 5.999 %92,2; P∩C 5.612 %93,6; C\P (Poisson eliyor) 1.412 %81,4; P\C (Poisson ekliyor) 1.951 %88,5; v2∩C 92,3, C\v2 86,4. Gölge lig benzer. Poisson net katkı: COND-only'ye göre +1,2 puan, aynı kapsam.
v5 vs v4.1: 26 ortak maç hepsi aynı seçim %61,5; sadece v5 1/3; sadece v4.1 3/8.

DONDURMA ZAMANI: Poisson p50 49dk maks 67; v2 maks 67; live-ms-v1 maks 97 — 6 maç/17 satır 24 Eki 18:37 ~97. dakikada donduruldu (3008288, 3008290, 3008292, 3008294, 3008295, 3013737), 13/17 tuttu ve GEÇERLİ sayılıyor. Sebep: freeze_live_prediction ana live-ms-v1 satırını window_ok'tan bağımsız yazıyor.
KAPSAMA 19-26 Eki: ana 50/57 (%87,7), gölge 26/36 (%72). Kaçanlar 19.10 22:15 ve 24.10 14:00-17:00: 24 Eki 14:39 backend sonlandırıldı, yeniden başlatma "Port 8000 başka bir sunucuda" diyerek açılmadı; 18:35'e kadar portu loglamayan başka süreç tuttu (hipotez: elle açılmış serve/ajan sunucusu), 18:35'te 6 maç late_score_changed (logda 114 tekrar, maç başına 18-22 tur). Yön bozulmasına kanıt yok ama kapsama ~%85 raporlanmalı. start-backend.bat negatif süre, gece 0x40010004 her gün.

COND KAYMASI: NED +1.513 (havuzun %31'i), GER +1.048 (%22). Eski tablo kayıttaki COND'u birebir üretti. 189 kayıtlı kararın 10'unda fark ≥1 puan, maks 2,1 (2996185 MS Ü1.5 86,6→84,9; 2996186 Ü3.5 üst 87,4→89,5). Şimdiye kadar kapı/etiket değişmedi; eşik yakınında değişebilir.

GÖLGE LİGLER: Poisson 23 %95,7; v2 19 %89,5; live-ms 70 %74,3; v5 7/9; v4.1 14 %64,3; v5 bilgi 70 %50 (taban −10); msv2 852 %47,7 altında.

BULGULAR: 1 Yüksek msv2 altında (ekranda); 2 Yüksek live-ms-v1 97. dk geç dondurma geçerli sayılıyor; 3 Yüksek kapsama ~%85; 4 Orta COND penceresiz; 5 Orta Poisson %89 trivial; 6 Orta v2 kapısı 3 yılda +6 puan eleme ama kapsamı Poisson'dan %10 düşük; 7 Orta parmak izi açıkları + 48 saat ihlalleri; 8 Düşük isabet çipi gölge lig içeriyor; 9 Düşük live-ms medium bozuk; 10 Düşük v5 high ayırt etmiyor; 11 v1.1 ve ht-display veri başlangıcında.

HÜKÜM: msv2 altında → askı/kalibrasyon kullanıcı kararı; live-ms-v1 bilgi katmıyor; <100 olanlar (Poisson v1.1, v2, live-2h, v5, v4.1, ht-display) değiştirilmesin. Tahmini 100'e ulaşma: Poisson ~2 hafta, v5 ~3-4 hafta, live-2h ~5-6 hafta (haftada ~60 ana lig maçı).

EYLEM:
A1 live-ms-v1 ana satırı archive_freeze_allowed penceresine bağla (live_ledger.freeze_live_prediction); 17 geç satır invalidate (kullanıcı onayı); sürüm live-ms-v1.1 ya da kaydı durdur. S.
A2 3026759 ve 3003600 ayıkla; ertelenen maç N gün sonra void (ledger.resolve_pending, CAPTURE_HORIZON); çözücü stats-v2. S.
A3 COND zaman penceresi (kickoff ≥ as_of − 3 yıl) parmak izine; live-arch-v2.1, live-2h-v1.1, live-poisson-v1.2; 3 yıllık backtest kullanıcı onayıyla. M.
A4 parmak izi açıkları kapat (v2 PATTERN_ALGO_VERSION, live-2h team_model_fingerprint, ht-display takım modeli). S.
A5 Ana Pazar Özeti: "arşiv frekansı" etiketi veya Dixon-Coles/Poisson olasılığı; fark, İY/MS, MS+2.5 gizle/soluklaştır; market-summary-v3 gölge. Kullanıcı kararı. M.
A6 geçmiş isabet çipi sadece ana lig (load_hit_table). S.
A7 kapsama karnesi /coverage + start-backend.bat süre düzeltmesi. S-M.
A8 v5 kademesini avantaj büyüklüğüne bağla → ft-display-v5.1 gölge. S.
Yeni gölge öneriler: live-poisson-v1.2 trivial/değerli rozeti ("İY skoru zaten söylüyor"); live-cond-filter-v1 (COND≥85 ama Poisson <85 → uyarı, dilim %81 tutuyor); live-comeback-v1 filtre testi — İY farkı 1, λ(geride)/λ(önde): <0,8 1.224 maç geride kazanır %6,8 kaybetmez %24,8; 0,8-1 442 11,1/32,4; 1,0-1,6 687 12,5-17,8/39,7-46,4 (2Y gol %64,8); 1,6-2,2 205 24,4/57,6 (2Y gol 77,6); ≥2,2 109 43,1/70,6 (2Y gol 79,8) → live-2h "geride 2Y gol" eşiği testi, ≥2,2 için ÇŞ "orta güven" gölge; market-summary-v3 (v5 ızgarası).
