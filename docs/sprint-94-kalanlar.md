# Sprint 94 — kalan maddeler takibi

Kaynak: `docs/sprint-94-plan.md` (bölüm 4 ve 5) + `docs/audit-2026-10-28/01..11`. Kullanıcı kararı (29 Ekim):
"küçük veya büyük farketmez 11 ajanın belirlediği her şey yapılacak, sırasıyla." Kararlar K1–K22 onaylı, tekrar sorulmaz.
Her madde bitince bu dosyada işaretlenir ve commit numarası yazılır.

## Bitti (94.1–94.34)

A1, A2 · B1, B2, B3, B4, B7 · C1, C2 · D1, D2, D4, D5, D3 (yerel kısım: D: kopyası + aylık geri yükleme) ·
E1–E7, E9 · F1–F5 · H1, H2, H3 (94.34) · I1 (gece görevi kuruldu), I2, I3 · J1–J6, J8–J10 · K-1, K-2 · L1, L2 · M1–M3, M6

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
- [ ] P1 "yalnız model" analizi (K15): H2H <5 → model_only, A3 + λ, v5/Poisson; v5.1 gölge (L — temiz oturumda)
  - Engel: `prediction_ledger.match_id` → `matches` yabancı anahtarı; kayıt için `matches` satırı şart.
  - Tasarım: migration `matches.model_only boolean default false`; runner H2H_INSUFFICIENT + takip ligi →
    takım/lig/saat + λ yazan satır (Katman A ve A1/A2 boş), `prematch_v5.ledger_rows_v51(model_only=True)`
    48 saat ufku + başlamış maç korumasıyla.
  - Ana liglerin oranları değişmesin diye model_only satırları şunlardan HARİÇ: COND tablosu (`live_model`),
    lig ortalamaları (`league_priors`), takım gücü eğitimi (`live_poisson.load_training`), A3 aday havuzu,
    bülten / sonuçlar / analiz listeleri, `_prepared_match_ids`, recompute-patterns, audit-db kalite metrikleri,
    canlı izleyici ekrandaki kayıtlar (model_only maçta sadece gölge sürümler yazılır), değerlendirme sayımları.
  - Test: her hariç tutma için bir test; v5.1 satırı `details.model_only=true`.
- [ ] F7 lig alias'ları (P2 ön koşulu)
- [ ] P2 lig partisi (K16): League Two, Çekya, Eerste Divisie, Yunanistan, Polonya — 5 sezon, gece görevinde
- [ ] P3 DISPLAY_LEAGUES / POOL_LEAGUES ayrımı + terfi süreci
- [ ] P4 Avrupa kupaları seçenek B (K17): arşiv + canlı COND gölge

### 20 — Kalan Orta/Düşük
- [ ] B5 İY arşiv alanları "hep 0" (Optional + sürüm + recompute)
- [ ] B6 kickoff yer tutucusu 15:59 (aday filtresi + sürüm; Faz G ile)
- [x] C3 geçmiş isabet çipi sadece ana lig — 94.38
- [x] C4 kapsama karnesi (/api/performance/coverage) — 94.40
- [ ] E8 paylaşım sonrası sertleştirme (ADMIN_API_KEY + compare_digest, /docs kapalı, disable-user, logout-all, WS oturum kontrolü, sabit zamanlı giriş, Origin kontrolü, çerez secure, çıkışta sepet temizliği)
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
- [ ] L3 mobil menü (çıkış, dil, gölge)
- [ ] L4 format.ts birleştirme, hata kodu çevirisi, ölü sözlük anahtarları, i18n parite testi
- [ ] L5 küçük UI düzeltmeleri
- [ ] L6 degerlendirme/page.tsx bölme
- [x] M4 engines/.nvmrc, requirements notu, vite-tsconfig-paths kaldırıldı — 94.42
- [x] M5 tekrar eden kod (poisson_utils, RESULT_KNOWN_DELAY, istanbulDate/ISTANBUL_TZ, audit-db skor kopyası, ölü fonksiyonlar) — 94.43

### Sonra — denetim notlarındaki küçük öneriler
`docs/audit-2026-10-28/01..11` içinde plana girmemiş her öneri tek tek taranıp buraya eklenecek.
