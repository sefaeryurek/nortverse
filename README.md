# Nortverse

Futbol maçı tahmin sistemi. Nowgoal26'dan bülten ve h2h verilerini çekip, istatistiksel analizle tahmin üretir.

## Durum

🚧 Sprint 1 — Scraping + Analiz Motoru (Çekirdek)

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
