# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Nortverse — Claude Code için Proje Brifingi

Bu dosya Claude Code'un projeyi anlaması için hazırlandı. Devam eden bir proje ve önceki sohbetteki tüm kararlar burada.

## Komutlar

Tüm komutlar `backend/` dizininden çalıştırılır:

```bash
cd backend

# Bağımlılıkları yükle (ilk kurulum)
pip install -r requirements.txt
python -m playwright install chromium

# Veritabanı migration
alembic upgrade head          # son migration'ı uygula
alembic revision --autogenerate -m "aciklama"  # yeni migration oluştur

# Testler
python -m pytest                        # tüm testler
python -m pytest tests/test_analysis.py::test_oran_hesaplama  # tek test
python -m pytest -v                     # verbose

# Linting
python -m ruff check app/
python -m ruff check app/ --fix        # otomatik düzelt

# CLI
python -m app.cli.main fetch-fixture                    # bugünün hot maçları
python -m app.cli.main fetch-fixture --date 2026-04-20  # belirli gün
python -m app.cli.main fetch-fixture --all              # gizli dahil tüm maçlar
python -m app.cli.main analyze 2813084                  # tek maç analizi
python -m app.cli.main analyze 2813084 --ratios         # 35 skorun tüm oranları
python -m app.cli.main analyze-debug 2813084            # Excel karşılaştırma için
python -m app.cli.main fetch-and-analyze                # çek + analiz et
python -m app.cli.main run-pipeline                     # fetch → analiz → DB'ye kaydet (GÜNLÜK ÇALIŞMALI)
python -m app.cli.main run-pipeline --date 2026-04-20   # belirli gün için pipeline
python -m app.cli.main update-scores                    # bugünün biten maçlarının skorlarını güncelle
python -m app.cli.main update-scores --date 2026-04-20  # belirli gün için skor güncelle

# Arşiv oluşturma
# Syntax: build-archive <LEAGUE_ID> [SEZON]
python -m app.cli.main build-archive 36 2024-2025   # ENG PR 2024-2025 sezonu
python -m app.cli.main build-archive 36              # güncel sezon
python -m app.cli.main build-multi-archive 36 39 78  # birden fazla lig — sırayla
python -m app.cli.main list-leagues                  # mevcut tüm lig ID'leri ve isimleri

# FastAPI sunucusu
python -m app.cli.main serve                         # http://localhost:8000
python -m app.cli.main serve --reload               # geliştirme modu (Windows'ta çalışır)

# Veri kalitesi & Audit (Sprint 8.9+20)
python -m app.cli.main self-test 2813084             # E2E sistem testi (7 adım kontrol)
python -m app.cli.main audit-db                      # DB sağlık raporu (kalite skoru, eksik veri)
python -m app.cli.main audit-patterns 2813084        # Pattern B/C eşleşme davranışı + tolerance etkisi
python -m app.cli.main prune-non-league              # Kupa maçlarını soft-delete (default dry-run)
python -m app.cli.main prune-non-league --apply      # Gerçekten temizle (audit_log'a kayıt düşer)
python -m app.cli.main restore-deleted 2976657       # Soft-deleted maçı geri al
python -m app.cli.main repair-archive                # Sorunlu kayıtları tespit et (dry-run)
python -m app.cli.main repair-archive --apply        # Sorunlu kayıtları soft-delete et
python -m app.cli.main normalize-leagues             # Lig adlarını normalize et (dry-run)
python -m app.cli.main normalize-leagues --apply     # Lig adlarını kanonik forma çevir

# Frontend (ayrı terminalde, frontend/ dizininden)
cd ../frontend
npm run dev                                          # http://localhost:3000
```

## Git & GitHub — Claude Code için Zorunlu Kurallar

> **Bu kurallar Claude Code'a yöneliktir. Her çalışma seansında eksiksiz uygulanacak.**
> **Hiçbir çalışma sadece local'de kalmamalı. Her anlamlı adımdan sonra commit + push yapılır.**

### Temel Kural

**Çalışma SIRASINDA** commit + push yapılır — sadece sonunda değil.

Her küçük ilerleme bile commit'e layık:
- Yeni bir dosya yazıldı → commit + push
- Bir bug düzeltildi → commit + push
- Bir özellik çalışır hale geldi → commit + push
- Test geçti → commit + push
- Migration uygulandı → commit + push
- CLAUDE.md güncellendi → commit + push
- Sprint tamamlandı → commit + push
- Seans bitmek üzere → mutlaka commit + push

**Sebep:** "Yaptığımız çalışmaları ve durumu asla kaybetmeyelim."
Her commit GitHub'da kalıcı bir kontrol noktasıdır. Seans kapanınca local değişiklikler kaybolabilir — GitHub'da olan kaybolmaz.

### Remote

```
https://github.com/sefaeryurek/nortverse.git  (branch: master)
```

### Commit ve Push Komutu

Her değişiklik sonrası şu sıra izlenir — istisnasız:

```bash
git add <değişen dosyalar>
git commit -m "Sprint X: Ne yapıldı — neden yapıldı"
git push origin master
```

### Commit Mesajı Formatı — TEMİZ ve AÇIK Olmalı

```
Sprint X: Ne yapıldı — neden yapıldı (Türkçe, kısa)
```

**KABUL EDİLMEZ:** `fix`, `update`, `wip`, `değişiklik`, `güncelleme`

**DOĞRU ÖRNEKLER:**
- `Sprint 6: EXPOSE 8000 kaldırıldı — Railway PORT env var ile çakışıyordu`
- `Sprint 6: DATABASE_URL_SYNC opsiyonel yapıldı — production'da gereksiz`
- `Sprint 5: DB-first analiz — Playwright sadece DB'de olmayan maçlar için açılıyor`

---

## Proje Nedir?

**Nortverse**, nowgoal26.com'dan futbol maçı verilerini çekip istatistiksel analiz yapan bir sistem. Son hedef: web uygulaması + premium üyelik. Sahip: Sefa, kod tecrübesi az ama öğrenmeye açık.

Excel'de çalışan mevcut analiz sistemini web tabanlı yapıyoruz. Sıfırdan ve temiz başlandı.

---

## Sistemin Özü

### 3 Katmanlı Analiz

**Katman A — Klasik Skor Hesaplama (TAMAMLANDI ✅)**
```
oran(hg, ag, periyot) = (
    (h2h_ev_periyot[hg] + form_ev_periyot[hg])
    + (h2h_dep_periyot[ag] + form_dep_periyot[ag])
) / 2
```
- 35 skor × 3 periyot (İY/2Y/MS) = 105 hesaplama
- Formül sonucu her zaman 0.5 katı (0, 0.5, 1.0, ..., 10.0)
- 3.5+ çıkan skorlar → MS1/MSX/MS2 olarak gruplanır, frontend'de Katman A bölümünde gösterilir
- Periyotta hiç 3.5+ skor yoksa o periyot için tahmin gösterilmez

**Katman B — Pattern Matching / Arşiv-1 (TAMAMLANDI ✅)**
- Bülten maçının MS1+MSX+MS2 skor setini DB'deki geçmiş maçlarla karşılaştırır
- **Tam aynı set** → eşleşme. En az 5 eşleşme varsa istatistik üretilir
- `app/analysis/pattern_b.py` → `find_pattern_b_matches(period, s1, sx, s2)`

**Katman C — Tam Oran Pattern Matching / Arşiv-2 (TAMAMLANDI ✅)**
- Bülten maçının FT oranlarını DB'deki geçmiş maçlarla ±0.5 aralığında karşılaştırır
- **Kritik tasarım kararı:** FT oranlarıyla tek sorgu yapılır, aynı eşleşme seti İY/2Y/MS için kullanılır
  - Sebep: Bir maçın İY oran benzerliği varsa 2Y ve MS için de vardır. Periyot başına ayrı sorgu yapılsaydı "İY var, MS yok" gibi tutarsız sonuçlar çıkardı
- `app/analysis/pattern_c.py` → `find_pattern_c_all_periods(ft_ratios)` → `(ht_result, h2_result, ft_result)`

### 35 Skor Listesi (Sıra Sabit)

```python
MS1 = [(1,0),(2,0),(2,1),(3,0),(3,1),(3,2),(4,0),(4,1),(4,2),(4,3),
       (5,0),(5,1),(5,2),(6,0),(6,1)]  # 15
MSX = [(0,0),(1,1),(2,2),(3,3),(4,4)]  # 5
MS2 = [(0,1),(0,2),(1,2),(0,3),(1,3),(2,3),(0,4),(1,4),(2,4),(3,4),
       (0,5),(1,5),(2,5),(0,6),(1,6)]  # 15
```

### Filtreleme Kuralları (Otomatik Kural Dışı)

Maç atlanır eğer:
1. Analiz edilen maç lig maçı değilse (kupa/friendly)
2. Ev veya deplasman takımı ligde < 5 maç oynamışsa
3. H2H'ta < 5 lig maçı varsa

---

## Kod Yapısı

