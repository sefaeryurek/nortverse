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
python -m app.cli.main run-pipeline                     # fetch → analiz → Supabase'e kaydet
python -m app.cli.main run-pipeline --date 2026-04-20   # belirli gün için pipeline

# Arşiv oluşturma (Sprint 3)
python -m app.cli.main build-archive --league 36 --season 2024-2025   # ENG PR geçmiş sezon
python -m app.cli.main build-archive --league 36                        # güncel sezon
python -m app.cli.main build-archive --league 36 --season 2024-2025 --season 2023-2024
```

## Git & GitHub — Claude Code için Zorunlu Kurallar

> **Bu kurallar Claude Code'a yöneliktir. Her çalışma seansında eksiksiz uygulanacak.**
> **Hiçbir çalışma sadece local'de kalmamalı. Commit atılmadan ve push yapılmadan seans bitirilmez.**

### Ne Zaman Commit + Push Yapılır

Claude Code çalışırken **aşağıdaki her durumda** commit atıp `git push origin master` ile GitHub'a gönder:

- Bir özellik veya düzeltme çalışır hale geldiğinde → hemen commit + push
- Bir bug giderildiğinde → hemen commit + push
- Sprint tamamlandığında → commit + push
- CLAUDE.md güncellendiğinde → commit + push
- Uzun bir çalışma seansının sonunda → mutlaka commit + push

Sebep: "Yaptığımız çalışmaları ve durumu asla kaybetmeyelim." Her commit GitHub'da kalıcı bir kontrol noktasıdır.

### Remote

```
https://github.com/sefaeryurek/nortverse.git  (branch: master)
```

### Commit Mesajı Formatı — TEMİZ ve AÇIK Olmalı

Commit mesajı, 6 ay sonra bakıldığında ne yapıldığını tek satırda anlatmalı:

```
Sprint X: Ne yapıldı (kısa, Türkçe)

- Değişiklik 1 — neden yapıldı
- Değişiklik 2 — neden yapıldı

Durum: Tamamlandı / Devam ediyor / Test bekleniyor
```

**Kötü mesaj:** `fix`, `update`, `değişiklik`
**İyi mesaj:** `Sprint 3: league.py JSON API ile yeniden yazıldı — HTML scraping çalışmıyordu`

### Git Komutları

```bash
# Değişiklikleri stage'e al ve commit at
git add <dosyalar>
git commit -m "Sprint X: açıklama"

# GitHub'a push et (her commit sonrası)
git push origin master

# Durum kontrolü
git log --oneline -5
git status
```

## Proje Nedir?

**Nortverse**, nowgoal26.com'dan futbol maçı verilerini çekip istatistiksel analiz yapan bir sistem. Son hedef: web uygulaması + premium üyelik. Sahip: Sefa, kod tecrübesi az ama öğrenmeye açık.

Excel'de çalışan mevcut analiz sistemini web tabanlı yapıyoruz. Excel sahibinin önceki yaptığı başka bir projesi bug'lıydı, **sıfırdan ve temiz** başlıyoruz.

## Sistemin Özü

### 3 Katmanlı Analiz

**Katman A — Klasik Skor Hesaplama (TAMAMLANDI)**
```
oran(hg, ag, periyot) = (
    (h2h_ev_periyot[hg] + form_ev_periyot[hg])
    + (h2h_dep_periyot[ag] + form_dep_periyot[ag])
) / 2
```
- 35 skor × 3 periyot (İY/2Y/MS) = 105 hesaplama
- Formül sonucu her zaman 0.5 katı (0, 0.5, 1.0, 1.5, ..., 10.0)
- 3.5+ çıkan skorlar ARŞIV-1'e MS1/MSX/MS2 olarak gruplanır

**Katman B — Pattern Matching (ARŞIV-1)** (henüz yapılmadı)
- Bülten maçının MS1+MSX+MS2 skor setini ARŞIV-1'de tara
- **Tam aynı set'e sahip** geçmiş maçları bul
- En az 5 eşleşme varsa → gerçek sonuçlardan istatistik (KG var %60, 2.5 üst %80 gibi)

**Katman C — Tam Oran Pattern Matching (ARŞIV-2)** (henüz yapılmadı)
- Bülten maçının 105 ham oranını ARŞIV-2'de tara
- 35 skorun ±0.5 aralığında eşleşen maçları bul
- Eşleşen maçların gerçek sonuçlarından istatistik

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

Lig maçı tespit: h2h sayfasındaki her satırın başında lig kısa kodu var (TUR D1, ENG PR, TUR Cup, INT CF). Ana maçın kısa koduyla **birebir eşleşen** satırlar lig maçı.

## Kod Yapısı

```
nortverse/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # ScraperConfig, AnalysisConfig (frozen dataclass)
│   │   ├── models.py              # Pydantic: FixtureMatch, HistoricalMatch, MatchRawData (+actual skorlar), ...
│   │   ├── db/
│   │   │   ├── connection.py      # SQLAlchemy async engine + get_session()
│   │   │   └── models.py          # Match ORM (JSONB Katman A + actual skor alanları)
│   │   ├── scraper/
│   │   │   ├── browser.py         # Playwright wrapper
│   │   │   ├── fixture.py         # Günlük bülten (Hot filtreli)
│   │   │   ├── match_detail.py    # H2H sayfası parse + gerçek skor çıkarımı
│   │   │   └── league.py          # Lig sayfasından maç ID listesi (arşiv için)
│   │   ├── analysis/
│   │   │   ├── scores.py          # ALL_SCORES sabiti, yardımcılar
│   │   │   ├── filtering.py       # check_match_filters
│   │   │   ├── engine.py          # analyze_match (Katman A)
│   │   │   └── pattern_b.py       # find_pattern_b_matches (Katman B, JSONB equality)
│   │   ├── pipeline/
│   │   │   └── runner.py          # run_pipeline: fetch → analiz → upsert
│   │   └── cli/
│   │       └── main.py            # Typer + Rich CLI (fetch-fixture, analyze, build-archive, ...)
│   ├── alembic/                   # DB migration
│   ├── tests/
│   │   └── test_analysis.py       # 8 test (hepsi geçiyor)
│   ├── requirements.txt
│   └── pytest.ini
├── docs/
└── README.md
```

## Önemli Teknik Detaylar

### Nowgoal HTML Yapısı

**Fixture sayfası** (`https://live5.nowgoal26.com/football/fixture`):
- Tarih parametresi: `?f=sc1` (+1 gün), `?f=ft1` (-1 gün)
- Reklam selector: `.closebtn` (açılır açılmaz kapatılmalı)
- Maç satırı: `<tr id="tr1_XXXXXX" class="b2" sclassid="XX" style="...">`
  - `style="display: none;"` → site Hot modunda gizliyor → atla
  - `style=""` → görünür → al
