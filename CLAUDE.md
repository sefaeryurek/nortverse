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

# Veri kalitesi & Audit (Sprint 8.9)
python -m app.cli.main self-test 2813084             # E2E sistem testi (7 adım kontrol)
python -m app.cli.main audit-db                      # DB sağlık raporu (kalite skoru, eksik veri)
python -m app.cli.main audit-patterns 2813084        # Pattern B/C eşleşme davranışı + tolerance etkisi
python -m app.cli.main prune-non-league              # Kupa maçlarını soft-delete (default dry-run)
python -m app.cli.main prune-non-league --apply      # Gerçekten temizle (audit_log'a kayıt düşer)
python -m app.cli.main restore-deleted 2976657       # Soft-deleted maçı geri al

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
├── backend/
│   ├── app/
│   │   ├── config.py              # ScraperConfig, AnalysisConfig (frozen dataclass)
│   │   ├── models.py              # Pydantic: FixtureMatch, HistoricalMatch, MatchRawData
│   │   ├── db/
│   │   │   ├── connection.py      # SQLAlchemy async engine + get_session() — pool_size=2, statement_cache_size=0 (Supabase PgBouncer)
│   │   │   └── models.py          # Match + FixtureCache ORM — JSONB kolonlar, actual skorlar
│   │   ├── scraper/
│   │   │   ├── browser.py         # Playwright wrapper (browser_context context manager)
│   │   │   ├── fixture.py         # Günlük bülten — Hot filtreli, kickoff UTC timezone
│   │   │   ├── match_detail.py    # H2H sayfası parse + gerçek skor çıkarımı
│   │   │   └── league.py          # Lig sayfasından maç ID listesi (arşiv için)
│   │   ├── analysis/
│   │   │   ├── scores.py          # ALL_SCORES sabiti
│   │   │   ├── filtering.py       # check_match_filters
│   │   │   ├── engine.py          # analyze_match (Katman A)
│   │   │   ├── pattern_b.py       # find_pattern_b_matches — JSONB equality
│   │   │   ├── pattern_c.py       # find_pattern_c_all_periods — FT oranları ±0.5 fuzzy, TEK sorgu
│   │   │   └── pattern_stats.py   # PatternResult model + compute_stats — ~130 istatistik alanı
│   │   ├── api/
│   │   │   └── main.py            # FastAPI — fixture cache, bg queue, DB-first analiz
│   │   ├── pipeline/
│   │   │   └── runner.py          # run_pipeline + update_results: fetch → analiz → upsert
│   │   └── cli/
│   │       └── main.py            # Typer + Rich CLI
│   ├── alembic/                   # DB migration
│   ├── tests/
│   │   └── test_analysis.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx             # Root layout (dark tema, sidebar)
│   │   ├── page.tsx               # Root → /bulten redirect
│   │   ├── error.tsx              # Global error boundary (Sprint 8.3) — React crash fallback
│   │   ├── bulten/
│   │   │   └── page.tsx           # Server component — fixture listesi (Suspense)
│   │   ├── sonuclar/
│   │   │   └── page.tsx           # Server component — biten maçlar, skor, tahmin özeti
│   │   └── analyze/[match_id]/
│   │       └── page.tsx           # Client component — maç analiz sayfası
│   ├── components/
│   │   ├── BultenRow.tsx          # Maç satırı (link ?home=&away= param ile, lig bayrak)
│   │   ├── DayTabs.tsx            # 8 günlük kayan pencere, basePath prop ile
│   │   ├── IddaaCoupon.tsx        # Arşiv istatistik kartları (Katman B + C) + Altın Oranlar
│   │   ├── ScoreList.tsx          # Katman A 3.5+ skor listesi
│   │   ├── Sidebar.tsx            # Sol menü (md altı gizli — mobile)
│   │   └── StatBadge.tsx          # Yeniden kullanılabilir yüzde rozeti
│   ├── lib/
│   │   ├── api.ts                 # Backend API çağrıları (BASE = BACKEND_URL ?? "" — SSR'da Railway, CSR'da proxy)
│   │   ├── leagues.ts             # Lig adı → bayrak + kısa kod sözlüğü (Sprint 8.3)
│   │   └── types.ts               # TypeScript type'ları (PatternResult ~130 alan)
│   ├── AGENTS.md                  # ⚠️ Next.js özel sürüm uyarısı — kod yazmadan önce oku
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
- `0 5 * * *` → 08:00 İstanbul → `run-pipeline` (sabah analiz, birinci deneme)
- `0 6 * * *` → 09:00 İstanbul → `run-pipeline` (yedek; 08:00 cron kaçırırsa)
- `30 21 * * *` → 00:30 İstanbul → `update-scores` (gece skor güncelleme)
- `0 23 * * *` → 02:00 İstanbul → `update-scores` (geç maçlar)

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

