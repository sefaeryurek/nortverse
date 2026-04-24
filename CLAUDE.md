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
│   │   ├── bulten/
│   │   │   └── page.tsx           # Server component — fixture listesi (Suspense)
│   │   ├── sonuclar/
│   │   │   └── page.tsx           # Server component — biten maçlar, skor, tahmin özeti
│   │   └── analyze/[match_id]/
│   │       └── page.tsx           # Client component — maç analiz sayfası
│   ├── components/
│   │   ├── BultenRow.tsx          # Maç satırı (link ?home=&away= param ile)
│   │   ├── BultenPrefetcher.tsx   # Bültendeki ilk 3 maçı arka planda prefetch eder
│   │   ├── DayTabs.tsx            # 8 günlük kayan pencere, basePath prop ile
│   │   ├── IddaaCoupon.tsx        # Arşiv istatistik kartları (Katman B + C) + Altın Oranlar
│   │   ├── ScoreList.tsx          # Katman A 3.5+ skor listesi
│   │   ├── Sidebar.tsx            # Sol menü (Bülten + Sonuçlar)
│   │   └── StatBadge.tsx          # Yeniden kullanılabilir yüzde rozeti
│   ├── lib/
│   │   ├── api.ts                 # Backend API çağrıları (BASE = BACKEND_URL ?? "" — SSR'da Railway, CSR'da proxy)
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

## Frontend — IddaaCoupon İstatistik Bölümleri

Her arşiv kartında (Arşiv-1 / Arşiv-2) şu bölümler gösterilir:

| Bölüm | Sekme | Açıklama |
|---|---|---|
| **Altın Oranlar** | Tümü | %79+ olan tüm tahminler, değere göre sıralı — kartın en üstünde |
| Maç Sonucu | Tümü | 1/X/2 + Çifte Şans |
| İlk Yarı / Maç Sonucu | MS only | 9 kombo (1/1, 1/X, ..., 2/2) |
| MS + 2.5 Alt/Üst | Tümü | 6 kombo |
| Hangi Takım Kaç Farkla Kazanır | Tümü | 7 seçenek |
| Handikap | Tümü | 12 hücre (2:0, 1:0, 0:1, 0:2) |
| Taraf Alt/Üst | Tümü | Ev/Dep 0.5/1.5/2.5 + 1Y 0.5 |
| Toplam Gol | Tümü | Gol aralığı + En çok gol yarısı |
| Yarı Alt/Üst | MS only | 1Y 0.5/1.5/2.5 + İki yarı 1.5 |
| Gol Sayısı ve KG | Tümü | Alt/Üst + KG |
| MS + 1.5 / MS + KG | Tümü | 6 kombo |
| Gol (detay) | MS only | 1Y/2Y KG, İY/2Y kombo, Ev/Dep iki yarı |
| Yarı Sonuçları | MS only | İY + 2Y alt istatistikler |
| Skor Sıklığı | Tümü | En sık 10 skor |

**Renk skalası:** %70+ → mavi, %40-70 → turuncu, %40 altı → kırmızı
**Altın Oranlar renk skalası:** %90+ → koyu altın, %79-89 → altın sarı

**Handikap convention:** `Hnd (2:0)` = ev sahibi +2 gol alır (ev güçlü) → `hnd_a20` hesabı kullanılır. `Hnd (0:2)` = deplasman +2 gol alır (dep güçlü) → `hnd_h20` hesabı kullanılır.

---

## Mevcut Durum (Sprint 8 — TAMAMLANDI ✅)

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
- ❌ **BultenPrefetcher kapatıldı (Sprint 7 acil):** Backend'i boğuyordu; bg_worker tek otorite

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

## Kaldığımız Yer (2026-04-25 Cumartesi gece)

Sprint 8 deploy edildi. Sistem stabil ve hızlı. Sıradaki adımlar (sırayla):

### 1. Veri Doğruluğu Auditi (Sıradaki — kullanıcı talep etti)
- 3-5 maçı nowgoal'da yan yana karşılaştır
- Saat, takım ismi, lig, skor zincirini kontrol et
- 5 biten maç → DB'deki actual_ft skorları vs nowgoal sayfası
- Kayserispor test maçı (`2813084`) — Excel ile pattern karşılaştırması
- Excel'in `ARSIV-1` ve `NORT ANALİZ` sheet'leriyle 1-2 maç çapraz doğrulama

### 2. Sprint 9 — Auth/Premium (Para kazanma yolu)
- NextAuth.js + Google OAuth (şifresiz)
- Supabase'de `users` tablosu — üyelik seviyesi (free/premium)
- Free: Bülten + Sonuçlar açık, Analiz kilitli
- Premium: Tüm analiz açık + ileride canlı maç
- İkinci faz: Stripe entegrasyonu (aylık abonelik)

### 3. Sprint 10 — Canlı Maç & Trend (Uzun vade)
- Anlık skor takibi (devre arası + final)
- WebSocket veya 30sn polling
- Maç sırasında oran değişimi takibi

### Bilinen Açık Konular
- **Storage:** Pattern saklama tahminen ~450MB → Supabase free tier 500MB sınırına yakın. İzlenmeli; aşılırsa eski arşiv maçlarının pattern'leri prune edilebilir.
- **Bg worker hız:** ~3-5sn/maç pattern hesabı. 200-300 maçlık bültende 15-25dk sürer. Acil değil ama paralelize edilebilir (3 worker).
- **Veri doğruluğu testi yapılmadı:** Sprint 8 öncesi ve sonrası nowgoal data karşılaştırması atlandı.
- **Yarın 08:00 cron testi:** Eklenen 09:00 yedek cron'un gerçekten çalıştığı yarın görülecek.

### Önemli Commit Zinciri (Son Oturum)
- `194ce94` Sprint 7: CLAUDE.md eksiklikleri düzeltildi
- `3ac8c8a` Sprint 7: /api/health zenginleştirildi
- `2a257f3` Sprint 7: /api/health HEAD desteği (UptimeRobot)
- `e65384d` Sprint 7: Performans (Data Cache, skeleton, prefetch, DayTabs)
- `aed8cfd` Sprint 7 ACİL: Playwright fırtınası durduruldu
- `b1086b9` Sprint 8: Pattern JSONB kolonları
- `ae31800` Sprint 8: compute_all_patterns yardımcısı
- `22cdde6` Sprint 8: run-pipeline pattern yazar
- `7008064` Sprint 8: _build_from_db saklı pattern okur (lazy backfill)
- `7792e56` Sprint 8: 09:00 yedek pipeline cron