- Lig başlığı: `<tr id="tr_XX" class="Leaguestitle" sclassid="XX">` → `.LGname` içinde ad
- Maç bilgisi: TD içindeki `onclick="soccerInPage.analysis(2784810,"Sassuolo","Como","Italy Serie A")"` regex ile çıkarılır
- Kick-off: `td.time[data-t="2026-4-17 16:30:00"]`

**Hot filtresi**: Site **Show All** modunda açılıyor (`li_ShowAll class="on"`). Maç satırları JavaScript tarafından dinamik olarak `#mintable` div'ine ekleniyor — statik HTML'de `tr1_` satırı yok. Playwright sayfayı açtıktan sonra `#li_FilterHot` butonuna tıklanıyor, 2 sn bekleniyor; JS hot olmayan satırlara `display:none` uyguluyor. Biz sadece görünür kalanları alıyoruz.

**Match detail sayfası** (`/match/h2h-{match_id}`):
- Takım isimleri: `.home` ve `.guest` span'ları
- Tablolar:
  - `#table_v1` class="team-table-home" → ev sahibinin son 20 maçı
  - `#table_v2` class="team-table-guest" → deplasmanın son 20 maçı
  - `#table_v3` class="team-table-other" → H2H
- Maç satırı: `<tr id="tr1_N" index="MATCH_ID">`
  - td[0]: lig kısa kodu (metin) + title attribute (tam ad)
  - td[1]: tarih (`<span data-t="...">`)
  - td[2]: ev takım
  - td[3]: skor `<span class="fscore_1">2-1</span><span class="hscore_1">(1-0)</span>`
  - td[4]: dep takım

Lig kısa kodu ana maçtan alınamaz (sayfa başlığında tam ad var). **Auto-detect**: h2h ve ev maçları tablolarındaki lig kodları sayılır, en çok görülen kupa/friendly olmayan kod ana maçın lig kodudur.

## Mevcut Durum (Sprint 3)

**Çalışan:**
- ✅ Fixture parser: Hot modunu aktive edip maçları doğru çekiyor (43 hot / ~252 toplam)
- ✅ Match detail parser: takım, lig kodu, form/H2H maçları parse + gerçek skor çıkarımı
- ✅ İY/2Y/MS gol dağılımları doğru
- ✅ Analiz motoru (Katman A): 105 oran hesaplaması
- ✅ 3.5+ filtresi → MS1/MSX/MS2 listeleri
- ✅ Kural dışı tespiti (lig/5 maç/h2h 5 maç)
- ✅ CLI: `fetch-fixture`, `analyze`, `analyze-debug`, `fetch-and-analyze`, `run-pipeline`, `build-archive`
- ✅ 8/8 unit test geçiyor
- ✅ Katman B pattern matching: `analyze` komutunda DB eşleşme istatistiği gösterilir
- ✅ `build-archive`: lig sayfasından geçmiş maç ID'leri → analiz → DB (gerçek skor dahil)

