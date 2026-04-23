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
│   │   │   ├── connection.py      # SQLAlchemy async engine + get_session()
│   │   │   ├── models.py          # Match + FixtureCache ORM — JSONB kolonlar, actual skorlar
│   │   └── connection.py      # pool_size=2, statement_cache_size=0 (Supabase PgBouncer)
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
│   │   ├── bulten/
│   │   │   └── page.tsx           # Server component — fixture listesi (Suspense)
│   │   ├── sonuclar/
│   │   │   └── page.tsx           # Server component — biten maçlar, skor, tahmin özeti
│   │   └── analyze/[match_id]/
│   │       └── page.tsx           # Client component — maç analiz sayfası
│   ├── components/
│   │   ├── BultenRow.tsx          # Maç satırı (link ?home=&away= param ile)
│   │   ├── DayTabs.tsx            # 8 günlük kayan pencere, basePath prop ile
│   │   ├── IddaaCoupon.tsx        # Arşiv istatistik kartları (Katman B + C)
│   │   ├── ScoreList.tsx          # Katman A 3.5+ skor listesi
│   │   └── Sidebar.tsx            # Sol menü (Bülten + Sonuçlar)
│   ├── lib/
│   │   ├── api.ts                 # Backend API çağrıları (BASE = "" → Next.js proxy)
│   │   └── types.ts               # TypeScript type'ları (PatternResult ~130 alan)
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
- `30 21 * * *` → 00:30 İstanbul → `update-scores` (gece skor güncelleme)
- `0 23 * * *` → 02:00 İstanbul → `update-scores` (geç maçlar)

Ayrıca Railway container'da FastAPI `_score_updater` task her 30 dakikada skorları günceller.

---

## Frontend — IddaaCoupon İstatistik Bölümleri

Her arşiv kartında (Arşiv-1 / Arşiv-2) şu bölümler gösterilir:

| Bölüm | Sekme | Açıklama |
|---|---|---|
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

---

## Mevcut Durum (Sprint 6 — TAMAMLANDI ✅)

### Backend

- ✅ Fixture parser: Hot modunu aktive edip maçları doğru çekiyor
- ✅ Match detail parser: takım, lig kodu, form/H2H parse + gerçek skor
- ✅ Analiz motoru (Katman A): 105 oran hesaplaması
- ✅ Katman B pattern matching: `find_pattern_b_matches`
- ✅ Katman C pattern matching: `find_pattern_c_all_periods` — tek sorgu, tüm periyotlar
- ✅ `build-archive` CLI: lig → geçmiş maç ID → fetch+analiz+upsert
- ✅ FastAPI: 7 endpoint + fixture cache (memory + DB) + bg analiz kuyruğu + DB-first analiz
- ✅ `pattern_stats.py`: ~130 alan, 9 bölüm
- ✅ Railway deployment: `https://nortverse-production.up.railway.app`
- ✅ `fixture_cache` DB tablosu: bülten verileri kalıcı, server restart'tan etkilenmez
- ✅ `/api/results` endpoint: günlük biten maçlar + Katman A kapsamı
- ✅ `update-scores` CLI: biten maçların actual skorlarını DB'ye yazar
- ✅ Otomatik skor güncelleme: FastAPI içinde her 30 dakikada `_score_updater` task
- ✅ Supabase PgBouncer uyumu: `pool_size=2`, `statement_cache_size=0`
- ✅ Date bug düzeltildi: fixture İstanbul tz bazlı, tarih filtresi eklendi

### Frontend

- ✅ Next.js App Router — dark tema, sidebar navigasyon
- ✅ Bülten sayfası: Hot maçlar, saat, lig, 8 günlük kayan takvim
- ✅ Analiz sayfası: Katman A skor listesi + IddaaCoupon (Arşiv-1 ve Arşiv-2)
- ✅ Periyot sekmeleri: İY / 2Y / MS — her biri kendi istatistiklerini gösterir
- ✅ Sonuçlar sayfası (`/sonuclar`): biten maçlar, skor, Katman A/KG/2.5 özet
- ✅ Vercel deployment: `https://nortverse.vercel.app`
- ✅ SSR URL düzeltildi: `BACKEND_URL` env var ile Vercel → Railway direkt

### Henüz Yok

- ❌ Premium/Auth — sonraki fazlar
- ❌ Canlı maç + trend motoru — sonraki fazlar

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

---

## Bilinen Teknik Notlar

- **Timezone:** nowgoal `data-t` attribute **UTC**'dir (Beijing UTC+8 değil). Istanbul = UTC+3. Eski kod +8 ekleyip sonra convert ediyordu → 16 saat ileri hata. `fixture.py`'de `_SITE_TZ = timezone.utc`.

- **Windows Playwright + uvicorn:** uvicorn `loop="auto"` Windows'ta `WindowsSelectorEventLoopPolicy` kullanır, Playwright subprocess açamaz. Çözüm: `cli/main.py`'de `loop="none"` + `api/main.py` modül seviyesinde `WindowsProactorEventLoopPolicy`.

- **Katman C tek sorgu:** `find_pattern_c_all_periods(ft_ratios)` FT oranlarıyla bir kez DB sorgular, aynı eşleşme setinden İY/2Y/MS istatistiklerini hesaplar. Periyot başına ayrı sorgu yapılsaydı İY'de eşleşme bulunup MS'de bulunmama gibi tutarsızlık oluşurdu.

- **DB-first analiz:** `_analyze_and_cache` önce DB kontrol eder. `run-pipeline` çalıştırıldıktan sonra tüm maçlar DB'de olur ve Playwright hiç açılmaz.

- **Typer 0.12.5 + Python 3.11 bug:** `bool` Option'lar string `'False'` dönebilir. `cli/main.py`'de `_flag()` yardımcısı çözüyor.

- **Next.js proxy:** `next.config.ts`'te `/api/*` → `http://localhost:8000/api/*` rewrite var. Frontend'de `BASE = ""` — aynı origin, CORS yok.

- **Supabase PgBouncer:** Transaction mode pooler (port 5432) ile asyncpg kullanırken `pool_size=2, max_overflow=0, connect_args={"statement_cache_size": 0}` zorunlu. Aksi halde GitHub Actions gibi ortamlarda ECIRCUITBREAKER hatası alınır.

- **fixture_cache tablosu:** `/api/fixture` 3 katmanlı cache kullanır: memory (5dk) → DB (geçmiş=kalıcı, bugün=1saat) → Playwright. Yeni migration: `a3f9e2b1c4d5`.

- **Otomatik skor güncelleme:** `api/main.py`'de `_score_updater` async task her 30 dakikada `update_results()` çağırır. Railway container ayakta olduğu sürece çalışır. Ayrıca GitHub Actions'da gece 00:30 ve 02:00 İstanbul'da da çalışır (yedek).

- **Arşive ekleme yapılmıyor:** Mevcut arşiv sabittir, yeni lig/sezon eklenmeyecek. Var olan maçların yüzdeleri değişmesin diye bu karar alındı.

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