```
nortverse/
├── .github/workflows/
│   ├── quality.yml                # CI: push/PR → ruff + pytest (backend) + vitest + tsc + build (frontend)
│   ├── daily_pipeline.yml         # Cron: 7 entry (2× run-pipeline + 5× update-scores)
│   ├── recompute_patterns.yml     # Cron: Pazar 03:00 İstanbul — haftalık pattern recompute
│   └── repair_archive.yml         # Manuel: repair-archive + normalize-leagues + audit-db (Sprint 20)
├── backend/
│   ├── app/
│   │   ├── config.py              # ScraperConfig, AnalysisConfig (env-aware frozen dataclass)
│   │   ├── models.py              # Pydantic: FixtureMatch, HistoricalMatch, MatchRawData
│   │   ├── db/
│   │   │   ├── connection.py      # SQLAlchemy async engine + get_session() — Neon pooler uyumlu (env-driven pool/cache)
│   │   │   └── models.py          # Match + FixtureCache ORM — JSONB kolonlar, actual skorlar
│   │   ├── scraper/
│   │   │   ├── browser.py         # Playwright wrapper (browser_context context manager)
│   │   │   ├── fixture.py         # Günlük bülten — Hot filtreli, kickoff UTC timezone
│   │   │   ├── match_detail.py    # H2H sayfası parse + gerçek skor çıkarımı
│   │   │   └── league.py          # Lig sayfasından maç ID listesi (arşiv için)
│   │   ├── analysis/
│   │   │   ├── scores.py          # ALL_SCORES sabiti
│   │   │   ├── filtering.py       # check_match_filters (lig, min maç, H2H kontrolleri)
│   │   │   ├── engine.py          # analyze_match (Katman A)
│   │   │   ├── history.py         # select_history — merkezi veri seçimi (Sprint 12 denetim)
│   │   │   ├── league_filter.py   # is_supported_league + canonical_league_name (Sprint 8.9)
│   │   │   ├── pattern_b.py       # find_pattern_b_matches — JSONB equality
│   │   │   ├── pattern_c.py       # find_pattern_c_all_periods — FT oranları, TEK sorgu
│   │   │   ├── pattern_stats.py   # PatternResult model + compute_stats — ~130 istatistik alanı
│   │   │   ├── persist.py         # compute_all_patterns + update_match_patterns (Sprint 8)
│   │   │   ├── correlation.py      # Poisson korelasyon faktörleri — pazar çiftleri arası (Sprint 19)
│   │   │   ├── repair.py          # detect_issues + needs_normalization — tarihsel veri onarımı (Sprint 20)
│   │   │   └── trends.py          # compute_trends — form & H2H trend verileri (Sprint 8.8)
│   │   ├── api/
│   │   │   ├── main.py            # FastAPI hub — router include, lifespan, CORS, middleware (Sprint 22)
│   │   │   ├── schemas.py         # Pydantic response modelleri (Sprint 21)
│   │   │   ├── services.py        # Ortak iş mantığı: cache, lock, bg queue, analiz (Sprint 22)
│   │   │   ├── routes_fixture.py  # /api/fixture endpoint (Sprint 22)
│   │   │   ├── routes_analysis.py # /api/analyze, /api/match endpoint'leri (Sprint 22)
│   │   │   ├── routes_results.py  # /api/results, /api/matches endpoint'leri (Sprint 22)
│   │   │   └── routes_admin.py    # /api/health, /api/admin/quality, /api/correlations (Sprint 22)
│   │   ├── pipeline/
│   │   │   └── runner.py          # run_pipeline + update_results: fetch → analiz → upsert
│   │   └── cli/
│   │       ├── main.py            # Hub — import + app.command() kayıtları (Sprint 21)
│   │       ├── _helpers.py        # Ortak yardımcılar: console, logging, render (Sprint 21)
│   │       ├── pipeline_cmds.py   # analyze, fetch-fixture, run-pipeline, serve (Sprint 21)
│   │       ├── archive_cmds.py    # build-archive, repair-archive, normalize-leagues (Sprint 21)
│   │       └── audit_cmds.py      # audit-db, self-test, prune-non-league (Sprint 21)
│   ├── alembic/                   # DB migration (6 migration)
│   ├── tests/                     # 432 test
│   │   ├── conftest.py            # Test DB izolasyonu — prod credentials kullanılmaz
│   │   ├── test_analysis.py       # Katman A oran hesaplama
│   │   ├── test_league_filter.py  # Lig filtresi (28 test)
│   │   ├── test_pre_write_validation.py  # Pre-write doğrulama (10 test)
│   │   ├── test_trends.py         # Trend hesaplama (6 test)
│   │   ├── test_pattern_c.py      # Pattern C fuzzy match (6 test)
│   │   ├── test_history.py        # History seçim kuralları
│   │   ├── test_api_regressions.py        # API regresyon testleri
│   │   ├── test_scraper_regressions.py    # Scraper regresyon testleri
│   │   ├── test_pattern_stats_regressions.py  # Pattern stats regresyon
│   │   ├── test_persistence_regressions.py    # DB yazma regresyon
│   │   ├── test_stale_writes.py           # Stale write koruması
│   │   ├── test_fixture_cache_recovery.py # Fixture cache kurtarma
│   │   ├── test_pattern_failure_handling.py  # Pattern hata yönetimi
│   │   ├── test_pattern_sample_limits.py  # Pattern örneklem sınırları
│   │   ├── test_analysis_refresh.py       # Analiz yenileme
│   │   ├── test_result_updates.py         # Skor güncelleme
│   │   ├── test_results_contract.py       # Results API sözleşmesi
│   │   ├── test_correlation.py            # Korelasyon faktörleri (16 test, Sprint 19)
│   │   ├── test_repair.py                # Veri onarımı testleri (26 test, Sprint 20)
│   │   ├── test_fixture_parser.py        # Fixture parser birim testleri (30 test, Sprint 21)
│   │   ├── test_engine.py               # Katman A motor birim testleri (39 test, Sprint 22)
│   │   ├── test_filtering.py            # Maç filtreleme birim testleri (25 test, Sprint 22)
│   │   ├── test_runner.py               # Pipeline runner birim testleri (27 test, Sprint 22)
│   │   ├── test_match_detail_parser.py  # H2H parser birim testleri (58 test, Sprint 23)
│   │   ├── test_services.py             # API services birim testleri (26 test, Sprint 23)
│   │   └── test_config.py              # Config env override testleri (25 test, Sprint 23)
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx             # Root layout (dark tema, sidebar, BetCart)
│   │   ├── page.tsx               # Root → /bulten redirect
│   │   ├── error.tsx              # Global error boundary (Sprint 8.3)
│   │   ├── bulten/
│   │   │   └── page.tsx           # Server component — fixture listesi (Suspense)
│   │   ├── sonuclar/
│   │   │   └── page.tsx           # Server component — biten maçlar, skor, tahmin özeti
│   │   └── analyze/[match_id]/
│   │       └── page.tsx           # Client component — maç analiz sayfası
│   ├── components/
│   │   ├── AddToCartButton.tsx    # "+" / "✓" sepet toggle butonu (Sprint 8.7)
│   │   ├── BetCart.tsx            # Floating bahis sepeti — desktop panel + mobile sheet (Sprint 8.7)
│   │   ├── BultenRow.tsx          # Maç satırı (link ?home=&away= param ile, lig bayrak)
│   │   ├── ComboSuggestion.tsx    # 3 hazır kombo kartı (Sprint 8.5)
│   │   ├── DayTabs.tsx            # 8 günlük kayan pencere, basePath prop ile
│   │   ├── DetailedStats.tsx      # Tüm 137 alan, accordion (Sprint 8.4)
│   │   ├── IddaaCoupon.tsx        # Arşiv istatistik kartları — orchestrator
│   │   ├── MarketSummary.tsx      # Ana pazar kazananları (Sprint 8.4)
│   │   ├── RetryButton.tsx        # Yeniden deneme butonu (Sprint 12 denetim)
│   │   ├── ScoreList.tsx          # Katman A 3.5+ skor listesi
│   │   ├── Sidebar.tsx            # Sol menü (md altı gizli — mobile)
│   │   ├── StatBadge.tsx          # Yeniden kullanılabilir yüzde rozeti
│   │   ├── TopPicks.tsx           # Confidence sıralı en güçlü tahminler (Sprint 8.4)
│   │   └── TrendsPanel.tsx        # Form & H2H trend kartları (Sprint 8.8)
│   ├── lib/
│   │   ├── analysis-validation.ts # Analiz verisi doğrulama (Sprint 12 denetim)
│   │   ├── api.ts                 # Backend API çağrıları
│   │   ├── cart.ts                # useCart hook — localStorage çok-maç sepet (Sprint 8.7)
│   │   ├── combos.ts             # generateCombos — kombo üretimi + korelasyonlu jointProb (Sprint 8.5/19)
│   │   ├── correlations.ts       # Poisson korelasyon tablosu + getCorrectionFactor (Sprint 19)
│   │   ├── correlation-table.json # 299 korelasyon faktörü statik tablo (Sprint 19)
│   │   ├── confidence.ts          # Confidence hesaplama + Top Picks (Sprint 8.4)
│   │   ├── dates.ts               # Tarih yardımcıları (Sprint 12 denetim)
│   │   ├── env.ts                 # getApiBase + getProxyTarget (Sprint 10)
│   │   ├── labels.ts              # Periyot etiketleri (Sprint 8.4)
│   │   ├── leagues.ts             # Lig adı → bayrak + kısa kod sözlüğü (Sprint 8.3)
│   │   ├── list-validation.ts     # Liste veri doğrulama (Sprint 12 denetim)
│   │   ├── match-context.tsx      # MatchProvider — match metadata paylaşımı (Sprint 8.7)
│   │   ├── pattern-fields.ts      # Pattern alan isimleri (Sprint 12 denetim)
│   │   ├── selection-compatibility.ts  # Seçim uyumluluk kontrolü (Sprint 12 denetim)
│   │   └── types.ts               # TypeScript type'ları (PatternResult ~130 alan)
│   ├── __tests__/                 # 241 vitest test
│   │   ├── fixtures.ts            # Test factory'leri
│   │   ├── confidence.test.ts     # Confidence hesaplama (~33 test)
│   │   ├── combos.test.ts         # Kombo üretimi (~15 test)
│   │   ├── cart.test.ts           # Sepet helper'ları (~14 test)
│   │   ├── use-cart.test.tsx      # useCart hook (14 test)
│   │   ├── env.test.ts            # URL fallback
│   │   ├── day-tabs.test.ts       # DayTabs
│   │   ├── api.test.ts            # API çağrıları
│   │   ├── analysis-validation.test.ts    # Analiz doğrulama
│   │   ├── selection-compatibility.test.ts # Seçim uyumluluk
│   │   ├── date-validation.test.ts        # Tarih doğrulama
│   │   ├── market-regressions.test.ts     # Pazar regresyon
│   │   ├── cart-display.test.tsx           # Sepet görüntüleme
│   │   ├── score-list.test.tsx            # ScoreList component (4 test)
│   │   ├── stat-badge.test.tsx            # StatBadge component (7 test)
│   │   ├── bulten-row.test.tsx            # BultenRow component (8 test)
│   │   ├── top-picks.test.tsx             # TopPicks component (9 test)
│   │   ├── market-summary.test.tsx        # MarketSummary component (7 test)
│   │   ├── combo-suggestion.test.tsx      # ComboSuggestion component (7 test)
│   │   ├── add-to-cart-button.test.tsx    # AddToCartButton component (7 test)
│   │   ├── day-tabs-render.test.tsx       # DayTabs render (7 test)
│   │   ├── leagues.test.ts               # Lig eşleme (12 test)
│   │   ├── trends-panel.test.tsx          # TrendsPanel component (13 test)
│   │   ├── retry-button.test.tsx          # RetryButton component (4 test)
│   │   └── correlations.test.ts          # Korelasyon faktörleri (10 test, Sprint 19)
│   ├── e2e/                       # 14 Playwright E2E test (×2 viewport = 28)
│   │   ├── navigation.spec.ts     # Sayfa yükleme, redirect, DayTabs (6 test)
│   │   ├── analyze.spec.ts        # Analiz sayfası, periyot sekmeleri (4 test)
│   │   └── mobile.spec.ts         # Mobil görünüm, sidebar, scroll (4 test)
│   ├── AGENTS.md                  # ⚠️ Next.js özel sürüm uyarısı — kod yazmadan önce oku
│   ├── playwright.config.ts       # Playwright E2E yapılandırması (Sprint 18)
│   ├── vitest.config.mts          # Vitest yapılandırması (Sprint 10)
│   └── next.config.ts             # Rewrite proxy: /api/* → localhost:8000/api/*
└── CLAUDE.md
```

---

## API Performans Mimarisi

### Anlık Analiz için 3 Katmanlı Cache

```
Kullanıcı maça tıklar
    ↓
1. Memory cache kontrolü  → HIT: 0ms döner
    ↓ MISS
2. DB kontrolü            → HIT: ~1-3sn (sadece B/C DB sorgusu, Playwright YOK)
    ↓ MISS
3. Playwright scrape      → ~15-30sn (ilk kez veya DB'de yok)
    ↓
Memory cache'e yazar
```

### Arka Plan Analiz Kuyruğu

- `/api/fixture` çağrıldığında tüm maçlar `asyncio.Queue`'ya eklenir
- Seri worker (`_bg_worker`) maçları sırayla analiz eder
- DB'deki maçlar kuyrukta hızlı (~1-3sn), DB'siz olanlar yavaş (~15-30sn)
- Kullanıcı maça tıkladığında büyük ihtimalle cache'de hazır

### Fixture Cache

- Aynı tarih için 5 dakika boyunca nowgoal'a gitmiyor
- Date switch'leri anında döner (2. ziyaretten itibaren)

### Production için Kritik: Günlük Pipeline

```bash
python -m app.cli.main run-pipeline
```

Bu komut sabah çalıştırıldığında bugünün tüm maçlarını scrape edip DB'ye yazar. Gün içinde kullanıcılar maçlara tıkladığında **Playwright hiç açılmaz**, DB'den 1-3sn'de gelir.

**GitHub Actions otomatik çalışır** (`.github/workflows/daily_pipeline.yml`):
- `0 5 * * *` → 08:00 İstanbul → `run-pipeline` (sabah analiz)
- `0 19 * * *` → 22:00 İstanbul → `update-scores` (akşam skor güncelleme)
- `30 21 * * *` → 00:30 İstanbul → `update-scores` (gece geç maçlar)

**Not:** `_score_updater` task'i Sprint 7 sırasında kaldırıldı (Playwright fırtınası sebebiyle). Skor güncelleme tek başına gece cron'una bırakıldı.

---

## Frontend — Analiz Sayfası Mimarisi (Sprint 8.4+)

Analiz sayfası 5 katman + sepet panelinden oluşur — eski "her bölümü yan yana göster" yerine **bilgi hiyerarşisi** uygulanmıştır:

### Katman 0 — Trends Paneli (sadece MS sekmesi)
`components/TrendsPanel.tsx` — 3 mini kart (Ev Form, Dep Form, H2H):
- Son 5 sonucu G/B/M renkli timeline (yeşil/sarı/kırmızı)
- Galibiyet/KG/Üst 2.5 yüzdeleri + Att/Yedi ortalama
- Backend'de `app/analysis/trends.py` ile hesaplanır, `matches.trends` JSONB'de saklanır
- Yetersiz örnek (<3) → ilgili blok gizlenir

### Katman 1 — Top Picks (Önerilen Bahisler)
`components/TopPicks.tsx` — confidence sıralı en güçlü 5-8 tahmin:
- Confidence formülü: `(pct/100) × volume × market_weight × dual_bonus`
- **Dinamik eşik (Sprint 8.6):** 5 maç %74, 50 maç %66 — örneklem küçükse daha sıkı
- Arşiv 1+2 ortak doğrularsa `1+2` rozeti, dual_bonus 1.15

### Katman 1b — Akıllı Kombolar (Sprint 8.5)
`components/ComboSuggestion.tsx` — 3 hazır kombo kartı:
- **Çift** (2 leg ≥%75) / **Üçlü** (3 leg ≥%70) / **Süper** (4-5 leg ≥%75, sadece ≥20 maç eşleşmesinde)
- Joint olasılık + tahmini decimal oran (≈ ile yaklaşık)
- Aynı domain'den iki leg yasak (`combos.ts:DOMAIN_OF`)
- "+ Sepete Ekle (N maç)" butonu tüm leg'leri toplu ekler

### Katman 2 — Ana Pazar Özeti
`components/MarketSummary.tsx` — sadece ana pazarların kazananları (Arşiv 1 vs Arşiv 2 yan yana). Çelişen seçimler yok, her pazarın tek kazananı.

### Katman 3 — Detaylı Analiz (varsayılan kapalı, accordion)
`components/DetailedStats.tsx` — tüm 137 alan; localStorage ile son state hatırlanır.

### Bahis Sepeti (Sprint 8.7)
`components/BetCart.tsx` — floating panel (desktop) / mobile sheet:
- localStorage tabanlı çok-maç sepet (`nortverse_bet_cart`)
- TopPicks/MarketSummary/ComboSuggestion'da "+" butonları
- Toplam joint olasılık + tahmini kombi oran
- `lib/cart.ts:useCart` hook + `lib/match-context.tsx` ile match metadata

### IY/2Y'de Gizlenen Pazarlar (Sprint 8.4)
İddaa'da 1.01 oranlı veya açılmayan pazarlar IY/2Y'de gösterilmez:
- 2.5 Alt/Üst, 3.5 Alt/Üst (toplam + Ev/Dep tarafları)
- Tüm handikaplar (2:0, 1:0, 0:1, 0:2)
- MS+2.5 kombineleri

`confidence.ts:MARKETS` içinde `excludePeriods: ["ht", "h2"]` ile merkezi filtre — Top Picks, Market Summary, DetailedStats üçü birden tutarlı.

### Renk Skalası
**Confidence-bazlı (Top Picks):** ≥0.80 yeşil dolu, 0.65-0.79 yeşil çerçeve, 0.50-0.64 gri, <0.50 silik.
**Detailed (Sprint 8.4):** ≥%75 yeşil canlı, %60-74 sade gri, %40-59 silik gri, <%40 transparan.

**Handikap convention:** `Hnd (2:0)` = ev sahibi +2 gol alır → `hnd_a20`. `Hnd (0:2)` = deplasman +2 gol alır → `hnd_h20`.

---

## Mevcut Durum (Sprint 20 — TAMAMLANDI ✅ — Production CANLI + Veri Kalitesi 89.4+)

### Backend