## Mevcut Durum (Sprint 8.9 — TAMAMLANDI ✅ — Veri Bütünlüğü)

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
- ✅ **DB write retry (Sprint 8.3):** `_with_retry` yardımcısı — `_upsert` ve `update_results` 3 deneme + exponential backoff (Supabase PgBouncer drop koruması)
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
- ✅ **Pytest 52 test (Sprint 8.9):** `test_league_filter.py` (28), `test_pre_write_validation.py` (10), `test_trends.py` (6) — kalıcı test suite
- ✅ `pattern_stats.py`: ~130 alan, 9 bölüm
- ✅ Railway deployment: `https://nortverse-production.up.railway.app`
- ✅ `fixture_cache` DB tablosu: bülten verileri kalıcı, server restart'tan etkilenmez
- ✅ `/api/results` endpoint: günlük biten maçlar + Katman A kapsamı
- ✅ `update-scores` CLI: biten maçların actual skorlarını DB'ye yazar
- ✅ Supabase PgBouncer uyumu: `pool_size=2`, `statement_cache_size=0`
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
- ✅ SSR URL düzeltildi: `BACKEND_URL` env var ile Vercel → Railway direkt
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

- ✅ **UptimeRobot kuruldu:** `/api/health`'e 5dk'da bir HEAD ping → Railway uyumaz
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

- **Typer 0.12.5 + Python 3.11 bug:** `bool` Option'lar string `'False'` dönebilir. `cli/main.py`'de `_flag()` yardımcısı çözüyor.

- **Next.js proxy & BACKEND_URL:** `next.config.ts`'te `/api/*` → `http://localhost:8000/api/*` rewrite var. `lib/api.ts`'te `BASE = process.env.BACKEND_URL || ""`. Sebep: Vercel SSR (server component) `BACKEND_URL` üzerinden Railway'e direkt gider; tarayıcı tarafı (CSR) `BACKEND_URL` görmez → boş string → Next.js proxy üzerinden Railway'e ulaşır. Local'de hiç `BACKEND_URL` yoksa proxy yine local backend'e gider.

- **Frontend Next.js — özel sürüm:** `frontend/AGENTS.md` Next.js'in eğitim verisindekinden farklı olabileceğini, `node_modules/next/dist/docs/` okunmadan kod yazılmaması gerektiğini söylüyor. Frontend kodu değiştirmeden önce **mutlaka** `frontend/AGENTS.md` okunacak.

- **Supabase PgBouncer:** Transaction mode pooler (port 5432) ile asyncpg kullanırken `pool_size=2, max_overflow=0, connect_args={"statement_cache_size": 0}` zorunlu. Aksi halde GitHub Actions gibi ortamlarda ECIRCUITBREAKER hatası alınır.

- **fixture_cache tablosu:** `/api/fixture` 3 katmanlı cache kullanır: memory (5dk) → DB (geçmiş=kalıcı, bugün=1saat) → Playwright. Migration zinciri: `641438be3ff8` (initial schema) → `c1b1b4cd333b` (h2 skorları + kickoff_time) → `a3f9e2b1c4d5` (fixture_cache).

- **Otomatik skor güncelleme:** `api/main.py`'de `_score_updater` async task her 30 dakikada `update_results()` çağırır. Railway container ayakta olduğu sürece çalışır. Ayrıca GitHub Actions'da gece 00:30 ve 02:00 İstanbul'da da çalışır (yedek).