**Henüz Yok:**
- ❌ Katman C pattern matching (ARŞIV-2, 105 ham oran ±0.5 eşleşme) — Sprint 4
- ❌ FastAPI REST endpoints — Sprint 4
- ❌ Frontend (Next.js) — Sprint 5
- ❌ Premium/Auth — sonraki fazlar
- ❌ Canlı maç + trend motoru — sonraki fazlar

## Sprint 2 — TAMAMLANDI ✅

- Supabase PostgreSQL (eu-west-1, session pooler port 5432)
- SQLAlchemy 2.x async + asyncpg — `app/db/`
- `matches` tablosu: JSONB sütunlarla Katman A sonuçları + gerçek sonuç alanları
- Alembic migration: `641438be3ff8_initial_schema`
- Pipeline: tek browser, fetch → analiz → upsert (idempotent)
- `run-pipeline` CLI komutu
- İlk çalışma: 43 maçtan 35 kayıt, 8 kural dışı, 0 hata

## Sprint 3 — TAMAMLANDI ✅

- `_extract_main_match_score()`: bitmiş maçların gerçek skorunu h2h sayfasından çıkarır
- `MatchRawData`'ya `actual_ft_home/away`, `actual_ht_home/away` alanları eklendi
- `app/scraper/league.py`: `fetch_league_match_ids(league_id, season, ctx)` — lig sayfasından maç ID listesi
- `app/analysis/pattern_b.py`: `find_pattern_b_matches()` — JSONB equality sorgusu, `PatternBResult` dataclass
- `build-archive` CLI komutu: lig+sezon → tüm maç ID → fetch+analiz+upsert (gerçek skor dahil)
- `analyze` ve `analyze-debug` komutları Katman B panelini gösteriyor

## Bilinen Teknik Notlar

- **Typer 0.12.5 + Python 3.11 bug:** `bool` type annotation'lı Option'lar string `'False'` veya `None` dönebiliyor. `cli/main.py`'de `_flag()` yardımcısı bu sorunu çözüyor. Typer güncellenirse `_flag()` kaldırılabilir.
- **Playwright tarayıcısı:** `browser_context()` context manager ile tek browser açılıp kapanıyor. Pipeline ve `build-archive` bu context'i tüm maçlarda paylaşır (tek seferlik browser).
- **Lig sayfası HTML yapısı:** `football.nowgoal26.com/league/{ID}` sayfası JS-render. `league.py` 4 farklı stratejiyle maç ID çıkarır; hiç bulamazsa debug HTML kaydeder — ID'lerin nasıl gömüldüğünü oradan kontrol et.

## Teknoloji Kararları

- **Python 3.11+** / FastAPI / SQLAlchemy / Pydantic 2
- **Playwright** (BS4 ile JS render yetersiz — Cloudflare/dinamik content)
- **PostgreSQL** (Supabase free tier) — ölçekleme için kritik (30K+ maç hedefi)
- **Next.js 14 + TailwindCSS** frontend
- **GitHub Actions** cron (günlük 1 kez)
- **Typer + Rich** CLI
- Tamamen ücretsiz altyapı

## Çalışma Tarzı

Kullanıcı kod tecrübesinde sınırlı. **Yapılacaklar:**
- Türkçe yorumlar, Türkçe commit mesajları, Türkçe CLI
- Her önemli karar açıklansın
- Mikro-refaktör değil, modüler ve okunabilir kod
- Eski projedeki "1165 satır tek main.py" gibi şeylerden KAÇIN
- Testleri önce yaz/güncel tut
- Kullanıcı komutları kopyala-yapıştır çalıştıracak; PowerShell (Windows 10/11) ortamına dikkat

## Kullanıcıya Sormadan Yapılmayacak Şeyler

- Büyük mimari değişiklikler
- Yeni altyapı seçimleri (DB, framework, vb.)
- Tekonoloji yığınına yeni şey ekleme
- Bağımlılık ekleme (requirements.txt'ye madde ekleme)

## Kullanıcının Verdiği Örnek Maç

Test için: **2813084** (Kayserispor vs Karagumruk, TUR D1, bitmiş maç 1-0). Excel ARSIV-1'deki benzer Kayserispor/Karagumruk maçlarıyla karşılaştırma yapılabilir.

## Excel Dosyası

Kullanıcının Excel'i: `Claude.xlsm` (projeyle birlikte gelmiyor, kullanıcıda). İçinde:
- ARSIV - 1: 3490 satır, 1633 maç analizi + gerçek sonuçlar
- NORT ANALİZ: Pattern matching sonuçları
- BAHİS TABLOSU: Manuel üretilmiş bahis önerileri
