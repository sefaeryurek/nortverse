# Altyapi Audit Raporu (25 Eylul 2026)

## Mevcut Topoloji

```
LOCAL MAKINE (Windows 11)
  |
  +-- Docker (docker-compose.yml)
  |     +-- PostgreSQL 16 Alpine (port 5433)
  |           +-- Database: nortverse
  |           +-- 9,257 aktif mac, quality 100/100
  |
  +-- Backend (Python/FastAPI, native calisir, Docker'da degil)
  |     +-- localhost:8000
  |     +-- Playwright/Chromium web scraping
  |
  +-- Frontend (Next.js, native calisir)
  |     +-- localhost:3000
  |     +-- /api/* → localhost:8000 proxy
  |
  +-- Windows Task Scheduler
        +-- 07:00 backup-db.bat (Sprint 27)
        +-- 08:00 run-pipeline.bat
        +-- 22:00 update-scores.bat
        +-- 00:30 update-scores.bat
```

---

## Docker Kurulumu

**docker-compose.yml** — tek servis (sadece DB):

| Servis | Image | Port | DB | User | Password |
|--------|-------|------|----|------|----------|
| db | postgres:16-alpine | 5433:5432 | nortverse | nortverse | nortverse_local |

Named volume: `pgdata` (kalici veri). Backend/Frontend container'da degil.

---

## GitHub Actions Workflow'lari

### quality.yml (Aktif — her push/PR)
- Backend: ruff check + pytest
- Frontend: vitest + tsc + build
- E2E: sadece workflow_dispatch (manuel)

### daily_pipeline.yml (Sprint 27'de cron devre disi birakildi)
- ~~3 cron: 08:00 pipeline + 22:00/00:30 update-scores~~
- Sadece workflow_dispatch (manuel) kaldi
- `secrets.DATABASE_URL` kullaniyordu (Neon'a isaret ediyordu)

### recompute_patterns.yml (Sprint 27'de cron devre disi birakildi)
- ~~Aylik (her ayin 1'i 03:00)~~
- Sadece workflow_dispatch kaldi

### repair_archive.yml (Zaten sadece manuel)
- workflow_dispatch: repair-archive, normalize-leagues, audit-db

---

## Environment Dosyalari

| Dosya | Amac | Aktif? |
|-------|------|--------|
| `backend/.env` | Local dev — Docker PG localhost:5433 | EVET |
| `backend/.env.neon` | Neon cloud yedek | Sadece yedek |
| `backend/.env.example` | Sablon | Referans |
| `frontend/.env.local` | BACKEND_URL=http://localhost:8000 | EVET |
| `frontend/.env.example` | Sablon | Referans |

---

## Backend Dockerfile

- Base: `mcr.microsoft.com/playwright/python:v1.47.0-noble`
- CMD: `alembic upgrade head` + `uvicorn`
- Cloud deployment icin (Railway) — docker-compose'da kullanilmiyor

---

## Otomasyon Script'leri

| Script | Zamanlama | Islem |
|--------|-----------|-------|
| `scripts/run-pipeline.bat` | 08:00 | Docker kontrol + run-pipeline |
| `scripts/update-scores.bat` | 22:00 + 00:30 | Docker kontrol + update-scores |
| `scripts/backup-db.bat` | 07:00 (Sprint 27) | pg_dump + 7 gun rotasyon |

Tum script'ler Docker otomatik baslama destekli.

---

## Alembic Migration'lar (14 toplam)

1. `641438be3ff8` — Ilk schema
2. `c1b1b4cd333b` — H2 skorlari + kickoff_time
3. `a3f9e2b1c4d5` — Fixture cache
4. `b7e4a2d8c901` — Pattern kolonlari
5. `f5c8d2a1b394` — Trends kolonu
6. `g4d2a7c9b815` — Soft delete + audit log
7. `h8c91e7a2b04` — Pattern computed_at
8. `i3b76d4e9a10` — Skipped analysis cache
9. `j4e8c1d7f920` — Analysis snapshots
10. `k5f8c4b2a613` — Score snapshots
11. `m7a1d9e4c256` — Prediction chronology
12. `n8b2e5f7a341` — Score snapshot chronology check
13. `p9c3f6a8d452` — V3 validation foundation
14. `q1d4a7b9e563` — Backfill result observations

---

## Deployment Konfigurasyonu

| Platform | Dosya | Durum |
|----------|-------|-------|
| Railway | `backend/railway.json` | Mevcut ama muhtemelen aktif degil |
| Vercel | yok (vercel.json yok) | Onceden vardi, simdi belirsiz |
| Render | yok (render.yaml yok) | Onceden vardi, simdi belirsiz |

---

## Kritik Endiseler

1. **Yedekleme stratejisi yoktu** — Sprint 27'de `backup-db.bat` eklendi
2. **GitHub Actions cron'lari local DB'ye erisilemiyordu** — Sprint 27'de devre disi birakildi
3. **Neon credentials git'te** — `.env.neon` .gitignore'da (Sprint 25'te eklenmis)
4. **Production deployment belirsiz** — Render/Vercel onceden vardi, simdi local
5. **Dual otomasyon riski** — Task Scheduler + GitHub Actions ayni isleri yapiyordu → cozuldu (cron kapatildi)