- **Arşive ekleme yapılmıyor:** Mevcut arşiv sabittir, yeni lig/sezon eklenmeyecek. Var olan maçların yüzdeleri değişmesin diye bu karar alındı.

- **Pattern matching self-exclusion:** `find_pattern_b_matches` ve `find_pattern_c_all_periods` fonksiyonları `exclude_match_id` parametresi alır. Bülten maçı analiz edilirken kendi match_id'si geçilmeli — DB'de sonucu varsa kendi kendini analiz etmemesi için. `main.py`'deki `_build_from_db` ve `_do_analyze` bunu otomatik yapar.

- **Handikap convention:** `Hnd(2:0)` → ev sahibi +2 head start alır = deplasman takımının 2 golü "silinir" → `hnd_a20` (`eff_h=h, eff_a=a-2`). `Hnd(0:2)` → deplasman +2 head start alır → `hnd_h20` (`eff_h=h-2, eff_a=a`). Eski kodda labellar takımlara ters bağlanmıştı (Sprint 7'de düzeltildi).

- **Canlı maç tespiti:** Sonuçlar sayfasında `kickoff_time + 110 dakika > now` ise maç muhtemelen hâlâ oynuyor → "Canlı" rozeti gösterilir. `_score_updater` canlı skorları da kaydedebilir (gerçek bitişi takip etmiyor), bu yüzden frontend tarafı tespit yapılıyor.

- **Railway uyku modu — ÇÖZÜLDÜ (Sprint 7):** UptimeRobot 5dk'da bir HEAD ping atıyor (`/api/health`). Container hep ayakta. Free tier yeterli.

- **Bg worker DB-only (Sprint 7 acil):** Önceki tasarım fixture yüklendikten sonra TÜM maçlar için arka planda Playwright açıyordu — pipeline'sız günlerde container OOM olurdu. Yeni tasarım: bg worker SADECE DB-hit yapar (`_analyze_db_only`). DB miss'ler atlanır; kullanıcı tıkladığında foreground tek seferlik scrape yapar. Bg worker + Sprint 8 lazy backfill kombinasyonu sayesinde DB'deki maçların pattern'lerini de arka planda ısıtır.

- **`/api/fixture` hard timeout (Sprint 7 acil):** Playwright scrape `asyncio.wait_for(timeout=20)` ile sarmalı. Vercel SSR ~25sn'de düşer, biz 20sn'de 503 dönüyoruz — backend ölmez, kullanıcı "fetch failed" görür ama sistem ayakta kalır.

- **Pattern saklama (Sprint 8):** `matches` tablosunda 6 JSONB kolon (`pattern_ht/h2/ft_b/c`). `exclude_match_id=match_id` ile hesaplanıp saklanır → okuma sırasında ek filtre gerekmez. Pattern eksikse `_build_from_db` runtime hesabı yapıp **write-through** ile DB'ye yazar (lazy backfill). Storage tahmini ~450MB Supabase free tier 500MB sınırına yakın — aşılırsa arşiv prune.

- **`compute_all_patterns` (Sprint 8):** `app/analysis/persist.py` — pipeline ve API tek bir kanaldan pattern üretir. 3 paralel pattern_b çağrısı + 1 pattern_c (3 periyot döner) `asyncio.gather` ile aynı anda hesaplanır.

- **Yedek pipeline cron (Sprint 8):** GitHub Actions free tier cron kırılgan (1-2 saat geç çalışabilir). 08:00 ve 09:00 İstanbul olmak üzere 2 cron tanımlı. İdempotent upsert sayesinde ikisi de başarılı olursa veri zarar görmez.

- **DB write retry (Sprint 8.3):** `_with_retry` helper (`app/pipeline/runner.py`) — Supabase PgBouncer ara sıra connection drop yapıyor; `_upsert` ve `update_results` write'ları 3 deneme + 0.5/1.0/2.0s exponential backoff ile sarmalı. Geçici hatalar sessizce iyileşir.

- **`/api/match/{id}` fallback (Sprint 8.3):** DB miss'te Playwright scrape + upsert; `asyncio.wait_for(timeout=25)` ile sarılı (Vercel SSR ~25-30sn limiti içinde). Scrape başarısız olursa 404; timeout olursa 504. Sonraki ziyaret hızlı (DB'de hazır).

