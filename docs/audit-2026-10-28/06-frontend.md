# 06 Frontend (28 Ekim) — özet kayıt
tsc 0, eslint 0, vitest 313/313 (vite-tsconfig-paths gereksiz uyarısı). >1000 satır yok (degerlendirme 861, DetailedStats 586, api.ts 580, sonuclar 559, PerformancePanel 552). Dosyalar: scratchpad\agents\frontend\ (i18n-diff.js, unused.js, unusedkeys.js).

TEYİTLER
A1 Yüksek safeNext açık yönlendirme giris/page.tsx:7-10 (%5C, %09, %0A) → lib/safe-next + URL origin + vitest. S.
A2 Yüksek proxy.ts:21-24 fail-open → yalnız res.ok, diğerleri 503; proxy birim testi. S.
A3 Orta SSR admin: kullanıcıya özel veri SSR'da çekilmiyor (kupondas, canli client); sızıntı yok. AMA analyze/[match_id]/page.tsx:27 SSR analyzeMatch + bulten getFixture → admin olmayan /analyze/<id> ile Playwright tetikler. Fix: çerez ilet, kullanıcıya özel uçlara no-store. M.
A4 Next 16.4.x yükseltmesinde kontrol: proxy matcher (/girisX, /apiary korumasız — sayfa yok), AbortSignal.timeout, allowedDevOrigins, turbopack.root, fetch revalidate varsayılanları (11 çağrı), searchParams Promise, eslint-config-next 16.2.4 sabit. Sonra tsc/eslint/vitest/e2e + proxy elle.
A5 Orta dev: __nextjs_source-map 204 oturumsuz; _next/static girişsiz (tüm istemci kodu + sözlükler); error overlay. Fix: next build+start, allowedDevOrigins daralt, paylasim-ac.bat prod.
A6 Orta MarketSummary.tsx:42-69 %pct ≥75 yeşil + dolu çubuk; sadece ou_25/kg soluk (confidence.ts:402 INFORMATIONAL_MARKETS); fark, iy_ms, ms_25_combo, hnd_* tam parlak (404-414); "olasılık değildir" sadece altta 10px. Seçenekler: başlık "Arşiv sıklığı" + 7/13 gösterimi; yeşil/çubuk kaldır; fark/iy_ms/ms_25_combo(/hnd) INFORMATIONAL'a (tek satır); başlıkta defter karnesi (gösterilen 54,5 → gerçek 48,1); varsayılan kapalı akordeon.
A7 Düşük İY 0.5 alanları ekranda sızmıyor (DetailedStats 299-306, 332-341 isFT korumalı; confidence 243-272 ftOnly). isMarketActive ftZeroCheck'i kullanmıyor (adı yanıltıcı). S.
A8 Orta "değer" çağrışımı: LiveArchiveView.tsx:129-133 %99 ÇŞ X2'ye yeşil "En iyi" rozeti (~1,01 oran); TopPicks "avantaj" (lig ortalamasına göre). Fix: "En yüksek olasılık", her yüzdeye "≈ adil oran 1/p", "lig ortalamasının +Y puan üstü". S.