- ✅ Fixture parser: Hot modunu aktive edip maçları doğru çekiyor
- ✅ Match detail parser: takım, lig kodu, form/H2H parse + gerçek skor
- ✅ Analiz motoru (Katman A): 105 oran hesaplaması
- ✅ Katman B pattern matching: `find_pattern_b_matches` — `exclude_match_id` ile analiz edilen maç kendi arşivinden hariç
- ✅ Katman C pattern matching: `find_pattern_c_all_periods` — tek sorgu, tüm periyotlar; `exclude_match_id` desteği
- ✅ **Pattern saklama (Sprint 8):** `matches` tablosunda 6 yeni JSONB kolon (`pattern_ht_b/c`, `pattern_h2_b/c`, `pattern_ft_b/c`) — runtime hesabı yerine DB'den okur
- ✅ **`compute_all_patterns` ortak yardımcısı:** `app/analysis/persist.py` — pipeline ve API kullanır
- ✅ **Lazy backfill:** `_build_from_db` pattern eksik bulursa hesaplayıp DB'ye yazar (write-through cache)
- ✅ **`_do_analyze` write-through:** Playwright scrape sonrası tam upsert (analiz + pattern)
- ✅ `build-archive` CLI: lig → geçmiş maç ID → fetch+analiz+upsert
- ✅ FastAPI: 7 endpoint + fixture cache (memory + DB) + bg analiz kuyruğu + DB-first analiz
- ✅ **Bg worker DB-only (Sprint 7 acil):** Playwright AÇMAZ; sadece DB-hit yapar + lazy backfill tetikler
- ✅ **`/api/fixture` hard timeout 20sn (Sprint 7 acil):** Playwright takılırsa 503, backend ölmez
- ✅ **`/api/health` zenginleştirildi:** DB durumu, son pipeline saati, fixture cache zamanı, bg queue, cached_analyses
- ✅ **`/api/health` GET+HEAD:** UptimeRobot free tier HEAD desteği
- ✅ **LRU cache bound (Sprint 8.2):** `_analysis_cache` ve `_analysis_locks` 500 entry sınırı — uzun ömürlü container'da bellek koruması
- ✅ **Sonuçlar smart filtering (Sprint 8.1):** `/api/results` endpoint'i artık tüm günün maçlarını döndürür, her maça `status` (scheduled/live/finished); scheduled ve stale (>130dk skorsuz) gizlenir
- ✅ **Saat başı update-scores cron (Sprint 8.1):** 12:00–23:00 İstanbul her saat — biten skorlar dakikalar içinde sonuçlar sayfasında
- ✅ **Playwright path ERROR seviyesi (Sprint 8.2):** `_do_analyze` upsert hatası `log.error` + `exc_info=True` (Railway logs'ta stack trace)
- ✅ **DB write retry (Sprint 8.3):** `_with_retry` yardımcısı — `_upsert` ve `update_results` 3 deneme + exponential backoff (pooler drop koruması)
- ✅ **`/api/match/{id}` lazy fallback (Sprint 8.3):** DB miss → Playwright scrape + upsert (25sn timeout); 404 yerine maç hep gelir
- ✅ **Fixture tarih sınırı (Sprint 8.3):** -30 / +14 gün dışına çıkılamaz (uçuk tarih → 400, Playwright açılmaz)
- ✅ **Form & H2H Trendleri (Sprint 8.8):** `app/analysis/trends.py` — `compute_trends(raw)` 3 blok döner (home_form / away_form / h2h); `matches.trends` JSONB (migration `f5c8d2a1b394`); `_do_analyze` ve `_result_to_row` write
- ✅ **`AnalyzeResponse.trends` (Sprint 8.8):** API'den frontend'e taşınır; `_build_from_db` saklı trends'i parse eder, `_trends` helper (api/main.py)
- ✅ **Lig filtresi (Sprint 8.9):** `app/analysis/league_filter.py` — `is_supported_league` (kupa keyword kara liste) + `canonical_league_name` (lig adı kanonik); `check_match_filters` NOT_LEAGUE_MATCH ile kupa/Avrupa/friendly maçları skip eder
- ✅ **Lig adı tespiti güçlendirildi (Sprint 8.9):** `fetch_match_detail(expected_league_name=...)` parametresi — pipeline `fixture.league_name`'i geçirir, H2H tabanlı yanlış tespit önlenir (UEL maçı "ENG PR" sanılma sorunu çözüldü)
- ✅ **Soft delete + audit_log (Sprint 8.9):** `matches.deleted_at/deleted_reason` kolonları + `audit_log` tablosu; `prune-non-league` soft delete yapar, `restore-deleted` geri alır; tüm SELECT(Match) sorgularında `deleted_at IS NULL` filtresi (pattern_b/c arşivde de saymaz)
- ✅ **Pre-write validation (Sprint 8.9):** `_validate_row` — bozuk veri (boş takım, kupa, saçma skor) DB'ye yazılmaz; `_upsert` öncesi guard
- ✅ **Pattern C sıkı eşleşme (Sprint 8.9):** `tolerance: 0.5 → 0.0` (tam eşleşme), `min_matches: 5 → 1`; tolerance=0 sıkı, az eşleşme normal — frontend Pattern C için `match_count >= 1`
- ✅ **`/api/health` data_quality skoru (Sprint 8.9):** total/active/soft_deleted/non_league_active/missing_pattern/missing_trends/missing_actual + 0-100 quality_score
- ✅ **5 yeni CLI komutu (Sprint 8.9):** `self-test` (E2E 7 adım), `audit-db` (kalite raporu), `audit-patterns` (Pattern B/C davranış), `prune-non-league` (soft delete), `restore-deleted` (geri al)
- ✅ **Pytest 67 test (Sprint 8.9 + 8.10):** `test_league_filter.py` (28), `test_pre_write_validation.py` (10), `test_trends.py` (6), `test_pattern_c.py` (6), `test_analysis.py` (mevcut) — kalıcı test suite
- ✅ **Pattern C egress optimizasyonu (Sprint 8.10):** tolerance=0.0 fast-path DB-side JSONB equality — eski 130MB/çağrı → yeni 50KB/çağrı (%99.96 azaltma); tolerance > 0 fallback yolu korundu
- ✅ **`/api/health` hafifletildi (Sprint 8.10):** Sprint 8.9'da eklenmiş `data_quality` UptimeRobot pinglerinde 187 MB/gün egress yaratıyordu → kaldırıldı; yeni `/api/admin/quality` endpoint detay rapor için (UptimeRobot çağırmaz)
- ✅ `pattern_stats.py`: ~130 alan, 9 bölüm
- ✅ Render.com deployment: `https://nortverse-backend.onrender.com`
- ✅ `fixture_cache` DB tablosu: bülten verileri kalıcı, server restart'tan etkilenmez
- ✅ `/api/results` endpoint: günlük biten maçlar + Katman A kapsamı
- ✅ `update-scores` CLI: biten maçların actual skorlarını DB'ye yazar
- ✅ Neon pooler uyumu: `pool_size=2`, `statement_cache_size=0` (env-driven)
- ✅ Date bug düzeltildi: fixture İstanbul tz bazlı, tarih filtresi eklendi
- ✅ **Yedek pipeline cron (09:00 İstanbul):** 08:00 cron kaçırırsa devreye girer
- ❌ `_score_updater` kaldırıldı: Playwright fırtınası sebebiyle (Sprint 7 acil)

### Frontend

- ✅ Next.js App Router — dark tema, sidebar navigasyon
- ✅ Bülten sayfası: Hot maçlar, saat, lig, 8 günlük kayan takvim
- ✅ Analiz sayfası: Katman A skor listesi + IddaaCoupon (Arşiv-1 ve Arşiv-2)
- ✅ Periyot sekmeleri: İY / 2Y / MS — her biri kendi istatistiklerini gösterir
- ✅ Sonuçlar sayfası (`/sonuclar`): biten maçlar, skor; canlı maç "Canlı" rozeti
- ✅ IddaaCoupon: her arşiv kartının üstünde "Altın Oranlar" (%79+) bölümü
- ✅ IddaaCoupon: handikap (2:0)/(0:2) convention düzeltildi
- ✅ Vercel deployment: `https://nortverse.vercel.app`
- ✅ SSR URL düzeltildi: `BACKEND_URL` env var ile Vercel → Render direkt
- ✅ **Next.js Data Cache 60sn (Sprint 7):** `getFixture`/`getResults` server cache → tarih değişimi anlık
- ✅ **Skeleton fallback (Sprint 7):** Suspense'te 8 satırlık iskelet, "Yükleniyor..." flash bitti
- ✅ **DayTabs disable (Sprint 7):** Aktif tarihe tıklayınca reload yok
- ✅ **Race condition fix (Sprint 8.2):** Analiz sayfası `useEffect` cleanup flag — hızlı maç değişiminde yanlış maç gösterilmesi engellendi
- ✅ **Mobile sidebar (Sprint 8.2):** `md:` breakpoint altında gizli — mobilde +%32 içerik alanı
- ✅ **Mobile touch hedefleri (Sprint 8.2):** Sonuçlar Analiz linki min-h-[40px]
- ✅ **Sonuçlar status renderı (Sprint 8.1):** Canlı (yeşil rozet, skor varsa "Canlı 1-0"), Bitmiş (skor), scheduled/stale (gizli)
- ✅ **Hover button cleanup (Sprint 8.2):** Geri butonu inline mouseenter → Tailwind hover sınıfı
- ✅ **Error boundary (Sprint 8.3):** `app/error.tsx` Next.js global error boundary — React crash'lerinde "Tekrar dene" butonlu fallback, beyaz ekran yok
- ✅ **`/sonuclar` empty state mesajı (Sprint 8.3):** "Henüz oynanan veya canlı maç yok" + bugün için açıklayıcı alt yazı
- ✅ **Periyot sekmeleri snappy (Sprint 8.3):** `useTransition` + opacity fade — geçiş anında, jank azaldı
- ✅ **Lig eşlemesi yenilendi (Sprint 8.3):** `lib/leagues.ts` — backend tam adlarına (English Premier League vs.) uygun 30+ lig bayrak/kısa kod sözlüğü
- ✅ **`ScoreFreq` null-safe (Sprint 8.3):** Defensive null check, parent'ta da kontrol
- ✅ **BultenPrefetcher silindi (Sprint 8.3):** Sprint 7'de no-op olmuştu, ölü kod olarak temizlendi
- ✅ **3 Katman Mimari (Sprint 8.4):** `IddaaCoupon` artık orchestrator — TopPicks (Katman 1) + ComboSuggestion (Katman 1b) + MarketSummary (Katman 2) + DetailedStats (Katman 3, accordion)
- ✅ **Confidence Scoring (Sprint 8.4):** `lib/confidence.ts` — pct × volume × market_weight × dual_bonus; `resolveConflicts` aynı pazardan tek seçim; `getTopPicks` çelişkisiz sıralı
- ✅ **IY/2Y'de iddaa açmayan pazarlar gizli (Sprint 8.4):** `MarketSpec.excludePeriods` — 2.5/3.5 A/Ü, taraf 2.5, tüm handikaplar IY/2Y'de gizlendi
- ✅ **Akıllı Kombinasyon Kuponu (Sprint 8.5):** `lib/combos.ts` + `components/ComboSuggestion.tsx` — 3 hazır kombo (çift/üçlü/süper); domain bazlı çelişki kontrolü; joint probability + tahmini decimal oran
- ✅ **Dinamik Confidence Eşiği (Sprint 8.6):** `dynamicMinPct(matchCount)` — 5 maç ~%74, 50 maç ~%66; başlıkta "Eşleşme: N maç · Eşik: ≥%X" göstergesi
- ✅ **Bahis Sepeti (Sprint 8.7):** `lib/cart.ts` (localStorage `nortverse_bet_cart`), `components/BetCart.tsx` (floating panel + mobile sheet), `components/AddToCartButton.tsx`, `lib/match-context.tsx`; çok-maç destekli; cross-tab sync (storage event + custom event)
- ✅ **TrendsPanel (Sprint 8.8):** `components/TrendsPanel.tsx` — 3 mini kart (Ev/Dep Form, H2H), son 5 sonuç G/B/M timeline, sadece MS sekmesinde

### Performans Sonuçları (Sprint 8 sonrası)

| Senaryo | Süre |
|---|---|
| Memory cache hit (2. tıklama) | ~50-100ms |
| DB hit + saklı pattern | ~300-1000ms |
| DB hit + pattern eksik (lazy backfill, tek seferlik) | ~1-9sn |
| DB miss (Playwright scrape, ilk kez) | ~10-15sn |

### Altyapı / Monitoring

- ✅ **UptimeRobot kuruldu:** `/api/health`'e 5dk'da bir HEAD ping → Render uyumaz
- ✅ Backend memory cache TTL: 5dk → 10dk

### Henüz Yok

- ❌ Premium/Auth — sonraki fazlar
- ❌ Canlı maç + trend motoru — sonraki fazlar
- ❌ Veri doğruluğu auditi yapılmadı (3-5 maç nowgoal vs DB karşılaştırması)

---

## Sprint Geçmişi

### Sprint 2 — TAMAMLANDI ✅
- Supabase PostgreSQL + SQLAlchemy async + asyncpg
- `matches` tablosu JSONB schema + Alembic migration
- `run-pipeline` CLI: fetch → analiz → upsert (idempotent)

### Sprint 3 — TAMAMLANDI ✅
- Gerçek skor çıkarımı (`actual_ft/ht_home/away`)
- `build-archive` CLI: lig arşivi DB'ye yazılıyor
- Katman B pattern matching (`find_pattern_b_matches`)

### Sprint 4 — TAMAMLANDI ✅
- Katman C pattern matching (`find_pattern_c_all_periods`)
- FastAPI REST API (5 endpoint)
- Windows ProactorEventLoop düzeltmesi

### Sprint 5 — TAMAMLANDI ✅
- Next.js frontend (bülten + analiz sayfaları)
- CORS 405 hatası düzeltildi: Next.js proxy rewrite (`/api/* → backend`)
- Timezone düzeltildi: nowgoal `data-t` UTC'dir, Beijing değil (8 saat ileri sorunu)
- Windows `--reload` modunda Playwright subprocess hatası düzeltildi (`loop="none"`)
- Fixture 5dk cache + arka plan analiz kuyruğu + DB-first analiz
- `pattern_stats.py`'ye 9 yeni istatistik bölümü eklendi
- IddaaCoupon: kompakt kartlar, mavi/turuncu/kırmızı renk skalası

### Sprint 6 — TAMAMLANDI ✅
- Railway backend deployment + Vercel frontend deployment
- `fixture_cache` tablosu: bülten DB'ye kaydediliyor, server restart'ta Playwright açılmıyor
- Sonuçlar sayfası (`/sonuclar`): biten maçlar, gerçek skor, Katman A/KG/2.5 özet
- GitHub Actions günlük pipeline: her sabah 08:00 İstanbul'da otomatik `run-pipeline`
- `update-scores` CLI + FastAPI `_score_updater`: her 30 dakikada skorlar otomatik güncellenir
- Supabase PgBouncer ECIRCUITBREAKER hatası düzeltildi: `pool_size=2`, `statement_cache_size=0`
- Date bug düzeltildi: fixture URL ve tarih filtresi İstanbul tz bazlı
- Vercel SSR URL sorunu düzeltildi: `BACKEND_URL` env var ile server-side fetch

### Sprint 7 — TAMAMLANDI ✅
- Sonuçlar sayfası temizlendi: KG/2.5 Üst/A✓ rozet kutucukları kaldırıldı
- Sonuçlar sayfası: canlı maç tespiti (kickoff+110dk içindeyse "Canlı" rozeti)
- IddaaCoupon: her arşiv kartının üstüne "Altın Oranlar" bölümü eklendi (%79+ tahminler, sıralı)
- IddaaCoupon: handikap convention düzeltildi — `Hnd(2:0)` ev +2 alır, `Hnd(0:2)` dep +2 alır
- `pattern_b.py` + `pattern_c.py`: `exclude_match_id` parametresi — analiz edilen maç kendi arşivinden hariç
- `api/main.py`: `_build_from_db` ve `_do_analyze`'a `exclude_match_id=match_id` geçildi
- CLAUDE.md eksik/hatalı bölümler düzeltildi (tree, komutlar, migration, AGENTS.md referansı)
- `/api/health` zenginleştirildi: DB durumu, son pipeline saati, fixture cache zamanı, bg queue
- `/api/health` GET+HEAD desteği — UptimeRobot 405 hatası çözüldü
- UptimeRobot kuruldu: 5dk'da bir HEAD ping → Railway uyku sorunu çözüldü
- Performans: Next.js Data Cache 60sn, skeleton fallback, DayTabs disable, prefetch 3→5
- **ACİL müdahale (production incident):** Playwright fırtınası tespit edildi
  - Bg worker DB-only yapıldı (Playwright AÇMAZ)
  - `_score_updater` task tamamen kaldırıldı (gece cron'a güveniliyor)
  - `/api/fixture` Playwright çağrısına 20sn hard timeout (503 dönüp backend'i koruyor)
  - BultenPrefetcher kapatıldı (no-op)
  - Backend memory cache 5dk→10dk

### Sprint 8 — TAMAMLANDI ✅ (Sub-saniye Analiz)
- **Pattern saklama altyapısı:** `matches` tablosuna 6 yeni JSONB kolon eklendi
  - Migration: `b7e4a2d8c901_add_pattern_columns`
  - Kolonlar: `pattern_ht_b`, `pattern_ht_c`, `pattern_h2_b`, `pattern_h2_c`, `pattern_ft_b`, `pattern_ft_c`
- `app/analysis/persist.py`: `compute_all_patterns` (paralel B+C hesabı) + `update_match_patterns` (lazy backfill DB write)
- `pipeline/runner.py`: `run-pipeline` artık her maç için pattern hesaplayıp DB'ye yazar
- `api/main.py` `_build_from_db`: kaydedilmiş pattern'leri okur (~300-1000ms); eksikse hesaplayıp DB'ye yazar (write-through)
- `api/main.py` `_do_analyze`: Playwright path'inde de pattern + analiz tam upsert
- 09:00 İstanbul yedek pipeline cron eklendi (`0 6 * * *`) — 08:00 cron kaçırırsa devreye girer
- **Sonuç:** Tüm maç tıklamaları **<1 saniye** (memory cache veya saklı pattern)

### Sprint 8.1 — TAMAMLANDI ✅ (Canlı/Bitti Ayrımı)
- `/api/results` endpoint'i artık actual_ft filtresi YOK — günün TÜM maçlarını döndürür
- Her maça `status` alanı: `finished`, `live`, `scheduled`
- Backend filtresi: `scheduled` (henüz başlamamış) ve `stale` (>130dk skorsuz) maçlar gizli
- Frontend `ResultRow`: status'e göre Canlı rozet / Skor render
- Saat başı update-scores cron: 12:00–23:00 İstanbul (12 yeni cron entry) — gün içi skor güncelleme
- Public repo → GitHub Actions cron limit yok

### Sprint 8.2 — TAMAMLANDI ✅ (Stabilite & Bug Fix)
- **Race condition fix:** Analiz sayfası `useEffect` cleanup flag — hızlı maç değişiminde yanlış maç gösterilmesi engellendi
- **LRU cache bound (500 entry):** `_analysis_cache` ve `_analysis_locks` `OrderedDict` — `_cache_put`, `_cache_touch`, `_get_or_make_lock` helper'ları
- **Mobile sidebar:** `md:` breakpoint altında gizli (mobil ekran genişliği kazanımı)
- **Mobile touch hedefi:** Sonuçlar Analiz linki min-h-[40px] flex items-center
- **Playwright path log seviyesi:** `_do_analyze` upsert hatası `log.warning` → `log.error` + `exc_info=True`
- **Geri butonu cleanup:** Inline `onMouseEnter`/`onMouseLeave` style → Tailwind `hover:` sınıfı

### Sprint 8.3 — TAMAMLANDI ✅ (Profesyonel Stabilite)
- **Frontend:** `app/error.tsx` global error boundary, sonuçlar empty state mesajı, ScoreFreq null-safe, periyot sekmeleri `useTransition`, lig eşlemesi (`lib/leagues.ts`) yeni tam adlara güncellendi
- **Frontend cleanup:** `BultenPrefetcher` ve `prefetchAnalyze` ölü kod silindi (Sprint 7'de devre dışıydı)
- **Backend:** `/api/fixture` tarih sınırı (-30 / +14 gün), `/api/match/{id}` lazy Playwright fallback (25sn timeout)
- **Backend dayanıklılık:** `_with_retry` yardımcısı (`pipeline/runner.py`) — `_upsert` ve `update_results` 3 deneme + exponential backoff
- **Sonuç:** Profesyonel stabilite hedefi — geçici DB hataları otomatik çözülür, React crash'leri yakalanır, mobil + desktop UX tutarlı

### Sprint 8.4 — TAMAMLANDI ✅ (3 Katman Tahmin Mimarisi + IY/2Y Filtre)
- **Problem:** Bir maç açıldığında 260+ rozet/oran rendering — kullanıcı bunalıyordu
- **Çözüm — 3 Katman:**
  - **Top Picks** (`components/TopPicks.tsx`): confidence sıralı 5-8 en güçlü tahmin
  - **Ana Pazar Özeti** (`components/MarketSummary.tsx`): sadece ana pazarların kazananları, Arşiv 1 vs 2 yan yana
  - **Detaylı Analiz** (`components/DetailedStats.tsx`): mevcut tüm bölümler accordion içinde, varsayılan kapalı, localStorage hatırlama
- **Yeni:** `lib/confidence.ts` — `computeConfidence`, `resolveConflicts`, `mergeArchives`, `getTopPicks`; `lib/labels.ts` — paylaşılan period etiketleri
- **Eski "Altın Oranlar" kaldırıldı:** Top Picks gelişmiş hali
- **Renk skalası yenilendi:** mavi/turuncu/kırmızı kakofoni → yeşil/gri sade
- **IY/2Y'de iddaa açmayan pazarlar gizlendi:** 2.5/3.5 A/Ü, taraf 2.5, tüm handikaplar (`MarketSpec.excludePeriods: ["ht", "h2"]`) — Top Picks + Market Summary + DetailedStats üçü birden tutarlı

### Sprint 8.5 — TAMAMLANDI ✅ (Akıllı Kombinasyon Kuponu)
- **`lib/combos.ts`:** `generateCombos(picks)` 3 hazır kombo üretir
  - **Çift Kombo** (2 leg ≥%75)
  - **Üçlü Kombo** (3 leg ≥%70)
  - **Süper Kombo** (4-5 leg ≥%75, sadece eşleşme ≥20 maç ve avg confidence ≥0.65)
- **Çelişki kontrolü:** `DOMAIN_OF` haritası ile aynı domain'den iki leg yasak; `HARD_CONFLICTS` keskin çelişkileri yakalar (örn. result_x + fark_ev1)
- **Joint olasılık:** `∏ (pct/100)` (bağımsızlık varsayımı, ≈ ile yaklaşık belirtilir)
- **Tahmini oran:** `1 / jointProb` (gerçek iddaa oranı değil, kullanıcıya açıkça söylenir)
- **`components/ComboSuggestion.tsx`:** 3 kart yan yana grid; "Sepete Ekle (N maç)" butonu tüm leg'leri toplu ekler

### Sprint 8.6 — TAMAMLANDI ✅ (Dinamik Confidence Eşiği)
- **Problem:** Sabit `minPct=60` küçük örneklemde yanıltıcı tahminler gösteriyordu
- **`dynamicMinPct(matchCount)`:** Wilson lower bound benzeri pragmatik formül — `max(64, 80 - log10(matchCount + 1) × 8)`
  - 5 maç → ~74%
  - 15 maç → ~70%
  - 30 maç → ~68%
  - 50 maç → ~66%
  - 100+ → ~64%
- **`getTopPicks` artık `TopPicksResult` döner:** `picks` + `effectiveMinPct` + `matchCount`
- **TopPicks başlığı:** "Eşleşme: N maç · Eşik: ≥%X" — şeffaflık, hover tooltip ile açıklama

### Sprint 8.7 — TAMAMLANDI ✅ (Bahis Sepeti)
- **`lib/cart.ts`:** localStorage tabanlı çok-maç sepet (`nortverse_bet_cart`)
  - `useCart()` React hook: `items`, `addItem`, `removeItem`, `clear`, `has`, `jointProb`, `estOdds`
  - Cross-tab sync: storage event + `nortverse-cart-updated` custom event
  - Idempotent: aynı tahmin iki kez eklenemez
- **`lib/match-context.tsx`:** `MatchProvider` — analiz sayfasında match metadata'yı paylaşır (prop drilling yok)
- **`components/BetCart.tsx`:** floating buton (sağ alt) + açıldığında panel
  - **Desktop (md+):** sticky w-80 kart
  - **Mobile:** alt sheet, arkaplan dim
  - Toplam joint olasılık + tahmini kombi oran + "Sepeti Temizle"
- **`components/AddToCartButton.tsx`:** "+" / "✓" toggle butonu
- **Mount noktaları:** TopPicks PickRow, ComboSuggestion (toplu ekleme), MarketSummary Cell (≥%60 olanlarda); DetailedStats kalabalık olur diye eklenmedi
- **Layout mount:** `app/layout.tsx` — `<BetCart />` her sayfada görünür (boş sepette gizli)

### Sprint 8.10b — TAMAMLANDI ✅ (Acil Tampon — Para Harcamadan Kesin Yol Hazırlığı)
- **Bağlam:** Sprint 8.10 deploy edildi ama Supabase erişilmez (egress %511), kullanıcı para harcamayacak — Oracle Cloud Always Free PostgreSQL göçüne karar verildi
- **GitHub Actions cron'ları DEVRE DIŞI:** `.github/workflows/daily_pipeline.yml` schedule blokunu yorum satırına aldı; sadece `workflow_dispatch` ile manuel tetiklenebilir → erişim geri gelse bile otomatik egress yaratmaz
- **Vercel SSR cache agresifleştirildi:** `getFixture` 60sn → 300sn (5dk), `getResults` 60sn → 120sn (2dk) — kullanıcı UX'te kayıp yok ama backend çağrı 5x azalır
- **Backend Cache-Control middleware:** `/api/fixture`, `/api/results`, `/api/matches`, `/api/health` için `s-maxage` + `stale-while-revalidate` header'ları → Cloudflare CDN önüne alındığında origin call %80 düşer
- **Sonuç:** Sistem Oracle göçüne hazır; göç sonrası tüm optimizasyonlar kalıcı kalır

### Sprint 9 — TAMAMLANDI ✅ (Oracle Migration Kod Hazırlığı + Kritik Bug Fix + Repo Temizlik)
**Sprint 9 (1/n) — `057a585`:** Oracle migration için kod hazırlığı.
- `connection.py`: pool_size/max_overflow/statement_cache_size hardcode kaldırıldı, env-driven (DB_POOL_SIZE/DB_MAX_OVERFLOW/DB_STATEMENT_CACHE_SIZE). Defaultlar Oracle-friendly (5/5/100); Supabase için Railway env'de 2/0/0 set edilir.
- `alembic/env.py`: DATABASE_URL_SYNC artık opsiyonel — yoksa DATABASE_URL'den asyncpg→psycopg2 dönüşümü otomatik. Tek env var ile çalışır.
- `Dockerfile`: CMD'ye `alembic upgrade head` eklendi. Container her açılışta schema güncel.

**Sprint 9 (2/n) — `3a01d7e` — KRİTİK FIX:** `app/api/main.py:528` `from sqlalchemy import or_` vardı ama `func` yoktu. Sprint 8.10'da `/api/health.data_quality` kaldırılıp `/api/admin/quality` ayrı endpoint olarak eklendiğinde unutulmuş; 5 satır `func.count(Match.id)` NameError fırlatıyordu. Production'da kırık olduğu fark edilmedi çünkü UptimeRobot bu endpoint'i değil `/api/health`'i pingliyor. Tek satır fix: `or_, func`.

**Sprint 9 (3/n) — `ae1c394`:** Repo temizlik (~60 MB) + lint cleanup.
- Silindi: 4 root scraping artifact (HTML/txt), `backend/debug/` (5 dosya, 172 KB), `backend/debug_html/` (74 dosya, 60 MB)
- `.gitignore`: `backend/debug/` pattern eklendi
- F-prefix lint bug'lar (ruff --fix + manuel): F811 `fetch_league_seasons` çift import (cli/main.py:34 kaldırıldı), F401 ×5 (Annotated, ALL_SCORES, timezone, and_, SCRAPER), F841 `steps = []` self-test dead code, F541 ×4 gereksiz f-string prefix
- DetailedStats SSR guard incelendi — gerçek bug değil (useEffect zaten client-only), skip edildi

### Sprint 10 — TAMAMLANDI ✅ (Kod İyileştirme Fazı — DB-Bağımsız)
**Bağlam:** Oracle Cloud hesap kabulu sorunlu çıktı, kullanıcı kararı: DB alternatifi başka sohbette aranacak. Bu sohbet DB'siz ilerletilebilir 5 iyileştirme yaptı.

**Sprint 10 (1/5) — `84c0761`:** Frontend Vitest birim test altyapısı (sıfırdan, Next.js 16.2.4 + React 19.2.4).
- `node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md` resmi rehber takip edildi
- devDeps: vitest, @vitejs/plugin-react, jsdom, @testing-library/{react,dom}, vite-tsconfig-paths
- `vitest.config.mts` + `__tests__/fixtures.ts` (PatternResult/Pick factory)
- `confidence.test.ts` (~33 test): dynamicMinPct, computeConfidence, confidenceTier, resolveConflicts, buildPicks, getTopPicks, getMarketSummary, getMarkets
- `combos.test.ts` (~15 test): generateCombos, domain conflict, hard conflict, tier kuralları
- 48 test 1.19sn yeşil

**Sprint 10 (2/5) — `a638389`:** `lib/cart.ts` helper testleri (jsdom localStorage).
- cart.ts: readStorage/writeStorage/itemKey/STORAGE_KEY/CART_EVENT export edildi (test edilebilirlik)
- Duplicate export ölü kod (`export { itemKey, STORAGE_KEY as CART_STORAGE_KEY }`) silindi
- `cart.test.ts` ~14 test: readStorage edge case'ler (boş/bozuk/array dışı/filter), writeStorage event fırlatma, itemKey determinism, roundtrip
- 62 test yeşil

**Sprint 10 (3/5) — `3c556e2`:** Top Picks Trend Boost — Sprint 8.8 trends → confidence formülü.
- `confidence.ts`: `getTrendsBoost(marketKey, selection, trends)` helper + TRENDS_BOOST_RULES (5 kural: result+1/2 home/away_form.win_pct≥65 → 1.10, result+X h2h.draw_pct≥40 → 1.07, kg+KG Var h2h.kg_var_pct≥60 → 1.10, ou_25+Üst 2.5 home_form.over_25_pct≥55 → 1.08)
- `computeConfidence`: 5. param `trendsBoost=1.0` (backward compat)
- `buildPicks`: 4. param `trends=null` (backward compat) → her pick için boost
- Prop drilling: `page.tsx → IddaaCoupon → TopPicks` ile `trends` geçirildi
- 12 yeni test, 74 toplam yeşil + npm run build temiz

**Sprint 10 (4/5) — `5a2d181`:** URL fallback centralize — `lib/env.ts`.
- `next.config.ts` ve `lib/api.ts`'teki ikili kaynak duplicate kaldırıldı
- `lib/env.ts` yeni modül: `getApiBase()` (CSR+SSR) + `getProxyTarget()` (rewrite)
- Davranış değişmedi: Vercel SSR direkt Render, CSR proxy üzerinden, lokal dev proxy localhost:8000

**Sprint 10 (5/5):** Pattern recompute CLI + haftalık workflow + CLAUDE.md güncelleme.
- `recompute-patterns` CLI komutu: `--limit N`, `--batch-size N`, `--only-missing`. `deleted_at IS NULL` filtresi, `_with_retry` ile lazy backfill, batch sonu progress log.
- `.github/workflows/recompute_patterns.yml`: haftalık cron şablonu (Pazar 03:00 İstanbul), `timeout-minutes: 350`. Şu an `schedule:` yorumlu (DB yok), `workflow_dispatch` aktif.
- 67 backend pytest yeşil.

### Sprint 11 — TAMAMLANDI ✅ (Kalan Kod İyileştirme Paketi — DB-Bağımsız)
**Bağlam:** Sprint 10'da skip edilen 4 DB-bağımsız iş tamamlandı.

**Sprint 11 (1/4) — `f77907e`:** `pattern_stats.py` E701/E702 cosmetic refactor.
- 13 inline lint bug temizlendi (3 E702 semicolon + 10 E701 colon): MS sonucu bloku, fark_ctr nested if, gol_aralık 4-way
- Logic değişmez, +14 satır, 67 pytest yeşil

**Sprint 11 (2/4) — `5600e33`:** Typer 0.12.5 → 0.25.1 upgrade. `--help` TypeError fix.
- Sorun: typer 0.12.5 eski Click API kullanıyordu, transitive click 8.3.2 ile `Parameter.make_metavar(ctx)` zorunlu olunca tüm `--help` çağrıları patlardı
- Typer 0.15.x'de hâlâ vardı, Typer 0.25.1 (Click 8.3 uyumlu) ile çözüldü
- `_flag()` helper korundu (eski 0.12 bool string bug için; 0.25'te no-op, zarar yok)
- annotated-doc==0.0.4 transitive yüklendi
- Doğrulama: `python -m app.cli.main --help` ve `recompute-patterns --help` temiz, 67 pytest yeşil

**Sprint 11 (3/4) — `531c72d`:** `useCart` hook integration testi (renderHook).
- Sprint 10 Faz B'de helper'lar (readStorage/writeStorage/itemKey) test edilmişti; hook davranışları eksikti
- `__tests__/fixtures.ts`'e `makeCartItem` eklendi, `cart.test.ts` fixtures'a yönlendirildi
- `__tests__/use-cart.test.tsx` (.tsx) 14 yeni test: initial state, addItem/idempotent/timestamp, removeItem(idx/key), clear, has, jointProb, estOdds, CART_EVENT re-sync, unmount cleanup (memory leak yok)
- `stripAddedAt` helper non-deterministic Date.now() için
- 74 → 88 test, 1.49sn yeşil

**Sprint 11 (4/4):** Sepet sticky bottom bar (mobile UX) + CLAUDE.md.
- `BetCart.tsx`: floating button `md:flex hidden` (mobile gizli) + yeni mobile sticky bottom bar `md:hidden`, `zIndex: 45` (panel 50 > bar 45 > overlay 40)
- İçerik: 🧾 + count + ≈%prob + ≈odds + "Aç" butonu; tıklayınca mevcut BetCart sheet açar
- Boş sepette zaten guard'lı (BetCart hidden if `!hydrated || count === 0`)
- 88 test yeşil, npm run build temiz

### Sprint 12 — TAMAMLANDI ✅ (Kapsamlı Kod Denetimi)
- **Commit `1038c8a`:** 14 Eylül 2026'da 10 turlu kapsamlı kod denetimi
- 42 değiştirilmiş + 29 yeni dosya (906 ekleme, 437 silme)
- Backend: 67 → 160 test, Frontend: 88 → 146 test
- CI pipeline eklendi (`.github/workflows/quality.yml`)
- Veri bütünlüğü, eşzamanlılık güvenliği, scraper doğruluğu, API sağlamlaştırma, istatistiksel dürüstlük iyileştirmeleri

### Sprint 13 — TAMAMLANDI ✅ (Neon PostgreSQL Migration — Production Geri Açıldı)
- **Bağlam:** 4 aydır production down (Supabase egress aşımı). Neon PostgreSQL + Render.com + Vercel ile tam yeniden kurulum.
- **Neon PostgreSQL geçişi (`c243aa3`):**
  - `connection.py`: asyncpg SSL + Neon pooler uyumu (`sslmode`/`channel_binding` URL'den strip, `ssl.create_default_context()` connect_args)
  - Alembic 6 migration zinciri Neon'da uygulandı
  - Supabase'den 4394 maç Neon'a aktarıldı (0 hata, batch 50)
  - DB: 19.6 MB / 512 MB kullanımda
- **Nowgoal lig kodu aliases genişletildi (`bb2b401`):**
  - `league_filter.py` LEAGUE_ALIASES'a 60+ yeni alias eklendi (SPA D1, ENG LCH, HOL D1, vs.)
  - Pipeline lig=0 bug'ı düzeltildi: `expected_league_name` (tam ad) vs H2H kısa kodları uyumsuzluğu
- **Railway → Render.com geçişi:**
  - Railway trial doldu → Render.com free tier (kullanıcının mevcut hesabı)
  - Backend: `https://nortverse-backend.onrender.com`
  - Render free tier: 15dk inaktivite uyku, ~30sn cold start, Docker
- **Fixture cache local popülasyon:**
  - Render Playwright timeout alıyor (512MB RAM, 20sn limit) → local'den `populate_fixture_cache.py` ile Neon'a yazıldı
  - Kalıcı çözüm: Sprint 14'te GitHub Actions
- **Vercel frontend:** `BACKEND_URL` güncellendi, clean redeploy ile çalıştı
- **GitHub Actions:** `DATABASE_URL` secret Neon'a güncellendi (cron hâlâ devre dışı — Sprint 14)
- **Sonuç:** 4 aylık downtime sona erdi, production CANLI

### Sprint 14 — TAMAMLANDI ✅ (GitHub Actions Cron Yeniden Aktif + Fixture Cache Otomasyonu)
- **GitHub Actions cron schedule yeniden açıldı:** `daily_pipeline.yml` 7 cron entry (08:00/09:00 pipeline + 14:00/18:00/22:00/00:30/02:00 update-scores), `recompute_patterns.yml` Pazar 03:00 İstanbul
- **Fixture cache otomasyonu:** `run_pipeline` artık fixture'ları çektikten sonra `fixture_cache` tablosunu da dolduruyor — Render Playwright çalıştıramadığı için bu kritik; GitHub Actions'ta pipeline çalışınca `/bulten` verisi hazır
- **Eski Supabase/Oracle yorumları kaldırıldı:** Workflow dosyalarındaki devre dışı yorumları Neon'a güncellendi

### Sprint 15 — TAMAMLANDI ✅ (Pattern Recompute — Yeni Kurallarla)
- **Bağlam:** Sprint 8.9+ denetim kuralları (tolerance=0.0, skor doğrulama, history filtreleme) ile pattern B/C yeniden hesaplanması gerekiyordu
- **Tam recompute:** 4,406 aktif maç, batch=200, 0 hata — `recompute-patterns` CLI komutu ile
- **`--only-missing` temizlik:** İlk run timeout sonrası kalan 88 eksik pattern ayrıca tamamlandı
- **prune-non-league:** Tüm 4,408 maç lig maçı, kupa maçı yok — temizleme gerekmedi
- **Sonuçlar:** Pattern eksik 3,161 → 0, tutarsızlık 0, quality score 75.1 → 89.4/100

### Sprint 16 — TAMAMLANDI ✅ (CLAUDE.md Kapsamlı Güncelleme)
- **Kod yapısı tree güncellendi:** 28 backend modül + 18 test dosyası + 14 frontend component + 13 lib modül + 13 test dosyası + 3 CI workflow — tüm dosyalar açıklamalı
- **Sprint 12 denetim korumaları belgelendi:** `history.py`, `conftest.py`, frontend doğrulama modülleri, stale write koruması, PatternComputationError yönetimi, CI pipeline
- **CI pipeline dokümantasyonu eklendi:** `quality.yml` (push/PR tetikli), `daily_pipeline.yml` (7 cron), `recompute_patterns.yml` (haftalık)

### Sprint 17 — TAMAMLANDI ✅ (Teknik Borç Temizliği)
- **`_flag()` kaldırıldı:** Typer 0.25.1'de bool option'lar native çalışıyor, 35 çağrı noktasında `_flag(x)` → `x` değiştirildi, helper fonksiyon silindi
- **BeautifulSoup 4.12.3 → 4.15.0 upgrade:** lxml `strip_cdata` DeprecationWarning (17 adet) tamamen gitti, 160 test 0 warning
- **`.gitignore` zaten güncel:** `xx/` ve `.claude/settings.local.json` Sprint 9'da eklenmişti
- **Neon compute izleme:** Aylık ~25-30 saat / 191.9 limit, free tier güvenli alanda

### Sprint 18 — TAMAMLANDI ✅ (Component + E2E Test)
- **Bağlam:** Frontend test coverage artırılması — 146 vitest birim test → 231 vitest + 28 Playwright E2E
- **Component testleri (1/n) — `7823b6e`:** 7 yeni test dosyası, 148→215 test
  - `score-list.test.tsx` (4 test): skor rendering, boş durum, tek skor, MS2 tipi
  - `stat-badge.test.tsx` (7 test): yüzde yuvarlama, etiket, 0/100%, boyutlar
  - `bulten-row.test.tsx` (8 test): takım adları, saat, Link href, lig, URL encoding
  - `top-picks.test.tsx` (9 test): null pattern, yüksek pct, arşiv rozetleri, sepet, 8-pick limiti
  - `market-summary.test.tsx` (7 test): null pattern, pazar satırları, uyum işaretçileri, sepet
  - `combo-suggestion.test.tsx` (7 test): null pattern, kombo kartları, localStorage entegrasyonu
  - `add-to-cart-button.test.tsx` (7 test): +/✓ toggle, sepet ekle/çıkar, olay yayılımı, boyutlar
- **Component testleri (2/n) — `3cbaca5`:** 215→231 test
  - `day-tabs-render.test.tsx` (7 test): 8 buton, aktif devre dışı, navigasyon, Türkçe gün adları
  - `leagues.test.ts` (12 test): bilinen ligler, fallback, null/undefined, alias, UEFA/Güney Amerika/Asya
  - `trends-panel.test.tsx` (13 test): null trends, bölüm başlığı, ev/dep/h2h kartları, G/B/M noktalar
  - `retry-button.test.tsx` (4 test): metin, buton rolü, router.refresh, mavi arka plan
- **Playwright E2E kurulumu:**
  - `@playwright/test` + Chromium tarayıcı kurulumu
  - `playwright.config.ts`: desktop (Chrome) + mobile (Pixel 5) projeler, webServer dev, CI retry
  - `e2e/navigation.spec.ts` (6 test): root redirect, bülten/sonuçlar yükleme, sidebar, DayTabs
  - `e2e/analyze.spec.ts` (4 test): analiz sayfası yükleme, geri buton, periyot sekmeleri
  - `e2e/mobile.spec.ts` (4 test): mobil viewport, sidebar gizli, yatay scroll, analiz mobil
  - **28 E2E test** (14 test × 2 viewport = 28) — backend gerektirir, CI'da workflow_dispatch ile
- **CI entegrasyonu:** `quality.yml`'e `e2e` job eklendi (workflow_dispatch ile tetiklenir)
- **Next.js mock desenleri:** `next/link` (BultenRow), `next/navigation` useRouter (DayTabs, RetryButton)
- **MatchProvider context:** TopPicks, MarketSummary, ComboSuggestion, AddToCartButton testlerinde gerekli
- **Sonuç:** 231 vitest (yeşil) + 28 Playwright E2E (yapı doğrulanmış), hedef 200+ aşıldı

### Sprint 19 — TAMAMLANDI ✅ (Joint Probability İyileştirmesi — Korelasyon Düzeltmesi)
- **Bağlam:** Combo ve sepet hesaplamalarında naif bağımsızlık varsayımı (`∏ P(Aᵢ)`) yerine korelasyon düzeltmesi: `P(A,B) = P(A) × P(B) × corr(A,B)`
- **Backend `app/analysis/correlation.py` (yeni modül):**
  - Poisson modeli (λ_h=1.37, λ_a=1.12) ile 299 pazar çifti korelasyon faktörü hesaplanıyor
  - `compute_poisson_correlations()`: teorik hesaplama (DB gerekmez)
  - `compute_from_matches()`: arşiv verisinden gözlemlenen korelasyon (≥100 maç gerekli, yoksa Poisson'a fallback)
  - `get_correction_factor()`: iki pazar sonucu arası düzeltme faktörü bulma
  - `_outcomes_for_score()`: skor → pazar sonuçları eşlemesi
- **Frontend `lib/correlations.ts` + `correlation-table.json` (yeni):**
  - 299 korelasyon faktörü statik JSON tablosu
  - `getCorrectionFactor(mktA, selA, mktB, selB)` → düzeltme faktörü (bilinmeyen çift → 1.0)
  - `computeJointProb(legs)` → korelasyon düzeltmeli birleşik olasılık
- **`combos.ts` güncellendi:** `Combo.jointProb: number | null` (literal `null` değil), `computeJointProb` ile hesaplanıyor; `estDecimalOdds = 1/jp`
- **`cart.ts` güncellendi:** Aynı maç seçimlerinde korelasyon düzeltmesi uygulanıyor; `hasRelatedSelections` kaldırıldı; tüm seçimler (farklı/aynı maç) artık hesaplanıyor
- **`ComboSuggestion.tsx` güncellendi:** Kombo kartlarında `≈%X.Y` olasılık ve `≈Z.ZZ oran` gösteriliyor
- **`BetCart.tsx` güncellendi:** "İlişkili seçimler" mesajı kaldırıldı, "korelasyon düzeltmesiyle hesaplanır" metni eklendi
- **Backend API:** `/api/correlations` GET endpoint (statik Poisson tablo, cache'li)
- **Testler:** 16 backend pytest (korelasyon) + 10 frontend vitest (getCorrectionFactor + computeJointProb) = 26 yeni test
- **Sonuç:** 176 backend + 241 frontend + 28 E2E = **445 toplam test**

### Sprint 20 — TAMAMLANDI ✅ (Tarihsel Veri Onarımı)
- **Bağlam:** Quality score 89.4 → 90+ hedefi; sorunlu kayıt tespiti + onarım altyapısı
- **`app/analysis/repair.py` (yeni modül):**
  - `detect_issues(row)`: tek kayıtta sorun tespit — boş takım, kupa, negatif/aşırı skor (>15), tutarsız yarılar (İY > MS)
  - `needs_normalization(league_code, league_name)`: lig adı kanonik formdan farklı mı kontrolü
  - Pure fonksiyonlar, DB bağımlılığı yok
- **`repair-archive` CLI komutu:**
  - Tüm aktif kayıtları tarar, sorunlu olanları kategorilere ayırır (empty_team, non_league, bad_score, inconsistent_half)
  - Default dry-run + `--apply` ile soft delete + audit_log
- **`normalize-leagues` CLI komutu:**
  - Tüm aktif maçlarda league_code/league_name'i `canonical_league_name()` ile normalize eder
  - Dönüşüm istatistikleri gösterir (eski → yeni, sayı)
  - Default dry-run + `--apply` ile güncelleme + audit_log
- **`audit-db` iyileştirmesi:**
  - Sorunlu skor (negatif/>15), tutarsız yarı (İY > MS), normalize edilmemiş lig adı metrikleri eklendi
  - Quality score formülüne repair_candidates (%15 ağırlık) ve unnormalized (%5 ağırlık) penaltıları eklendi
  - Öneri satırlarında `repair-archive --apply` ve `normalize-leagues --apply` komutları gösteriliyor
- **Testler:** 26 yeni test (test_repair.py) — detect_issues (18 test) + needs_normalization (8 test)
- **Sonuç:** 202 backend + 241 frontend + 28 E2E = **471 toplam test**

### Sprint 21 — TAMAMLANDI ✅ (Kod Sağlığı & Kritik Test Kapsamı)
- **Bağlam:** 9-sprint yol haritası (12-20) tamamlanmış, codebase büyümüş — tek dosyada 1786 satır CLI, scraper parse testleri sıfır, config hala hardcode
- **Fixture parser testleri (`d06a156`):**
  - `tests/test_fixture_parser.py` — 30 yeni test: `_parse_fixture_html`, `_extract_match_info`, `_build_fixture_url`, `_is_row_hidden`, `_build_league_map`, regex sabitleri
  - Mock HTML ile pure fonksiyon testi, DB bağımlılığı yok
  - nowgoal HTML değişikliklerini erken yakalayan güvenlik ağı
- **CLI modüler bölme (`6e1d828`):**
  - `cli/main.py` 1786 → 73 satır hub (import + `app.command()` kayıtları)
  - `_helpers.py`: console, logging, render yardımcıları (249 satır)
  - `pipeline_cmds.py`: analyze, fetch-fixture, run-pipeline, serve, update-scores (7 komut)
  - `archive_cmds.py`: build-archive, repair-archive, normalize-leagues (5 komut)
  - `audit_cmds.py`: audit-db, self-test, prune-non-league, recompute-patterns (6 komut)
  - Dış API değişmedi — tüm `python -m app.cli.main <komut>` aynı çalışır
- **API response model ayrıştırma (`cdd37fa`):**
  - 7 Pydantic model `api/main.py`'den `api/schemas.py`'ye taşındı
  - `api/main.py` 963 → 875 satır
- **Config env-aware (`be1aaa7`):**
  - Sprint 1'den beri açık TODO kapatıldı
  - 9 env var ile override: `SCRAPER_BASE_URL`, `SCRAPER_HEADLESS`, `SCRAPER_TIMEOUT`, `SCRAPER_WAIT`, `SCRAPER_BETWEEN_REQUESTS`, `ANALYSIS_N_MATCHES`, `ANALYSIS_THRESHOLD`, `ANALYSIS_MIN_H2H`, `ANALYSIS_MIN_LEAGUE_MATCHES`
  - Default değerler mevcut hardcode ile aynı — geriye uyumlu
- **Sonuç:** 232 backend + 241 frontend + 28 E2E = **501 toplam test**

### Sprint 22 — TAMAMLANDI ✅ (API Modülerleştirme & Kritik Test Kapsamı)
- **Bağlam:** api/main.py 876 satır tek dosya — cache, lock, queue, endpoint'ler karışık. Motor, filtreleme ve pipeline fonksiyonları test edilmemiş.
- **API route splitting (`c8b04a1`):**
  - `api/main.py` 876 → ~95 satır hub (router include + lifespan + middleware)
  - `services.py`: cache, lock, bg queue, analiz orkestrasyonu (ortak iş mantığı)
  - `routes_fixture.py`: `/api/fixture` endpoint (3 katmanlı cache)
  - `routes_analysis.py`: `/api/analyze/{id}` GET/POST + `/api/match/{id}` GET
  - `routes_results.py`: `/api/results` + `/api/matches`
  - `routes_admin.py`: `/api/health` + `/api/admin/quality` + `/api/correlations`
  - 6 mevcut test dosyası import yolları güncellendi (monkeypatch target kuralı)
- **engine.py birim testleri (`58cf28e`):**
  - `tests/test_engine.py` — 39 test: `_get_goals_in_period`, `_goal_count_distribution`, `_current_season`, `is_match_analyzable`, `analyze_match` validasyon, edge case'ler
- **filtering.py birim testleri (`1511b9d`):**
  - `tests/test_filtering.py` — 25 test: `check_match_filters` geçen/reddedilen durumlar, öncelik sırası, `select_last_n_league_matches`
- **pipeline/runner.py birim testleri (`9656631`):**
  - `tests/test_runner.py` — 27 test: `_with_retry`, `_result_to_row`, `_validate_row`, `_merge_result_scores`, `StaleAnalysisWrite`
- **Sonuç:** 323 backend + 241 frontend + 28 E2E = **592 toplam test**

### Sprint 23 — TAMAMLANDI ✅ (H2H Parser Test & API/Config Birim Testleri)
- **Bağlam:** Sprint 22 ile motor/filtre/pipeline testleri eklenmişti. H2H parser, API services ve config modülleri hâlâ testsizdi.
- **match_detail.py parser testleri (`54c29f5`):**
  - `tests/test_match_detail_parser.py` — 58 test: `_text_of`, `_parse_source_datetime`, `_extract_main_match_kickoff`, `_extract_main_match_info`, `_extract_main_match_score`, `_parse_score_cell`, `_parse_match_row`, `_detect_main_league_code`, `_parse_history_table`
  - Mock HTML ile pure fonksiyon testi, nowgoal HTML değişikliklerini erken yakalayan güvenlik ağı
- **services.py birim testleri (`e9158cd`):**
  - `tests/test_services.py` — 26 test: `cache_put`/`cache_get` LRU/TTL, `get_or_make_lock`, `_pat`/`_trends_parse` deserialize, `enqueue_bg_analysis`, `init/shutdown_bg_queue`
- **config.py birim testleri (`6300247`):**
  - `tests/test_config.py` — 25 test: `_env_float`/`_env_int`/`_env_bool` helper'lar, `ScraperConfig`/`AnalysisConfig` default ve override, frozen dataclass koruması
- **Sonuç:** 432 backend + 241 frontend + 28 E2E = **701 toplam test**

### Sprint 25-26 — TAMAMLANDI ✅ (Local Docker PostgreSQL + 7 Lig Arşiv)
- **Bağlam:** Cloud DB'ler (Supabase, Neon) kota/egress sorunlarına yol açtı. Local Docker PostgreSQL'e geçildi.
- **Docker PostgreSQL:** Port 5433 (native PG 5432'de olduğu için), `nortverse` DB
- **7 lig × 5 sezon arşiv:** ENG PR (1,537), SPA D1 (1,642), ITA D1 (1,332), GER D1 (1,209), FRA D1 (1,274), TUR D1 (1,062), HOL D1 (1,201) = **9,257 aktif maç**
- **Task Scheduler otomasyonu:** 4 bat script — `backup-db.bat` (07:00), `run-pipeline.bat` (08:00), `update-scores.bat` (22:00 + 00:30)
- **Pattern recompute:** 9,257/9,257 tamamlandı, 0 hata
- **Veri kalitesi:** 100/100 (tüm kontroller yeşil)
- **Nowgoal lig ID'leri doğrulandı:** GER D1=8 (35 değil!), FRA D1=11 (37 değil!), TUR D1=30 (52 değil!)

### Sprint 27 — TAMAMLANDI ✅ (Güvenlik + Temizlik)
- **DB yedekleme:** `scripts/backup-db.bat` — günlük pg_dump, 7 gün rotasyon
- **GitHub Actions cron devre dışı:** Tüm schedule'lar yorum satırına alındı (local DB ile gereksiz), sadece `workflow_dispatch` aktif
- **Audit raporları:** `docs/audit-backend-sept2026.md`, `docs/audit-frontend-sept2026.md`, `docs/audit-infrastructure-sept2026.md`
- **Local E2E test:** Backend serve + frontend dev birlikte çalıştı, health/analyze/bulten/sonuclar endpoint'leri doğrulandı

### Sprint 28 — TAMAMLANDI ✅ (Frontend Tam Yeniden Tasarım — Dark Tema Design System)
- **Bağlam:** Tüm frontend 24 dosyada yeniden yazıldı. Eski Tailwind sınıfları `--nv-` design token sistemine geçirildi.
- **Design token sistemi (`globals.css`):** 40+ CSS custom property — renkler, tipografi, spacing, shadow, radius. Dark-first.
- **Fontlar:** Inter (sans) + JetBrains Mono (mono) via `next/font/google`
- **Glassmorphism:** `backdrop-blur`, `bg-opacity` ile kart ve sidebar efektleri
- **Collapsible sidebar (desktop):** Dar/geniş toggle, localStorage hatırlama
- **Mobile bottom tab bar:** Sidebar yerine alt tab navigasyonu
- **CSS-only görseller:** `.nv-conf-ring` (conic-gradient confidence halkası), `.nv-pct-bar` (yüzde çubuğu) — 0 yeni npm bağımlılığı
- **Component listesi (16 component):** Tümü yeni design system ile yeniden yazıldı
- **Sonuç:** 638 backend + 266 frontend = **904 toplam test** (tümü yeşil)

### Sprint 29 — TAMAMLANDI ✅ (Test Uyumu + Görsel Zenginleştirme)
- **Faz A — Test Uyumu:**
  - `test_analysis_snapshots.py`: Zaman-bağımlı test düzeltildi — `kickoff_time` gelecek tarihe (2099) alındı (`prekickoff_picks` kontrolü)
  - `test_pattern_failure_handling.py`: asyncio.Lock event loop mismatch düzeltildi — stale lock temizleme eklendi
  - 638 backend + 266 frontend test yeşil
- **Faz B — Görsel Zenginleştirme (CSS-only, 0 yeni bağımlılık):**
  - **Maç Güç Skoru (`AnalyzeClient.tsx`):** `computePowerScore()` fonksiyonu — 5 faktörden 0-100 skor (Pattern B/C hacmi, top selection %, trends, dual archive). CSS conic-gradient gauge (80px), faktör badge'leri. Sadece MS sekmesinde, score > 0 ise görünür
  - **TrendsPanel W/D/L bar:** 6px yatay stacked bar (yeşil/amber/kırmızı) — galibiyet/beraberlik/mağlubiyet oranı görsel
  - **TrendsPanel Att/Yedi mini bar:** 4px karşılaştırmalı çubuklar (yeşil=atılan, kırmızı=yenilen), max değere ölçekli
  - **ScoreList frekans göstergesi:** Opacity gradient (1.0→0.6) + genişlik azalan frekans çubuğu + en iyi skora accent dot
- **Sonuç:** 638 backend + 266 frontend = **904 toplam test** (tümü yeşil)

### Sprint 8.10 — TAMAMLANDI ✅ (ACİL — Supabase Egress Optimizasyonu)
- **Problem:** Production'da Supabase egress 25,567 MB / 5 GB (%511) — Fair Use Policy aşıldı, tüm DB istekleri 402 dönüyor, servisimiz down
- **Kök neden:**
  1. `pattern_c.py` her çağrıda 13K+ matches satırı çekip Python'da filter (130MB/çağrı × 200 maç/gün run-pipeline = ~26 GB/gün)
  2. `/api/health.data_quality` (Sprint 8.9'da eklendi) UptimeRobot her 5dk pingde tüm matches taraması (~187 MB/gün)
- **Çözüm — Pattern C DB-side filter:**
  - `tolerance == 0.0` fast-path: `cast(Match.ft_all_ratios, JSONB) == cast(ft_ratios, JSONB)` PostgreSQL JSONB kanonik equality
  - 130 MB/çağrı → ~50 KB/çağrı (%99.96 azaltma)
  - `tolerance > 0.0` fallback yolu korundu (ileride fuzzy match için)
- **Çözüm — `/api/health` hafifletme:**
  - `data_quality` alanı `HealthResponse`'tan kaldırıldı
  - Yeni `/api/admin/quality` endpoint — manuel/CLI çağrılır, UptimeRobot çağırmaz
- **Yeni pytest:** `tests/test_pattern_c.py` (6 test) — `_ratios_match` fuzzy match davranışı; toplam 67 test yeşil
- **Beklenen toplam egress:** ~26 GB/gün → ~50 MB/gün (500x altı, free tier güvenli alanı)
- **Lokal test:** Supabase erişimi yok, smoke test prod kotası geri geldikten sonra
- **Kullanıcı kararı bekleyen:** Supabase Pro upgrade ($25/ay) anlık vs billing reset bekleme (~1 ay)

### Sprint 8.9 — TAMAMLANDI ✅ (Veri Bütünlüğü & Filtre Sertleştirme)
- **Problem:** UEL maçı 2976657 "ENG PR" sanıldı; UCL maçı 2976378 lig sanılıp tahmin üretildi; kupa maçları DB/bültende görünüyordu; sistem sürekli arşiv ekliyor → veri kalitesi izleme yok
- **Lig filtresi:** `app/analysis/league_filter.py` (CUP_KEYWORDS kara listesi 30+ keyword; LEAGUE_ALIASES kanonik form 50+ lig); `is_supported_league(*names)` çoklu parametre desteği; `canonical_league_name(name)` "ENG PR" → "English Premier League"
- **Maçın kendisi lig mi:** `check_match_filters`'a NOT_LEAGUE_MATCH kontrolü eklendi
- **Lig tespiti güçlendirildi:** `fetch_match_detail(expected_league_name=...)` — pipeline bültenden geçirir; H2H tabanlı tespit fallback
- **Soft delete + audit_log:** Migration `g4d2a7c9b815` — `matches.deleted_at`/`deleted_reason` + `audit_log` tablosu (id, timestamp, operation, target_match_id, actor, details JSONB); tüm SELECT(Match) sorgularına `deleted_at IS NULL` filtresi
- **Pre-write validation:** `_validate_row` — boş takım, kupa, saçma skor DB'ye yazılmaz
- **Kanonik lig adı:** `_result_to_row` `canonical_league_name` uygular; tutarsızlık önlenir
- **Pattern C sıkı:** `tolerance: 0.5 → 0.0`, `min_matches: 5 → 1`; frontend `match_count >= 1` (Pattern B 5'te kalır)
- **5 yeni CLI:** `prune-non-league` (soft delete + audit), `restore-deleted`, `audit-db` (kalite raporu + pattern self-check), `audit-patterns` (B/C davranış), `self-test` (E2E 7 adım)
- **`/api/health` data_quality:** quality_score 0-100, alt metrikler
- **Pytest 52 test:** kalıcı `tests/test_league_filter.py`, `test_pre_write_validation.py`, `test_trends.py` — hepsi yeşil

### Sprint 8.8 — TAMAMLANDI ✅ (Form & H2H Trendleri)
- **Backend `app/analysis/trends.py`:** `compute_trends(raw)` 3 blok döner
  - `home_form`: ev sahibinin son N **ev** maçı (lig, role="home")
  - `away_form`: deplasmanın son N **dış** maçı (lig, role="away")
  - `h2h`: son lig karşılaşmaları (ev sahibi perspektifinden)
  - Her blok: win/draw/loss %, KG Var %, Üst 2.5 %, ort gol, son 5 G/B/M
  - Minimum 3 örnek altında ilgili blok None
- **Migration `f5c8d2a1b394_add_trends_column`:** `matches.trends` JSONB kolonu (kullanıcı 2026-05-07'de Supabase'da uyguladı)
- **`pipeline/runner.py:_result_to_row`:** raw verildiyse `compute_trends(raw).model_dump()` ile `trends` kolonunu doldurur
- **`api/main.py`:** `AnalyzeResponse.trends: Optional[TrendsData]`; `_trends()` helper; `_build_from_db` saklı trends'i parse eder; `_do_analyze` Playwright path'inde de hesaplar
- **Frontend `lib/types.ts`:** `TrendBlock`, `TrendsData` interface'leri
- **`components/TrendsPanel.tsx`:** 3 mini kart yan yana (Ev/Dep Form, H2H)
  - Header: ikon + label + örneklem boyutu rozet
  - Mini timeline: son 5 sonuç G/B/M renkli noktalar (yeşil/sarı/kırmızı)
  - Metrikler: Galibiyet/Beraberlik/Mağlubiyet/KG Var/Üst 2.5/Att-Yedi
- **Mount noktası:** `app/analyze/[match_id]/page.tsx` — sadece MS periyodunda görünür (`activePeriod === "ft"`)

---

## Bilinen Teknik Notlar

- **Timezone:** nowgoal `data-t` attribute **UTC**'dir (Beijing UTC+8 değil). Istanbul = UTC+3. Eski kod +8 ekleyip sonra convert ediyordu → 16 saat ileri hata. `fixture.py`'de `_SITE_TZ = timezone.utc`.

- **Windows Playwright + uvicorn:** uvicorn `loop="auto"` Windows'ta `WindowsSelectorEventLoopPolicy` kullanır, Playwright subprocess açamaz. Çözüm: `cli/main.py`'de `loop="none"` + `api/main.py` modül seviyesinde `WindowsProactorEventLoopPolicy`.

- **Katman C tek sorgu:** `find_pattern_c_all_periods(ft_ratios)` FT oranlarıyla bir kez DB sorgular, aynı eşleşme setinden İY/2Y/MS istatistiklerini hesaplar. Periyot başına ayrı sorgu yapılsaydı İY'de eşleşme bulunup MS'de bulunmama gibi tutarsızlık oluşurdu.

- **DB-first analiz:** `_analyze_and_cache` önce DB kontrol eder. `run-pipeline` çalıştırıldıktan sonra tüm maçlar DB'de olur ve Playwright hiç açılmaz.

- **Typer 0.12.5 + Python 3.11 bug (çözüldü):** Eski Typer'da `bool` Option'lar string `'False'` dönebilirdi. Sprint 11'de Typer 0.25.1'e upgrade edildi, Sprint 17'de `_flag()` helper'ı kaldırılıp tüm çağrılar direkt bool'a çevrildi.

- **Next.js proxy & BACKEND_URL:** `next.config.ts`'te `/api/*` → `http://localhost:8000/api/*` rewrite var. `lib/env.ts` `getApiBase()` SSR/CSR ayrımı yapar. Sebep: Vercel SSR (server component) `BACKEND_URL` üzerinden Render'a direkt gider; tarayıcı tarafı (CSR) `BACKEND_URL` görmez → boş string → Next.js proxy üzerinden Render'a ulaşır. Local'de hiç `BACKEND_URL` yoksa proxy yine local backend'e gider.

- **Frontend Next.js — özel sürüm:** `frontend/AGENTS.md` Next.js'in eğitim verisindekinden farklı olabileceğini, `node_modules/next/dist/docs/` okunmadan kod yazılmaması gerektiğini söylüyor. Frontend kodu değiştirmeden önce **mutlaka** `frontend/AGENTS.md` okunacak.

- **Neon pooler:** Transaction mode pooler ile asyncpg kullanırken `pool_size=2, max_overflow=0, connect_args={"statement_cache_size": 0}` zorunlu. asyncpg URL'de `sslmode` desteklemez — `connection.py` URL'den strip edip `ssl.create_default_context()` ile connect_args'a ekler. `channel_binding` parametresi de strip edilir.

- **fixture_cache tablosu:** `/api/fixture` 3 katmanlı cache kullanır: memory (5dk) → DB (geçmiş=kalıcı, bugün=1saat) → Playwright. Migration zinciri: `641438be3ff8` (initial schema) → `c1b1b4cd333b` (h2 skorları + kickoff_time) → `a3f9e2b1c4d5` (fixture_cache).

- **Otomatik skor güncelleme:** `_score_updater` Sprint 7'de kaldırıldı. Skor güncelleme sadece GitHub Actions gece cron'u (`update-scores`) ve CLI ile yapılır.

- **Arşive ekleme yapılmıyor:** Mevcut arşiv sabittir, yeni lig/sezon eklenmeyecek. Var olan maçların yüzdeleri değişmesin diye bu karar alındı.

- **Pattern matching self-exclusion:** `find_pattern_b_matches` ve `find_pattern_c_all_periods` fonksiyonları `exclude_match_id` parametresi alır. Bülten maçı analiz edilirken kendi match_id'si geçilmeli — DB'de sonucu varsa kendi kendini analiz etmemesi için. `main.py`'deki `_build_from_db` ve `_do_analyze` bunu otomatik yapar.

- **Handikap convention:** `Hnd(2:0)` → ev sahibi +2 head start alır = deplasman takımının 2 golü "silinir" → `hnd_a20` (`eff_h=h, eff_a=a-2`). `Hnd(0:2)` → deplasman +2 head start alır → `hnd_h20` (`eff_h=h-2, eff_a=a`). Eski kodda labellar takımlara ters bağlanmıştı (Sprint 7'de düzeltildi).

- **Canlı maç tespiti:** Sonuçlar sayfasında `kickoff_time + 110 dakika > now` ise maç muhtemelen hâlâ oynuyor → "Canlı" rozeti gösterilir. `_score_updater` canlı skorları da kaydedebilir (gerçek bitişi takip etmiyor), bu yüzden frontend tarafı tespit yapılıyor.

- **Render.com uyku modu:** Render free tier 15dk inaktivite sonrası uyku + ~30sn cold start. UptimeRobot 5dk'da bir HEAD ping (`/api/health`) ile sıcak tutulabilir. (Eski Railway devre dışı.)

- **Bg worker DB-only (Sprint 7 acil):** Önceki tasarım fixture yüklendikten sonra TÜM maçlar için arka planda Playwright açıyordu — pipeline'sız günlerde container OOM olurdu. Yeni tasarım: bg worker SADECE DB-hit yapar (`_analyze_db_only`). DB miss'ler atlanır; kullanıcı tıkladığında foreground tek seferlik scrape yapar. Bg worker + Sprint 8 lazy backfill kombinasyonu sayesinde DB'deki maçların pattern'lerini de arka planda ısıtır.

- **`/api/fixture` hard timeout (Sprint 7 acil):** Playwright scrape `asyncio.wait_for(timeout=20)` ile sarmalı. Vercel SSR ~25sn'de düşer, biz 20sn'de 503 dönüyoruz — backend ölmez, kullanıcı "fetch failed" görür ama sistem ayakta kalır.

- **Pattern saklama (Sprint 8):** `matches` tablosunda 6 JSONB kolon (`pattern_ht/h2/ft_b/c`). `exclude_match_id=match_id` ile hesaplanıp saklanır → okuma sırasında ek filtre gerekmez. Pattern eksikse `_build_from_db` runtime hesabı yapıp **write-through** ile DB'ye yazar (lazy backfill). Storage tahmini ~450MB Neon free tier 500MB sınırına yakın — aşılırsa arşiv prune.

- **`compute_all_patterns` (Sprint 8):** `app/analysis/persist.py` — pipeline ve API tek bir kanaldan pattern üretir. 3 paralel pattern_b çağrısı + 1 pattern_c (3 periyot döner) `asyncio.gather` ile aynı anda hesaplanır.

- **Yedek pipeline cron (Sprint 8):** GitHub Actions free tier cron kırılgan (1-2 saat geç çalışabilir). 08:00 ve 09:00 İstanbul olmak üzere 2 cron tanımlı. İdempotent upsert sayesinde ikisi de başarılı olursa veri zarar görmez.

- **DB write retry (Sprint 8.3):** `_with_retry` helper (`app/pipeline/runner.py`) — pooler ara sıra connection drop yapabiliyor; `_upsert` ve `update_results` write'ları 3 deneme + 0.5/1.0/2.0s exponential backoff ile sarmalı. Geçici hatalar sessizce iyileşir.

- **`/api/match/{id}` fallback (Sprint 8.3):** DB miss'te Playwright scrape + upsert; `asyncio.wait_for(timeout=25)` ile sarılı (Vercel SSR ~25-30sn limiti içinde). Scrape başarısız olursa 404; timeout olursa 504. Sonraki ziyaret hızlı (DB'de hazır).

- **Fixture tarih sınırı (Sprint 8.3):** `/api/fixture` -30 / +14 gün dışındaki tarihler için 400 döner. Yanlışlıkla uçuk tarih (örn. 2030-01-01) → Playwright sürekli açılmaz.

- **`useTransition` periyot sekmeleri (Sprint 8.3):** Analiz sayfasında İY/2Y/MS geçişi `startTransition` ile sarılı. Buton tıklaması anında hisli; React arka planda re-render eder, içerik `isPending` iken hafif soluk (opacity 0.6).

- **Frontend `lib/leagues.ts` (Sprint 8.3):** Backend artık tam lig adı dönüyor ("English Premier League"). Eski "ENG PR" kısa kodları kaldırıldı; yeni eşleme bayrak + kısa görsel kod (ENG, ESP, ITA, ...) sözlüğü. Bilinmeyen lig için `⚽ + —` fallback.

- **Error boundary (Sprint 8.3):** `app/error.tsx` Next.js convention — React render hatalarında otomatik fallback ("Tekrar dene" butonlu kart). Beyaz ekran yok, kullanıcı kurtarılabilir.

- **Confidence formülü (Sprint 8.4):** `confidence = (pct/100) × volume_weight × market_weight × dual_bonus`. `volume_weight = min(1, ln(matchCount+1) / ln(30))` — 5 maçta 0.50, 30+ maçta 1.0. `market_weight` 1.0 (ana pazarlar) → 0.4 (encok yarı, iy/2y kg kombineleri). `dual_bonus = 1.15` eğer her iki arşivde de ≥%65.

- **`MarketSpec.excludePeriods` (Sprint 8.4):** `confidence.ts` MARKETS tablosunda her pazara `excludePeriods?: Period[]` alanı. IY/2Y'de iddaa açmayan pazarlar (2.5/3.5 A/Ü, taraf 2.5, handikaplar, MS+2.5 kombo) bu listede `["ht", "h2"]` olarak işaretlenir. `isMarketActive` filtreleyerek Top Picks + MarketSummary + DetailedStats üçü birden tutarlı.

- **Combo domain mantığı (Sprint 8.5):** `combos.ts:DOMAIN_OF` 30+ pazarı 14 domain'e gruplar (`match_result`, `total_goals`, `btts`, `home_total`, `away_total`, `iy_ms`, vs.). Bir leg seçilince aynı domain'den ikinci leg yasaklanır → bağımsızlık varsayımı daha sağlam. `HARD_CONFLICTS` ekstra keskin çelişki çiftleri (örn. `result_x` + `fark_ev1`).

- **Joint olasılık korelasyon düzeltmesi (Sprint 19):** `combos.ts` ve `cart.ts` artık `P(A,B) = P(A) × P(B) × corr(A,B)` formülüyle hesaplıyor. Poisson modeli (λ_h=1.37, λ_a=1.12) ile 299 pazar çifti korelasyon faktörü hesaplandı ve `correlation-table.json`'da statik tablo olarak saklanıyor. `lib/correlations.ts` getCorrectionFactor + computeJointProb sağlar. Bilinmeyen çiftler için corr=1.0 (bağımsız varsayım) uygulanır. Backend'de `/api/correlations` endpoint'i dinamik güncelleme için hazır.

- **Dinamik eşik formülü (Sprint 8.6):** `dynamicMinPct = max(64, 80 - log10(n+1) × 8)`. Wilson alt sınırının pragmatik yaklaşımı. Küçük örneklemde yanıltıcı yüksek yüzdeyi eler, büyük örneklemde gerçek değerli tahminleri keser. `getTopPicks` artık `{picks, effectiveMinPct, matchCount}` döner — UI başlıkta gösterir.

- **Bahis sepeti localStorage anahtarları:** `nortverse_bet_cart` (Sprint 8.7), `nortverse_detailed_open` (Sprint 8.4). Cross-tab sync için `storage` event + `nortverse-cart-updated` custom event. SSR'da hidrasyon yarış koşulu önlemek için `useCart` `hydrated` flag — boş sepette `BetCart` render bile etmez.

- **MatchContext (Sprint 8.7):** `lib/match-context.tsx` analyze sayfasında match metadata'yı (`matchId`, `homeTeam`, `awayTeam`) paylaşır. Tüm pick component'leri `useMatchInfo()` ile match bilgisini alır → prop drilling yok. `MatchProvider` sadece analyze page'inde sarar, diğer sayfalarda `useMatchInfo()` null döner → "+" butonu görünmez.

- **Trends mimarisi (Sprint 8.8):** `compute_trends(raw)` ham `MatchRawData`'dan 3 blok üretir. `_result_to_row` pipeline path'inde, `_do_analyze` API path'inde DB'ye `trends` JSONB yazar. `_build_from_db` DB'den okur, parse hatası warning + None döner. **Lazy backfill yok** — eski maçlarda `trends` null kalır, frontend sessizce gizler. Yeni gelen maçlar (her run-pipeline veya foreground scrape) trends ile yazılır.

- **Trends migration adımı (Sprint 8.8):** Dockerfile'daki `alembic upgrade head` sayesinde (Sprint 9) container her açılışta schema güncel. Eski not: `f5c8d2a1b394` (trends) Supabase'da 2026-05-07'de manuel uygulanmıştı.

- **Lig filtresi `is_supported_league` (Sprint 8.9):** Hibrit yaklaşım — kara liste keyword (champions/europa/cup/friendly/qualifier/...) + beyaz liste override (`LEAGUE_ALIASES` içindeki ad zaten geçer). Çoklu parametre kabul eder (`is_supported_league(name, code)`); biri lig sayılırsa True.

- **Lig adı tespit önceliği (Sprint 8.9):** `fetch_match_detail` üç kademe: (1) `expected_league_name` parametresi (bültenden gelir, en güvenilir), (2) `_extract_main_match_info` HTML `.fbheader > a`, (3) `_detect_main_league_code` H2H tabanlı (en zayıf, fallback). Aston Villa-Nottingham Forest UEL sorunu (3. yöntemin H2H'taki "ENG PR" maçlarını sayması) (1) ile çözüldü.

- **Soft delete (Sprint 8.9):** `matches.deleted_at IS NOT NULL` ise satır "silinmiş" sayılır. Pattern_b/c, /api/fixture, /api/results, /api/match, list_matches — tüm SELECT(Match) sorgularında `deleted_at IS NULL` filtresi eklendi. Geri alma: `restore-deleted <match_id>` komutu. Audit_log tablosu tüm prune/restore işlemlerini timestamp'li saklar.

- **Migration `g4d2a7c9b815` (Sprint 8.9):** Manuel uygulanması gereken SQL:
  ```sql
  ALTER TABLE matches ADD COLUMN deleted_at TIMESTAMPTZ NULL;
  ALTER TABLE matches ADD COLUMN deleted_reason VARCHAR(50) NULL;
  CREATE INDEX ix_matches_deleted_at ON matches(deleted_at) WHERE deleted_at IS NULL;
  CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operation VARCHAR(50) NOT NULL,
    target_match_id VARCHAR(20),
    actor VARCHAR(100),
    details JSONB
  );
  CREATE INDEX ix_audit_log_timestamp ON audit_log(timestamp);
  CREATE INDEX ix_audit_log_target ON audit_log(target_match_id);
  ```

- **Pre-write validation (Sprint 8.9):** `_validate_row(row)` `_upsert` öncesi kontrol — boş takım/lig kodu, kupa filtresi, saçma skor (negatif/>30) → reddedilir, log.error, ama pipeline devam eder. Pipeline başarısızlığı sayılmaz.

- **Pattern C tolerance=0.0 (Sprint 8.9):** Eski `±0.5` toleransta yan yana iki "kova" eşleşmiş sayılıyordu (örn. 3.5 ile 4.0). Yeni: tam eşleşme. Eşleşme sayısı 5-10x düştü ama kalite arttı. `min_matches: 5 → 1` çünkü tolerance=0 sıkı, 1-4 maç düşük güven kabul edilebilir. Frontend `match_count >= 1` ile Pattern C'yi gösterir; UI'da düşük örneklemde dynamicMinPct doğal koruma sağlar (Sprint 8.6).

- **Kanonik lig adı (Sprint 8.9+20):** `LEAGUE_ALIASES` 50+ alias → kanonik ad. `_result_to_row` `canonical_league_name(r.league_code)` uygular → yeni maçlar tutarlı. Eski maçlar için `normalize-leagues --apply` CLI komutu (Sprint 20) toplu normalize yapar. `repair.py:needs_normalization()` ile `audit-db` normalize edilmemiş kayıt sayısını gösterir.

- **Audit & quality görünürlük (Sprint 8.9 → 8.10 değiştirildi):** Quality skoru artık `/api/admin/quality` endpoint'inde. Sprint 8.9'da `/api/health` içine konmuştu ama UptimeRobot pinglerinde tüm matches taraması = ~187 MB/gün egress → Sprint 8.10'da ayrı endpoint'e taşındı. UptimeRobot artık hafif `/api/health` pingler. CLI `audit-db` aynı bilgiyi Rich tabloyla verir.

- **Pattern C egress optimizasyonu (Sprint 8.10):** Sprint 8.9'da `tolerance=0.0` koyduktan sonra fast-path mümkün oldu — `cast(Match.ft_all_ratios, JSONB) == cast(ft_ratios, JSONB)` ile DB-side filter. Eski yol 13K+ satır çekip Python'da filtere = ~130 MB/çağrı egress; yeni yol ~50 KB/çağrı (%99.96 azaltma). PostgreSQL JSONB karşılaştırması kanonik (key sırası önemsiz). tolerance > 0 fallback yolu `_ratios_match` Python fonksiyonu ile korundu.

- **Backend Cache-Control middleware (Sprint 8.10b):** `app/api/main.py` `add_cache_headers` middleware'i — `/api/fixture` (5dk), `/api/results` (2dk), `/api/matches` (5dk), `/api/health` (30sn) için `Cache-Control: public, s-maxage=N, stale-while-revalidate=60` header'ları ekler. Cloudflare CDN önüne alındığında edge cache çalışır → origin call (Render → DB) %80 azalır. Vercel `revalidate` SSR cache'inden farklı, ortogonal: birlikte çalışırlar.

- **GitHub Actions cron'ları aktif (Sprint 14.1):** `.github/workflows/daily_pipeline.yml` 3 cron entry (08:00 pipeline + 22:00/00:30 update-scores), `recompute_patterns.yml` aylık (her ayın 1'i 03:00 İstanbul). Neon kota optimizasyonu: 7→3 cron, haftalık→aylık recompute. Column pruning ile birlikte tahmini egress 3-4 GB/ay → 100-300 MB/ay.

- **`run_pipeline` fixture_cache yazıyor (Sprint 14):** Pipeline fixture'ları çektikten sonra `fixture_cache` tablosunu da dolduruyor. Render free tier Playwright çalıştıramadığı için bu kritik — GitHub Actions'ta pipeline çalışınca `/api/fixture` cache'den döner, Playwright'a gerek kalmaz.

- **Neon PostgreSQL geçişi (Sprint 13):** Supabase egress limiti aşılıp Oracle Cloud başarısız olunca Neon free tier seçildi. asyncpg `sslmode` URL param desteklemez — `connection.py` URL'den strip edip `ssl.create_default_context()` ile bağlanır. `channel_binding` de strip edilir. Supabase'den 4394 maç aktarıldı.

- **`history.py` merkezi veri seçimi (Sprint 12 denetim):** `select_history(matches, team, ...)` — gelecek veri sızıntısı (future leakage), self-inclusion, duplicate ve kupa maçı filtreleri tek merkezde. `engine.py`, `trends.py` ve pattern hesaplamaları bu fonksiyonu kullanır. Eski dağınık filtreleme kaldırıldı.

- **`conftest.py` test DB izolasyonu (Sprint 12 denetim):** `tests/conftest.py` test başlamadan önce `DATABASE_URL`'yi dummy değere override eder — testlerin yanlışlıkla production DB'ye bağlanması engellenir.

- **Frontend doğrulama modülleri (Sprint 12 denetim):** `analysis-validation.ts` (analiz verisi şekil kontrolü), `list-validation.ts` (liste veri doğrulama), `selection-compatibility.ts` (seçim uyumluluk), `pattern-fields.ts` (pattern alan isimleri), `dates.ts` (tarih yardımcıları) — frontend'e gelen backend verisinin beklenen formatta olduğunu doğrular, bozuk veri UI crash'i önler.

- **Stale write koruması (Sprint 12 denetim):** `_upsert` fonksiyonu `analyzed_at` karşılaştırır — DB'deki kaydın daha yeni bir analizi varsa eski veriyle üzerine yazılmaz. `test_stale_writes.py` ile doğrulanır.

- **PatternComputationError yönetimi (Sprint 12 denetim):** Pattern hesaplamasında hata olursa maç atlanır, pipeline devam eder. Hata log'a yazılır. `test_pattern_failure_handling.py` ile doğrulanır.

- **CI pipeline `quality.yml` (Sprint 12+18):** Her push/PR'da otomatik çalışır. Backend: `ruff check` + `pytest`. Frontend: `vitest` + `tsc --noEmit` + `npm run build`. E2E (Playwright): sadece `workflow_dispatch` ile tetiklenir (backend gerektirir). Üç bağımsız job — biri düşerse diğeri devam eder.

---

## Teknoloji Kararları

- **Python 3.11+** / FastAPI / SQLAlchemy 2.x async / Pydantic 2
- **Playwright** (nowgoal Cloudflare/dinamik JS render — BS4 yetersiz)
- **PostgreSQL** (Neon free tier — sınırsız egress, 0.5 GB depo) — 30K+ maç hedefi için JSONB şart
- **Next.js App Router + TailwindCSS** frontend
- **GitHub Actions** cron (günlük `run-pipeline` + gece `update-scores`)
- **Render.com** backend (Docker, `mcr.microsoft.com/playwright/python:v1.47.0-jammy`, free tier — 15dk uyku + cold start)
- **Vercel** frontend (Next.js otomatik deploy, `BACKEND_URL=https://nortverse-backend.onrender.com`)
- **Typer + Rich** CLI
- Tamamen ücretsiz altyapı

## Çalışma Tarzı

Kullanıcı kod tecrübesinde sınırlı. **Yapılacaklar:**
- Türkçe yorumlar, Türkçe commit mesajları, Türkçe CLI
- Her önemli karar açıklansın
- Modüler ve okunabilir kod — tek dosyada 1000+ satır olmayacak
- Kullanıcı komutları kopyala-yapıştır çalıştıracak; Windows PowerShell ortamına dikkat

## Kullanıcıya Sormadan Yapılmayacak Şeyler

- Büyük mimari değişiklikler
- Yeni altyapı seçimleri (DB, framework, vb.)
- Teknoloji yığınına yeni şey ekleme
- Bağımlılık ekleme (requirements.txt'ye madde ekleme)

## Test Maçı

Test için: **2813084** (Kayserispor vs Karagumruk, TUR D1, bitmiş maç 1-0).

## Excel Referansı

Kullanıcının Excel'i: `Claude.xlsm` (projeyle gelmiyor, kullanıcıda).
- ARSIV-1: 3490 satır, 1633 maç + gerçek sonuçlar (Katman B referansı)
- NORT ANALİZ: Pattern matching sonuçları
- BAHİS TABLOSU: Manuel bahis önerileri

---

## Kaldığımız Yer (2026-09-25 — Sprint 29 sonu, Local Development + Veri Kalitesi 100/100)

### ✅ Mevcut Durum — Local Development + Sprint 25-29 Tamamlandı

Cloud DB sorunları (Supabase egress, Neon kota) sonrası tamamen local altyapıya geçildi:

| Katman | Servis | Detay |
|---|---|---|
| **Frontend** | Local Next.js dev | `http://localhost:3000` |
| **Backend** | Local FastAPI | `http://localhost:8000` |
| **Veritabanı** | Docker PostgreSQL | Port 5433, 9,257 aktif maç |
| **Otomasyon** | Windows Task Scheduler | 4 bat script (pipeline + skor + yedekleme) |
| **CI/CD** | GitHub Actions | `quality.yml` aktif (push/PR), cron'lar devre dışı |

**Eski cloud deployment (Render + Vercel + Neon):** Konfigürasyon korunuyor ama aktif değil.

### Veri Kalitesi (Sprint 26 sonrası)

| Metrik | Değer |
|---|---|
| Aktif maç | 9,257 |
| Pattern eksik | 0 |
| Pattern tutarsızlık | 0 |
| Quality score | 100 / 100 |
| Arşiv | 7 lig × 5 sezon |

### Test Durumu (Sprint 29 sonrası)

| Katman | Araç | Test Sayısı | Durum |
|---|---|---|---|
| **Backend** | pytest | 638 | ✅ Yeşil |
| **Frontend birim** | vitest | 266 | ✅ Yeşil |
| **Frontend E2E** | Playwright | 28 | ✅ Yapı doğrulanmış (backend gerektirir) |
| **Toplam** | — | 932 | — |

### Sıradaki Adımlar

Sprint 29 tamamlandı. Bekleyen konular kullanıcı kararı gerektirir:

- **Deploy kararı:** Tamamen local mi kalacak, Cloudflare Tunnel mi, VPS ($4-5/ay) mi, yoksa Render+Vercel'e dönüş mü?
- **Excel audit:** `Claude.xlsm` ile DB çapraz doğrulama (dosya kullanıcıda)
- **Auth + Premium:** Monetizasyon için kullanıcı sistemi (büyük mimari değişiklik — onay gerekir)
- **Canlı maç + WebSocket:** Real-time skor push (onay gerekir)

### Bilinen Açık Konular

- **Veri doğruluğu derin audit:** Excel ile çapraz doğrulama yapılmadı; spot-check geçti
- **Windows console Türkçe karakter:** PYTHONIOENCODING=utf-8 olmadan CLI çıktısında UnicodeEncodeError olabilir
- **CLAUDE_HANDOFF.md:** Önceki oturumdan kalan V3 doğrulama şeması devir notu — mevcut yol haritasıyla ilgisiz, temizlenebilir
- **Eski cloud deployment:** Render/Vercel/Neon yapılandırması korunuyor ama aktif değil; deploy kararından sonra temizlenecek veya yeniden aktifleştirilecek