- **Fixture tarih sınırı (Sprint 8.3):** `/api/fixture` -30 / +14 gün dışındaki tarihler için 400 döner. Yanlışlıkla uçuk tarih (örn. 2030-01-01) → Playwright sürekli açılmaz.

- **`useTransition` periyot sekmeleri (Sprint 8.3):** Analiz sayfasında İY/2Y/MS geçişi `startTransition` ile sarılı. Buton tıklaması anında hisli; React arka planda re-render eder, içerik `isPending` iken hafif soluk (opacity 0.6).

- **Frontend `lib/leagues.ts` (Sprint 8.3):** Backend artık tam lig adı dönüyor ("English Premier League"). Eski "ENG PR" kısa kodları kaldırıldı; yeni eşleme bayrak + kısa görsel kod (ENG, ESP, ITA, ...) sözlüğü. Bilinmeyen lig için `⚽ + —` fallback.

- **Error boundary (Sprint 8.3):** `app/error.tsx` Next.js convention — React render hatalarında otomatik fallback ("Tekrar dene" butonlu kart). Beyaz ekran yok, kullanıcı kurtarılabilir.

- **Confidence formülü (Sprint 8.4):** `confidence = (pct/100) × volume_weight × market_weight × dual_bonus`. `volume_weight = min(1, ln(matchCount+1) / ln(30))` — 5 maçta 0.50, 30+ maçta 1.0. `market_weight` 1.0 (ana pazarlar) → 0.4 (encok yarı, iy/2y kg kombineleri). `dual_bonus = 1.15` eğer her iki arşivde de ≥%65.

- **`MarketSpec.excludePeriods` (Sprint 8.4):** `confidence.ts` MARKETS tablosunda her pazara `excludePeriods?: Period[]` alanı. IY/2Y'de iddaa açmayan pazarlar (2.5/3.5 A/Ü, taraf 2.5, handikaplar, MS+2.5 kombo) bu listede `["ht", "h2"]` olarak işaretlenir. `isMarketActive` filtreleyerek Top Picks + MarketSummary + DetailedStats üçü birden tutarlı.

- **Combo domain mantığı (Sprint 8.5):** `combos.ts:DOMAIN_OF` 30+ pazarı 14 domain'e gruplar (`match_result`, `total_goals`, `btts`, `home_total`, `away_total`, `iy_ms`, vs.). Bir leg seçilince aynı domain'den ikinci leg yasaklanır → bağımsızlık varsayımı daha sağlam. `HARD_CONFLICTS` ekstra keskin çelişki çiftleri (örn. `result_x` + `fark_ev1`).

- **Joint olasılık yaklaşıklığı (Sprint 8.5/8.7):** `combos.ts` ve `cart.ts` `∏ (pct/100)` ile joint hesaplar (bağımsız olay varsayımı). UI'da `≈` ile yaklaşık olduğu belirtilir. Gerçekte futbol pazarları arasında korelasyon var; ileride profesyonelleştirilebilir (corr matrisi → `Pₐᵦ ≈ Pₐ × Pᵦ × 1.05` gibi).

- **Dinamik eşik formülü (Sprint 8.6):** `dynamicMinPct = max(64, 80 - log10(n+1) × 8)`. Wilson alt sınırının pragmatik yaklaşımı. Küçük örneklemde yanıltıcı yüksek yüzdeyi eler, büyük örneklemde gerçek değerli tahminleri keser. `getTopPicks` artık `{picks, effectiveMinPct, matchCount}` döner — UI başlıkta gösterir.

- **Bahis sepeti localStorage anahtarları:** `nortverse_bet_cart` (Sprint 8.7), `nortverse_detailed_open` (Sprint 8.4). Cross-tab sync için `storage` event + `nortverse-cart-updated` custom event. SSR'da hidrasyon yarış koşulu önlemek için `useCart` `hydrated` flag — boş sepette `BetCart` render bile etmez.

