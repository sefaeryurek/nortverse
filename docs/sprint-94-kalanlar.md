# Sprint 94 — kalan maddeler takibi

Kaynak: `docs/sprint-94-plan.md` (bölüm 4 ve 5) + `docs/audit-2026-10-28/01..11`. Kullanıcı kararı (29 Ekim):
"küçük veya büyük farketmez 11 ajanın belirlediği her şey yapılacak, sırasıyla." Kararlar K1–K22 onaylı, tekrar sorulmaz.
Her madde bitince bu dosyada işaretlenir ve commit numarası yazılır.

## Bitti (94.1–94.34)

A1, A2 · B1, B2, B3, B4, B7 · C1, C2 · D1, D2, D4, D5, D3 (yerel kısım: D: kopyası + aylık geri yükleme) ·
E1–E7, E9 · F1–F5 · H1, H2, H3 (94.34) · I1 (gece görevi kuruldu), I2, I3 · J1–J6, J8–J10 · K-1, K-2 · L1, L2 · M1–M3, M6

## Kullanıcının yapması gereken (yönetici izni)

- [x] `install-tasks.ps1` yönetici olarak çalıştırıldı (29 Ekim öğlen): Frontend, HealthCheck, LongJobs, RestoreTest,
  RunPipelineAll, RunPipelineTomorrow kuruldu; UpdateScores2 kaldırıldı.
- `backend/.env`'ye `ADMIN_API_KEY` (isteğe bağlı; yoksa admin uçları sadece yönetici hesabıyla).

## Bekleyen — dış koşula bağlı

| Madde | Koşul |
|---|---|
| A3 DB portu + şifre | arşiv tamamlama ve gol çekimi bitince, maç saati dışında (Runbook: plan A3) |
| Faz G runbook (13 adım) | arşiv tamamlama bitince |
| Faz N inplay-v1 | gol dakikası çekimi bitince (29 Ekim: 3.201 / 42.468) |
| I4 backtest-market, I6 ft-display-v6-mkt | I1 MS oran geçmişi doldurulunca |
| D3 bulut kopyası (7-Zip AES) | 7-Zip kurulu mu — yeni araç; K12 onaylı |

## Sıradaki (sırayla)