YENİ
B1 KRİTİK kupondaş İY kapanışı (backend K1 ile aynı): /api/odds/2993842 2. yarıda "live minute 03 0-0", ht closed null; prediction frozen İY 2-4, maç 2-6. OddsPanel (kupondas/page.tsx:63-85) closed boşsa İY tıklanabilir. Fix: backend _closed_reason match_ht_observations / phase ht,2h / kickoff+47dk; frontend now−kickoff>47dk → İY kapalı, yanlış canlı skor gizle; testler. M.
B2 Yüksek Ü/A çizgisi kaydederken sessizce değişir: createCoupon line/seen_odds göndermiyor (page.tsx:193), backend o anki çizgi (routes_coupons 146-159); OddsPanel yenilenmiyor; yanıt sadece {id}. Fix: line + seen_odds gönder, değiştiyse 409 + onay; 30sn'de oran yenile; yanıt kaydedilen bacakları dönsün. M.
B3 Yüksek istemcide 401 yönetimi yok (api.ts:35-37): kupondaş boş liste "Henüz kupon yok" der, canlı sessiz; fix 401 → /giris?next=, taslak sessionStorage, hata vs boş durumu ayır. S/M.
B4 Yüksek önbellekli fetch + şekil değişikliği çökme sınıfı: revalidate tablosu (fixture/results 15/300, pattern-status 300, evaluation 300, perf summary 120, backtest runs 30, backtest summary 3600, live-matches/predictions/ht-strategy 60); dev'de .next/cache/fetch-cache diskte kalıcı. Doğrulama sadece fixture/results/analyze. Çökme noktaları: iy 79,120,145,147; degerlendirme 94,173,188,189; PerformancePanel 151,184; LiveArchiveView 93,152; kupondas 73-82 (m.result![s]). Fix: uç bazlı doğrulayıcılar (validHtStrategy, validPerformanceSummary, validMatchOdds), şema sürümü önbellek anahtarına, /iy ve backtest summary no-store/düşük, ortak fmtNum null→"—". M.
B5 Orta mobilde çıkış/dil/gölge lig yok (Sidebar.tsx:203-275 hidden md:flex; mobil alt menü 279-313 sadece 6 link) → "Daha fazla" menüsü. S/M.
B6 Düşük (hipotez) mobil alt menü 360px taşma; BetCart mobil çubuğu içerik örtüyor → kısa etiketler, ek alt boşluk, e2e 360px.
B7 Düşük/Orta i18n: tr 561 = en 561 anahtar tam eşli. Sabit TR: tüm metadata (meta.* kullanılmıyor), api.ts hata metinleri (87,107), SSR errorMessages hep TR, backend Türkçe metinleri aynen (kupondaş closed, 503), Sidebar aria. Yüzde biçimi 6 farklı yardımcı (LiveArchiveView.fmtPct dil yok, degerlendirme %x EN'de, PerformancePanel 184/274). ~25 ölü anahtar (meta.*, live.prediction.* 16, topPicks.emptyMessage vb.). Fix: lib/format.ts formatPct/formatOdds, generateMetadata, backend hata kodları, parite testi CI. M.
B8 Düşük/Orta canlı: REST hatası veri varken gösterilmiyor (canli/page.tsx:275); setNow 15sn tüm sayfa render, MatchCard memo yok; değerlendirme canlı listesinde v1.1 "Model (0)" (PerformancePanel.tsx:538-540, n>0 değilse gizle).
B9 Düşük değerlendirme: API ile tutarlı (v5 145 karar %57,9 beklenen 58,3 on_track); sürüm sabitleri elle (page.tsx:553-564) → backend rule_versions göster/uyar; Pattern geçmişi sekmesi ana lig dışını sayıyor (26 Eki 39 maç, Singapur dahil), 2/2 %100 yeşil → <10 nötr; PerformancePanel:268 ci_high null → "undefined".
B10 Düşük giriş: dil değiştirme yok, girişliyken /giris → /bulten yok, title yok, 429 kalan süre yok.
B11 Düşük kupondaş a11y: tablist eksik (aria-pressed daha doğru), aria-live yok, ✕ küçük, taslak kayboluyor, akış otomatik yenilenmiyor/sayfalama yok, MAX_LEGS gösterilmiyor, idempotency yok (hipotez).
B12 Düşük ölü kod: i18n locales export kullanılmıyor; gereksiz export'lar.
B13 Düşük performans: iki sözlük client pakette (~60KB) → sadece aktif dil; DetailedStats next/dynamic; proxy her istekte /api/auth/me (prefetch'lerle 6 tur) → 30sn bellek önbelleği.
B14 Düşük: validMatchList ya hep ya hiç → bozuk satırı ele; leagues.ts German 2. Bundesliga, Dutch Eredivisie bayrak yok ("⚽ German 2."); çıkışta nortverse_bet_cart temizlenmiyor.

ÖNCELİK: B1 > A1 > A2 > A4 > B2 > B3 > B4 > A5 > A3 > A6+A8 > B5 > B7 > B8/B9/B14 > B6/B10-B13.
UX ÖNERİLERİ: her yüzdenin yanında ≈ adil oran; kupondaşta piyasa vs model olasılığı yan yana; kupon karnesi (kullanıcı başına sayı/tutma/getiri); taslak sessionStorage; canlı bildirimi (sekme başlığı "(1) Canlı" + tarayıcı bildirimi); mobil "Daha fazla"; değerlendirmede tek satır karne; Ana Pazar Özeti varsayılan kapalı.
