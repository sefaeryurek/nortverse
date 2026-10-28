# 01 Backend denetimi (28 Ekim) — özet kayıt
Test: 1127 geçti, ruff temiz. Hızlı uçlar: coupon-matches 9ms, coupons 11ms, ht-strategy sıcak 15-22ms, fixture önbellek 66ms, perf summary 0,32sn. Yavaş: /api/odds 2-10sn, POST coupons 7-20sn (iki kez 503), ht-strategy soğuk 8sn, fixture soğuk kazıma 45sn→503.

KRİTİK
K1 Kupondaş kapanmış periyoda kupon: kaynağın t=10 MatchState hep 0 (2993842 canlı ve bitmiş halde 0) → _FINISHED_STATES/(2,3) ölü; DB skoru update-scores ile ~11 saat sonra; İY dakikası op satırından ("03") alınıyor, ou'da "45". Fix: _closed_reason canlı panoya (live_snapshot/source_board kodları 1/2/3/-1) + zaman sınırları (İY: başlama+45dk, MS: +115dk), dakika op/ou içinde en yeni mt'den, 45+/90+ ayrıştır, canlı satır >2dk eskiyse kabul etme; testler. M.

YÜKSEK
Y1 update-scores: pipeline_cmds._run döngüsünde try yok; 27 Eki 25 Ekim goto 3x timeout → çıkış 1, resolve_pending/settle_pending çalışmadı. 27 Eki bugünün sayfası boş → "0 güncellendi 331 atlandı" başarılı sayıldı. Fix: gün başına try, finally'de resolve+settle, hata varsa kod 2; boş sayfa+beklenen maç>0 = hata. S.
Y2 SSR iç anahtar = admin "sunucu" (auth.py:145) → admin olmayan kullanıcı da Playwright tetikler (28 Eki fixture 45sn 503). Fix: Next çerezi de iletir, backend gerçek kullanıcıyı çözer, _SERVER_USER is_admin=False. M.
Y3 Ertelenen maç: 3079945 v4 kaydı 18 Eki, maç 28 Eki'ye ertelendi, karar 243 saat önce geçerli sayılıyor (sync_kickoffs sadece kickoff değiştiriyor). 3003600 (23 Eki) 38 defter kaydı + kupon sonsuza dek bekliyor. Fix: kickoff >6 saat kayınca önceki defteri invalidate(reason=rescheduled), yeniden dondurma (snapshot anahtarı — migration olabilir), postponed+3 gün → kupon bacağı void, coupon_status void=iade. M-L.
Y4 COND tablosu zaman penceresiz; arşiv tamamlama NED 1387 / GER 1048 eski maç ekledi → live-arch-v2 kapısı, live-2h min(P,COND), v1.1 değerli etiketi sürüm artmadan kayıyor; ResultsWatch 5 dk'da yeniden kuruyor; geçmiş isabet tabloları eski arşivle. Fix: cond_years penceresi parmak izine + live-arch-v3 gölge, ya da arşiv sonrası backtest yenile + veri sürümü kaydı; results_marker sadece son 30 gün. M.