- **MatchContext (Sprint 8.7):** `lib/match-context.tsx` analyze sayfasında match metadata'yı (`matchId`, `homeTeam`, `awayTeam`) paylaşır. Tüm pick component'leri `useMatchInfo()` ile match bilgisini alır → prop drilling yok. `MatchProvider` sadece analyze page'inde sarar, diğer sayfalarda `useMatchInfo()` null döner → "+" butonu görünmez.

- **Trends mimarisi (Sprint 8.8):** `compute_trends(raw)` ham `MatchRawData`'dan 3 blok üretir. `_result_to_row` pipeline path'inde, `_do_analyze` API path'inde DB'ye `trends` JSONB yazar. `_build_from_db` DB'den okur, parse hatası warning + None döner. **Lazy backfill yok** — eski maçlarda `trends` null kalır, frontend sessizce gizler. Yeni gelen maçlar (her run-pipeline veya foreground scrape) trends ile yazılır.

- **Trends migration adımı (Sprint 8.8):** Railway Dockerfile alembic koşturmuyor. Yeni migration eklendiğinde kullanıcı manuel olarak Supabase SQL Editor'den `ALTER TABLE matches ADD COLUMN <kolon> JSONB;` çalıştırmalı. `f5c8d2a1b394` (trends) bu yolla 2026-05-07'de uygulandı.

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

- **Kanonik lig adı (Sprint 8.9):** `LEAGUE_ALIASES` 50+ alias → kanonik ad. `_result_to_row` `canonical_league_name(r.league_code)` uygular → DB hep tutarlı isim yazar. Mevcut karışık isimleri normalize etmek için ayrı CLI yazılmadı (yeni gelenler tutarlı, eskileri organik düzelir).

- **Audit & quality görünürlük (Sprint 8.9):** `/api/health.data_quality.quality_score` 0-100 arası — `total - (non_league/total*40 + missing_pattern/active*20 + missing_actual/active*30 + missing_trends/active*10) * 100`. UptimeRobot'ta görünür; `audit-db` CLI Rich tablo ile detay verir.

---

## Teknoloji Kararları

- **Python 3.11+** / FastAPI / SQLAlchemy 2.x async / Pydantic 2
- **Playwright** (nowgoal Cloudflare/dinamik JS render — BS4 yetersiz)
- **PostgreSQL** (Supabase free tier) — 30K+ maç hedefi için JSONB şart
- **Next.js App Router + TailwindCSS** frontend
- **GitHub Actions** cron (günlük `run-pipeline` + gece `update-scores`)
- **Railway** backend (Docker, `mcr.microsoft.com/playwright/python:v1.47.0-jammy`)
- **Vercel** frontend (Next.js otomatik deploy, `BACKEND_URL` env var gerekli)
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

## Kaldığımız Yer (2026-05-08 — Sprint 8.9 sonu)

Sprint 8.9 deploy edildi (commits `6ab2821`, `72d4ab1`, `2b7274b`). Veri bütünlüğü altyapısı tamamen canlıda.

### ⚠️ Manuel Migration Adımı (Kullanıcı bekliyor)

Railway Dockerfile alembic koşturmuyor. Sprint 8.9 migration `g4d2a7c9b815` Supabase SQL Editor'de manuel uygulanmalı:

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

Migration uygulanana kadar `/api/health` `db_ok: false` döner (`deleted_at` kolonu yok). Uygulandıktan sonra `python -m app.cli.main prune-non-league --apply` ile mevcut kupa maçları temizlenebilir.

### Sıradaki Yapılacaklar (sırayla)

#### 1. Migration uygula + ilk DB temizliği (manuel adım)
- Yukarıdaki SQL'i Supabase'da çalıştır
- `python -m app.cli.main audit-db` — kalite skoru raporu
- `python -m app.cli.main prune-non-league` (dry-run) → kaç kupa maçı var
- Onay ile `--apply` → audit_log'a kayıt düşer
- `python -m app.cli.main self-test 2813084` → E2E doğrulama

#### 2. Frontend Vitest birim testleri
- `frontend/lib/confidence.ts`, `lib/combos.ts`, `lib/cart.ts` saf TS — birim test edilebilir
- Vitest setup gerekir (`npm i -D vitest`)
- Hedef: confidence formülü, çelişki çözümü, kombo üretimi, sepet idempotency

