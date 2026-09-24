# Backend Audit Raporu (25 Eylul 2026)

## API Endpoints (11 toplam)

### Fixture Router (`routes_fixture.py`)
| Method | Path | Aciklama |
|--------|------|----------|
| GET | `/api/fixture` | Gunluk bulten. 3 katmanli cache (memory 10dk, DB, Playwright fallback). `?date=YYYY-MM-DD` destekli. |

### Analysis Router (`routes_analysis.py`)
| Method | Path | Aciklama |
|--------|------|----------|
| GET | `/api/analyze/{match_id}` | Mac analizi. Cache'den veya Playwright ile. 90sn timeout. |
| POST | `/api/analyze/{match_id}` | Zorla yeniden scrape, cache bypass. |
| GET | `/api/match/{match_id}` | Mac ozeti (takimlar, skorlar, FT skor listeleri). DB miss → Playwright fallback. |

### Results Router (`routes_results.py`)
| Method | Path | Aciklama |
|--------|------|----------|
| GET | `/api/matches` | Analiz edilen maclar. `?league=` ve `?limit=` (1-200, default 50). |
| GET | `/api/results` | Gunun bitmis maclari + turetilmis alanlar (sonuc, KG, ust 2.5). |

### Admin Router (`routes_admin.py`)
| Method | Path | Aciklama |
|--------|------|----------|
| GET/HEAD | `/api/health` | UptimeRobot saglik kontrolu. DB durumu, son pipeline, queue, cache. |
| GET | `/api/analysis-evidence` | Kapsam istatistikleri: analiz edilen maclar, pattern degerlendirme sayilari. |
| GET | `/api/analysis-validation` | V3 pazar dogrulama (model vs baseline isabet oranlari, Brier skorlari). |
| GET | `/api/score-validation` | Skor listesi dogrulama (baseline karsilastirma). |
| GET | `/api/admin/quality` | Veri kalitesi raporu (quality score 0-100). |
| GET | `/api/correlations` | Poisson korelasyon faktorleri (statik, cache'li). |

Hicbir endpoint'te authentication yok. CORS: `allow_origins=["*"]`.

---

## CLI Komutlari (22 toplam)

### Pipeline / Analiz (10)
- `analyze <match_id>` — Tek mac analizi
- `analyze-debug <match_id>` — Excel karsilastirma icin debug cikti
- `fetch-fixture` — Gunluk bulten cek
- `fetch-and-analyze` — Cek + analiz et
- `run-pipeline` — Tam pipeline: fetch → analiz → DB kayit
- `capture-score-snapshots` — Kickoff oncesi FT skor snapshot'i
- `capture-recommendations` — V3 oneri snapshot'lari
- `refresh-fixture-cache` — Fixture cache yenile
- `update-scores` — Bitmis maclarin skorlarini guncelle
- `serve` — FastAPI sunucusu baslat

### Arsiv / Onarim (5)
- `build-archive` — Tek lig arsivi olustur
- `build-multi-archive` — Birden fazla lig arsivi
- `list-leagues` — Bilinen ligleri listele
- `repair-archive` — Arsiv verisi onar
- `normalize-leagues` — Lig adi varyantlarini normalize et

### Audit / Bakim (6)
- `prune-non-league` — Kupa maclarini sil
- `restore-deleted` — Soft-deleted maci geri al
- `audit-db` — DB butunluk auditi
- `audit-patterns` — Pattern veri auditi
- `recompute-patterns` — Tum pattern B/C yeniden hesapla
- `self-test` — Sistem oz-testi

### Diger
- `version` — Surum bilgisi

---

## DB Tablolari (8)

| Tablo | Aciklama |
|-------|----------|
| `matches` | Ana tablo. Mac metadata, skor dagilimlari (JSONB), pattern B/C (JSONB), trend (JSONB), soft-delete. |
| `audit_log` | Degismez log (prune/delete/restore/recompute islemleri). |
| `fixture_cache` | Gunluk bulten cache (tarih PK, JSONB mac listesi). |
| `skipped_analysis` | Reddedilen maclar (tekrar scrape onleme). |
| `analysis_snapshots` | Donmus kickoff oncesi FT secimler (kural versiyonu bazli). |
| `analysis_snapshot_markets` | Normalize pazar bazli model/baseline kararlari. |
| `match_final_result_observations` | Degismez final skor gozlem audit trail'i. |
| `score_snapshots` | Donmus kickoff oncesi skor listeleri (baseline karsilastirmali). |

User tablosu, auth tablolari YOK.

---

## Bagimliliklar (requirements.txt)

| Kategori | Paketler |
|----------|----------|
| Web scraping | playwright 1.47.0, beautifulsoup4 4.15.0, lxml 5.3.0, httpx 0.27.2 |
| CLI | typer 0.25.1, rich 13.9.2 |
| Data | pydantic 2.9.2 |
| Database | sqlalchemy 2.0.36, alembic 1.13.3, asyncpg 0.29.0, psycopg2-binary 2.9.9 |
| API | fastapi 0.115.12, uvicorn 0.34.2 |
| Dev | pytest 8.3.3, pytest-asyncio 0.24.0, ruff 0.6.9 |

Auth kutuphanesi (JWT, passlib, bcrypt), odeme (Stripe), WebSocket, email, rate limiting YOK.

---

## Eksik Ozellikler

| Ozellik | Durum |
|---------|-------|
| Authentication | Tamamen yok |
| Kullanici yonetimi | User modeli yok |
| Yetkilendirme / RBAC | Rol sistemi yok |
| Premium / Abonelik | Katman/paywall yok |
| Odeme | Stripe/Iyzico yok |
| WebSocket / SSE | Yok (HTTP polling var) |
| Rate limiting | Yok |
| API key | Yok |
| Email / bildirim | Yok |
| API versiyonlama | Yok |

## Iyi Yapilanmis Alanlar

- Analiz pipeline'i olgun (pattern B/C, trend, dogrulama)
- Veri butunlugu saglam (soft delete, audit log, degismez gozlem defteri, yazma oncesi dogrulama, retry)
- Cache cok katmanli (memory LRU+TTL, DB cache, Playwright fallback)
- Dogrulama sistemi gelismis (donmus snapshot'lar, model vs baseline karsilastirma, Wilson CI, Brier skor)