### 19 — Faz O (gölge kurallar)
- [x] O1 live-poisson-v1.2 trivial etiketi (H3) — 94.34
- [x] O2 live-cond-filter-v1: COND ≥%85 ama Poisson <%85 → uyarı (gölge kayıt) — 94.35
- [x] O3 live-comeback-v1: λ(geride)/λ(önde) ≥2,2 dilimi — kalibrasyon #14 (%78,5 → %79,1) — 94.36
- [x] O4 market-summary-v3 (H1, 94.11)
- [x] O5 ft-display-v5.1 (H5): kademe avantaja bağlı (#12: ≥20 %70,1 · 15–20 %61,4 · 10–15 %52,6) — 94.37; "yalnız model" kapsamı P1 ile gelir
- [ ] O6 ft-display-v6-mkt (I6) — I1 sonrası

### 19 — Faz P (kapsam)
- [x] P1 "yalnız model" analizi (K15) — 94.48: `matches.model_only` (migration c3p6l1m7h885), `runner.upsert_model_only`,
  `prematch_v5.capture_model_only` (sadece gölge v5.1), canlı izleyicide sadece gölge sürümler + `details.model_only`;
  havuz/ekran sorguları `Match.model_only.is_(False)`; `tests/test_model_only.py` (38 test, her hariç tutma için bir
  test). İlk gerçek kayıt: 2993838 Frosinone–Lecce (H2H 2; avantaj 4,4 puan → kural gereği yayın yok).
  Not: "yalnız model" backtest'i (#12 tekrar oynatma bu maçlar için) arşivde bu satırlar olmadığından yapılamıyor;
  ölçüm gölge karneyle (`group_by=model_only`).
- [x] F7 lig alias'ları — 94.49: 7 ligin kısa kod/bülten adı birleşti, kaynaktan örneklenen 20 (kod, ad) çifti testte, `normalize-leagues --apply` 65 satır; frontend bayrakları (German 2. Bundesliga, Eerste Divisie, League One/Two, TUR 1. Lig)
- [ ] P2 lig partisi (K16) — 94.50: `scripts/lig-partisi-cek.bat` hazır (lig no 35/137/17/32/6, 5 sezon, kaynaktan doğrulandı); KULLANICI ÇEKİYOR. Bitince: SHADOW_LEAGUES'e ekle (P3 ile), audit-db, gölge karne
- [ ] P3 DISPLAY_LEAGUES / POOL_LEAGUES ayrımı + terfi süreci
- [ ] P4 Avrupa kupaları seçenek B (K17): arşiv + canlı COND gölge

### 20 — Kalan Orta/Düşük
- [ ] B5 İY arşiv alanları "hep 0" (Optional + sürüm + recompute)
- [ ] B6 kickoff yer tutucusu 15:59 (aday filtresi + sürüm; Faz G ile)
- [x] C3 geçmiş isabet çipi sadece ana lig — 94.38
- [x] C4 kapsama karnesi (/api/performance/coverage) — 94.40
- [x] E8 paylaşım sonrası sertleştirme — 94.46 (ADMIN_API_KEY değerini .env'ye yazmak kullanıcıda; anahtar yoksa admin uçları sadece yönetici hesabı) (ADMIN_API_KEY + compare_digest, /docs kapalı, disable-user, logout-all, WS oturum kontrolü, sabit zamanlı giriş, Origin kontrolü, çerez secure, çıkışta sepet temizliği)
- [ ] F6 scrape-canary + gerçek sayfa örnekleri
- [ ] F8 skor gecikmesi
- [ ] F9 build-archive hata takibi
- [x] F10 canlı Playwright bütçesi (tek deneme, kalan bütçe; canlı maç yoksa Chromium yok) — 94.45
- [x] F11 fixture_cache koruması (küçülme uyarısı; düşenler zaten carried) + skipped_analysis 90 gün budama — 94.44
- [ ] H4 piyasa olasılığı (market_prob.py)
- [x] H5 v5 kademesi (O5 ile) — 94.37
- [ ] I5 yedek bahisçi
- [ ] J7 kupon skor düzeltmesi revizyon tablosu
- [ ] J11 kupon detay sayfası, mobil taslak çubuğu, sessionStorage, aria-pressed, sayfalama
- [ ] J12 bildirimler (yeni altyapı — onay)
- [x] K-3 İY panosu yarım kazanç/kayıp etiketi, "ima olasılık", power pay çıkarma — 94.41
- [x] K-4 bitmiş günlerde model_pct sızıntısı — 94.39
- [x] L3 mobil menü (4 ana sayfa + "Daha fazla": Sonuçlar, Değerlendirme, dil, gölge, çıkış; sepet çubuğu içeriği örtmüyor) — 94.47
- [ ] L4 format.ts birleştirme, hata kodu çevirisi, ölü sözlük anahtarları, i18n parite testi
- [ ] L5 küçük UI düzeltmeleri
- [ ] L6 degerlendirme/page.tsx bölme
- [x] M4 engines/.nvmrc, requirements notu, vite-tsconfig-paths kaldırıldı — 94.42
- [x] M5 tekrar eden kod (poisson_utils, RESULT_KNOWN_DELAY, istanbulDate/ISTANBUL_TZ, audit-db skor kopyası, ölü fonksiyonlar) — 94.43

### 21 — Denetim notlarından plana girmemiş öneriler (29 Ekim taraması, 11 notun tamamı)
Her aday kodda kontrol edildi; uygulama sırasında zaten düzelmiş olanlar aşağıda "kapandı" olarak ayrı.

- [ ] Q1 `/api/health` `bg_queue_size` hep 0 — `routes_admin` kuyruğu içe aktarma anında kopyalıyor (01 D1). S
- [ ] Q2 Süresi dolan oturum satırları DB'den hiç silinmiyor (sadece çıkışta) → okurken/periyodik budama (01 D3). S
- [ ] Q3 `live-freeze` deneme modu `sync_kickoffs` ile DB'ye yazıyor; `--match` bitmiş maçta "sonucu görmüş model" uyarısı yok;
  ekrandaki `live-poisson-v1.1`'e "Gölge" yazıyor (01 D4). S
- [ ] Q4 Eski docstring'ler: `live_poisson`, `routes_live_ht`, `auth.py:7`, `routes_coupons:29` (01 D5). S
- [ ] Q5 `is_admin_request(None)` giriş açıkken AttributeError (`fixture(request=None)` doğrudan çağrıda) (01 D6). S
- [ ] Q6 `goal_events._fix_sides` skorsuz satırda taraf kayabilir — savunma + test (01 D7; bugün 358/358 uyuşuyor). S
- [ ] Q7 `routes_performance._load` sabit 50.000 sınırı (~2 ayda "tümü" kesilir) ve `predictions` sınırı süzgeçten önce (01 D8). S
- [ ] Q8 `create-user --password` kabuk geçmişine düşer → şifre isteme (gizli giriş) seçeneği + uyarı (02 D6). S
- [ ] Q9 Python bağımlılık güncellemesi (starlette DoS açıkları, fastapi, uvicorn, lxml, playwright) (02 D5) — K6 "ertele"; Faz E sonrası onayla
- [ ] Q10 `pg_stat_statements` (onay) + Faz G'den 1 hafta sonra indeks kullanım kontrolü (03 B14). S
- [ ] Q11 Kupondaş'ta oranın yanında payı çıkarılmış olasılık ve bahisçi payı; "value" ipucu yok (05 adım 7, 06 UX) — H4 sonrası. S–M
- [ ] Q12 Giriş sayfasında 429'da kalan bekleme süresi (06 B10). S
- [ ] Q13 Kupondaş erişilebilirlik: `aria-live`, küçük ✕ düğmesi, en fazla bacak sayısı gösterimi, boş durumlar (06 B11 — J11'de olmayanlar). S
- [ ] Q14 Ölü kod: frontend `i18n.locales` ve gereksiz export'lar; backend `correlation.get_correction_factor`,
  `filtering.select_last_n_league_matches` sadece testlerde (06 B12, 07). S
- [ ] Q15 Canlı sayfada sekme başlığı sayacı "(1) Canlı" (tarayıcı bildirimi J12'ye bağlı) (06 UX). S
- [ ] Q16 Mobil 360 px E2E kontrolü (06 B6; L3'te yazılmadı). S
- [ ] Q17 `pipeline/runner.py` bölme (~930 satır → `pipeline/results.py`) (07). M
- [ ] Q18 `numpy` requirements'ta sabit değil (bağımlılık satırı → onay) (07). S
- [ ] Q19 `score-list-v1` parmak izi + sabitlenmiş test (07). S
- [ ] Q20 Eksik testler: `users_cmds`, `odds_cmds`, `events_cmds`; frontend `live-labels.ts`, `api.createCoupon`/`getHtStrategy` (07). M
- [ ] Q21 Yıllık "felaket provası" belgesi — yeni PC'ye kurulum adımları (08, D3 planında yazıldı, belge yok). S

Kontrol edilip kapanmış bulunanlar (iş yok): PerformancePanel `ci_high` "undefined" (L2 `fmtNum`), `_FINISHED_STATES` ölü kod (A1),
canlı sayfa tanınmayan etiket (B2 `status.py`), oran satırlarında maç içi/öncesi ayrımı (A1 `pre`/`closed`), `curl_cffi` (requirements'ta yok),
live-2h geride takım eşiği 65 (O3 `live-comeback-v1`), gölge liglerde ilk sezon λ/A3 düşük (ölçüldü: sadece ilk sezon, model eğitim
sezonu — tasarım gereği), SetThreadExecutionState (otomatik uyku zaten kapalı; elle uykuyu engellemez).
Gözlem (yeni, karar gerekmez): 2. ligde sezon başına arşiv ~%50 (ör. 2. Bundesliga 2024/25 141/306) — H2H ≥5 kuralı arşivi de
yarıya indiriyor; takım gücü eğitimi bu yüzden az veriyle. P2 liglerinde de aynısı beklenir.