#### 3. Top Picks'e Trend Katkısı (confidence boost)
- Ev formu KG %80'se → kg_var pick'ine küçük bonus (örn. `× 1.05`)
- Üst 2.5 trendi yüksekse → ust_25 pick'ine bonus
- Form mağlubiyet trendi → ev kazanma pick'lerine penaltı
- Implementation: `confidence.ts`'e `trendBoost(pick, trends)` fonksiyonu

#### 4. Sepet Özeti Sticky Rozet
- Sepet kapalıyken sayfa üstünde küçük bilgi: "🧾 3 tahmin · ≈%49 · ≈2.03"
- Mobile'da özellikle değerli (bottom bar şeffaflığı)

#### 5. Migration otomatikleştirme
- Dockerfile CMD'den önce `alembic upgrade head` ekle — manuel SQL adımı kalksın
- Risk: prod migration ilk deploy'da koşar; geri alma planı gerek

#### 6. Trends Backfill (eski maçlar için — opsiyonel)
- Mevcut maçlar bir sonraki `run-pipeline`'da otomatik trend ile yazılır (idempotent upsert)
- Daha hızlı: `backfill-trends` CLI — `raw_data` olmadığı için yeniden scrape gerek → Playwright fırtınası riski; organik dolması yeterli

#### 7. Pattern recompute trigger
- Arşiv her gün büyüyor (`run-pipeline`) → eski maçların pattern eşleşme sayısı zamanla değişir
- Şimdilik: pattern bir kere yazılır, bayatlar ama sorun değil
- İleride: haftalık `recompute-patterns` cron — eski maçların pattern'lerini yeniler

#### 8. Sprint 10 — Canlı Maç & Trend (Uzun vade)
- Anlık skor takibi (devre arası + final)
- WebSocket veya 30sn polling
- Maç sırasında oran değişimi takibi

#### 9. Sprint 11+ — Auth/Premium (Para kazanma yolu) — kullanıcı şu an istemiyor
- NextAuth.js + Google OAuth
- Free vs Premium farkı

### Bilinen Açık Konular
- **Migration manuel adımı:** Railway Dockerfile alembic koşturmuyor (Sprint 8.5'te eklenecek)
- **Storage:** Pattern + trends ~500MB, Supabase free tier sınırına yakın — izlenmeli
- **Joint olasılık bağımsızlık varsayımı:** Combo/sepet `∏ p` — gerçekte korelasyon var; ML correction Sprint 10+
- **Pattern self-check anomalileri:** `audit-db` rapor üretebilir — uygulandığında kontrol edilmeli
- **Veri doğruluğu derin audit:** Excel ile çapraz doğrulama yapılmadı; spot-check geçti

### Önemli Commit Zinciri (Sprint 8.9 oturumu)
- `6ab2821` Sprint 8.9 (1/n): Lig filtresi + Pattern C tam eşleşme — kupa maçları sistemden çıkarıldı
- `72d4ab1` Sprint 8.9 (2/n): Soft delete + audit_log + pre-write validation + kanonik lig adı
- `2b7274b` Sprint 8.9 (3/n): 5 CLI komutu (prune/restore/audit-db/audit-patterns/self-test) + 52 pytest + /api/health quality

### Önceki Oturum (Sprint 8.4-8.8) Commit Zinciri
- `cd49f4e` Sprint 8.4: 3 katman mimari (TopPicks + MarketSummary + DetailedStats), Altın Oranlar kaldırıldı
- `9203b3a` Sprint 8.4: IY/2Y'de iddaa açmayan pazarlar gizlendi (excludePeriods)
- `92d95c9` Sprint 8.5: Akıllı kombinasyon kuponu (combos.ts + ComboSuggestion)
- `13a9db3` Sprint 8.6: Dinamik confidence eşiği (dynamicMinPct)
- `713cf79` Sprint 8.7: Bahis sepeti (cart.ts + BetCart + AddToCartButton + MatchContext)
- `e994468` Sprint 8.8: Form & H2H trendleri (trends.py + matches.trends + TrendsPanel)
