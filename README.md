# Nortverse

Futbol maçı tahmin sistemi. Nowgoal26'dan bülten ve h2h verilerini çekip, istatistiksel analizle tahmin üretir.

## Durum

FastAPI backend, Next.js frontend, PostgreSQL arşivi ve analiz pipeline'ı bulunur.
Son kod incelemesi ve doğrulama sınırları: [Denetim raporu](DENETIM_RAPORU.md).

## Gereksinimler

- Python 3.11+
- Windows / macOS / Linux

## Kurulum

```bash
# Virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Bağımlılıklar
cd backend
pip install -r requirements.txt

# Playwright tarayıcı indir
playwright install chromium
```

## Kullanım

Web arayüzü için backend dizininde `.env` dosyasına `DATABASE_URL` tanımlayın
(`postgresql+asyncpg://kullanici:parola@localhost:5432/nortverse`), ardından
`alembic upgrade head` ve `python -m app.cli.main serve` çalıştırın.
Başka bir terminalde `frontend` dizininde `npm ci` ve `npm run dev` çalıştırın.
Yerel API varsayılanı `http://localhost:8000`; farklı hedef için frontend'de
`BACKEND_URL` kullanılabilir.

Kontroller: backend'de `python -m pytest -q` ve `python -m ruff check app/ tests/`;
frontend'de `npm run test:run`, `npm run lint`, `npx tsc --noEmit`, `npm run build`.

```bash
cd backend

# Tek bir maçı analiz et
python -m app.cli.main analyze 2813084

# Tam detay (Excel karşılaştırma için) — dosyaya kaydet
python -m app.cli.main analyze-debug 2813084 --save

# Günlük bülteni çek
python -m app.cli.main fetch-fixture

# Bülten + tüm maçları toplu analiz et, sonuçları dosyaya kaydet
python -m app.cli.main fetch-and-analyze --save
```

Detaylı kullanım için **[KULLANIM.md](KULLANIM.md)** dosyasına bakın.

`--save` flag kullanıldığında çıktılar `backend/debug/` klasörüne `.txt` ve `.json`
olarak kaydedilir. GitHub'a push edilebilir ve oradan incelenebilir.

## Proje Yapısı

```
nortverse/
├── backend/
│   ├── app/
│   │   ├── scraper/        # Nowgoal scraping
│   │   ├── analysis/       # Analiz motoru
│   │   ├── cli/            # Komut satırı arayüzü
│   │   ├── models.py       # Veri tipleri
│   │   └── config.py       # Ayarlar
│   ├── tests/
│   └── requirements.txt
├── docs/
│   └── mimari.md           # Mimari dokümanı
└── README.md
```

## Lisans

Private — kişisel kullanım.