ORTA
O1 _poisson_decisions dondurulmuş maçta defter satırı yoksa anlık yeniden hesaplıyor (bitmiş maçta sızıntı, görünen≠kaydedilen). Fix: details.poisson_evaluated, dondurulmuşta defter boşsa []. S.
O2 Ana canlı kayıt live-ms-v1'e bağlı; predict_live hata verirse v1.1 de yazılmaz; dondurulmuş testi live-ms-v1 satırına bakıyor. Fix: try ile sar / ana kaydı v1.1 yap. S.
O3 Login limiter IP hep 127.0.0.1 → arkadaş 8 yanlışta sahibi kilitler; analiz hız sınırı ortak; _failures sınırsız. Fix: kullanıcı adı + global eşik, TRUSTED_PROXIES, kimlik bazlı hız sınırı. S.
O4 routes_ht._refresh eşzamanlı ikinci istekte kayıtsız maç düşüyor; ağ çekerken DB oturumu açık (havuz 5+5); wait_for thread'i durdurmuyor; 8sn. Fix: _inflight paylaşılan Task, çekim oturum dışında, ayrı sınırlı executor. M.
O5 İY panosu model_pct geçmiş günlerde güncel modelle (sızıntı). Fix: bitmiş+snapshot yok → None ya da başlama haftası modeli. S.
O6 load_or_fetch boş yanıtla iyi geçmişi eziyor (hipotez). Fix: boş/eski ise yazma. S.
O7 Parmak izi boşlukları: ht-display-v1 takım modeli parmak izi yok; live-2h-v1 Poisson yok; live-arch-v2 c4/d4 sonrası sürüm atlamadı; poisson-v1 91 kararla ekrana alındı (kullanıcı kararı, protokol notu). Fix: parmak izlerine ekle, sürümleri artır (ht-display-v1.1 vb.). S.
O8 13x "Future exception was never retrieved" Playwright TargetClosedError: live_snapshot._refresh 30sn bütçe < fetch_live_scores ihtiyacı (goto 30sn×3 + 12sn); canlı maç yokken de her 45sn Chromium. Fix: bütçe parametresi, aday yoksa sadece AJAX pano. S.
O9 coupon_status yarım kayıpta "refund" yazıyor → "partial"; settle_pending GET içinde (hata→500, skor düzeltmesi kupona yansımaz); create_coupon lig kontrolü yok. S.

DÜŞÜK
D1 /api/health bg_queue hep 0 (import anında kopya). D2 ADMIN_API_KEY yok → /api/admin/quality, /api/score-validation her girişliye açık. D3 süresi dolan oturum silinmiyor; WS sadece bağlanırken kontrol; çerez secure yok. D4 live-freeze deneme modu sync_kickoffs ile DB'ye yazıyor; --match bitmiş maçta sızıntı; v1.1 "Gölge" yazıyor. D5 eski docstring'ler (live_poisson, routes_live_ht, auth.py:7, routes_coupons:29). D6 fixture(request=None) auth açıkken AttributeError. D7 goal_events._fix_sides skorsuz satırda taraf kayabilir (şu an 358/358 uyuşuyor). D8 routes_performance._load limit 50.000 (~2 ayda "tümü" kesilir); predictions limiti süzgeçten önce.

LOG (19-28 Eki): 13 Playwright future (O8); 1 ASGI 500 /api/odds eski kod (düzeldi); 2 POST coupons 503 (20sn eski timeout); 1 fixture 503 (Y2); 2 boş livescore; 11 başlama saati güncelleme; 2 login 404 (eski backend, geçici); 3 "Backend durdu kod 1073807364" = 0x40010004 sistem sonlandırma (26 Eki 05:17, 14:55, 27 Eki 21:46 = arşiv işinin öldüğü dakika → PC kapanma/oturum kapanma). start-backend.bat: STOPPED boş → uptime negatif → 10dk sayaç sıfırlama hiç çalışmaz; fix: STOPPED boşsa atla. 27 Eki 21:46 – 28 Eki 09:42 backend kapalı; Roma-Cagliari devre arası kaydı yok. scores.log: 27 Eki 19:04 kod 1 (Y1), 21 Eki 18:00 kod 1, 17-18 Eki eski bat, 15-16 Eki Docker başlamadı.

SORUNSUZ: resolver defterdeki 81 kombinasyonu çözüyor; skoru olup çözümsüz satır 0; ara bellekler sınırlı; kilitler doğru; Poisson/v5 sızıntısız; gün sınırları İstanbul; N+1 yok.

ÖNCELİK: K1 > Y1 > Y3 > Y4 > Y2 > O1+O2 > O3 > O4+O6 > O7 > O8 > O5,O9 > D1-D8.
