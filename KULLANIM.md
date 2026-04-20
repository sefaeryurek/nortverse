# Nortverse — Kullanım Kılavuzu

Bu doküman projeyi GitHub'dan indirip yerelde çalıştırmak için adım adım rehberdir.

---

## 1. GitHub'dan İndirme

### Seçenek A: Git clone (önerilen)

```bash
git clone https://github.com/sefaeryurek/nortverse.git
cd nortverse
git checkout claude/share-files-chat-jOfdx
```

### Seçenek B: ZIP olarak indir

1. GitHub sayfasında branch seçiminden **`claude/share-files-chat-jOfdx`** dalını seç
2. Sağ üstte **Code → Download ZIP** tıkla
3. ZIP'i çıkart

---

## 2. Kurulum

### Gereksinimler
- Python 3.11 veya üstü
- Windows / macOS / Linux

### Adımlar

```bash
# 1. Virtual environment oluştur
python -m venv .venv

# 2. Aktif et
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 3. Bağımlılıklar
cd backend
pip install -r requirements.txt

# 4. Playwright tarayıcısını indir (ilk kurulumda zorunlu)
playwright install chromium
```

---

## 3. CLI Komutları

Tüm komutlar `backend/` dizininden çalıştırılır.

### 3.1. `analyze` — Tek Maç Analizi

Bir maç ID'sinin 3 periyot × 35 skor analizini yapar.

```bash
python -m app.cli.main analyze 2813084
python -m app.cli.main analyze 2813084 --ratios      # Tüm 105 hücre
python -m app.cli.main analyze 2813084 --save        # debug/ klasörüne kaydet
python -m app.cli.main analyze 2813084 --n 10        # Son 10 maç
python -m app.cli.main analyze 2813084 --threshold 4 # Eşiği 4.0
```

### 3.2. `analyze-debug` — Tam Detay (Excel karşılaştırma için)

Filtreleme geçmese bile çalışır. Ham maçlar + gol dağılımları + 105 oran.

```bash
python -m app.cli.main analyze-debug 2813084
python -m app.cli.main analyze-debug 2813084 --save  # ÖNEMLİ: dosyaya kaydet
```

### 3.3. `fetch-fixture` — Bülten Çekme

```bash
python -m app.cli.main fetch-fixture                      # Bugün, Hot modu
python -m app.cli.main fetch-fixture --date 2026-04-21    # Belirli tarih
python -m app.cli.main fetch-fixture --all                # Gizli maçlar dahil
python -m app.cli.main fetch-fixture --save               # Dosyaya kaydet
```

### 3.4. `fetch-and-analyze` — Toplu Pipeline

Bültendeki Hot maçların hepsini çeker ve analiz eder.

```bash
python -m app.cli.main fetch-and-analyze                  # Hepsi
python -m app.cli.main fetch-and-analyze --limit 5        # İlk 5 maç
python -m app.cli.main fetch-and-analyze --save           # Dosyaya kaydet
python -m app.cli.main fetch-and-analyze --date 2026-04-21 --save
```

---

## 4. `--save` Flag Nasıl Çalışır?

Tüm komutlara `--save` eklenince iki dosya oluşur:

| Dosya | Format | Ne İçerir? |
|-------|--------|------------|
| `*.txt` | Düz metin | Terminal çıktısının aynısı (renksiz) |
| `*.json` | JSON | Yapılandırılmış veri (oranlar, skorlar) |

### Dosya İsimlendirmesi

```
backend/debug/
├── analyze_2813084_20260420_193022.txt
├── analyze_2813084_20260420_193022.json
├── debug_2813084_20260420_193045.txt
├── debug_2813084_20260420_193045.json
├── fixture_20260420_193110.txt
├── fixture_20260420_193110.json
├── batch_20260420_193200.txt
└── batch_20260420_193200.json
```

Format: `{komut}_{idOrDate}_{YYYYMMDD}_{HHMMSS}.{uzantı}`

---

## 5. GitHub'a Dosya Yükleme (Debug Paylaşımı)

Debug dosyalarınızı Claude'un inceleyebilmesi için GitHub'a push edin:

```bash
# Debug dosyalarını ekle
git add backend/debug/

# Commit (Türkçe mesajla)
git commit -m "debug: 2813084 analiz cikitilari eklendi"

# Push
git push origin claude/share-files-chat-jOfdx
```

Sonra GitHub arayüzünde `backend/debug/` klasöründen dosyaları görüntüleyebilirsiniz. `.txt` dosyası direkt tarayıcıda açılır, `.json` dosyası da yapılandırılmış halde görüntülenir.

---

## 6. Tipik Kullanım Akışı

### Senaryo: Excel ile karşılaştırma

```bash
cd backend

# 1. Tek maç için tüm detayları dosyaya al
python -m app.cli.main analyze-debug 2813084 --save

# 2. Dosyaları GitHub'a gönder
cd ..
git add backend/debug/
git commit -m "debug: 2813084 Excel karsilastirma"
git push
```

Claude dosyaları GitHub'dan okuyup Excel değerleriyle karşılaştırabilir.

### Senaryo: Günlük bülten analizi

```bash
cd backend

# Tüm maçları toplu analiz et ve kaydet
python -m app.cli.main fetch-and-analyze --save

# Gönder
cd ..
git add backend/debug/
git commit -m "debug: gunluk bulten analizi"
git push
```

---

## 7. Test Çalıştırma

```bash
cd backend
pytest -v
```

8 test bulunmalı ve hepsi geçmeli.

---

## 8. Proje Dosya Yapısı

```
nortverse/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Ayarlar
│   │   ├── models.py              # Pydantic veri tipleri
│   │   ├── scraper/
│   │   │   ├── browser.py         # Playwright wrapper
│   │   │   ├── fixture.py         # Bülten scraper
│   │   │   └── match_detail.py    # H2H sayfası scraper
│   │   ├── analysis/
│   │   │   ├── scores.py          # 35 skor sabiti
│   │   │   ├── filtering.py       # Kural dışı filtreleme
│   │   │   └── engine.py          # Analiz motoru (Katman A)
│   │   └── cli/
│   │       └── main.py            # Typer CLI — --save flag burada
│   ├── debug/                     # --save çıktıları buraya gelir
│   ├── tests/
│   │   └── test_analysis.py       # 8 unit test
│   ├── requirements.txt
│   └── pytest.ini
├── docs/
├── CLAUDE.md                      # Claude Code için proje brifingi
├── CHANGELOG.md
├── README.md
└── KULLANIM.md                    # Bu dosya
```

---

## 9. Sık Karşılaşılan Sorunlar

### "playwright: command not found"
`playwright install chromium` çalıştırmadan önce virtual environment aktif olmalı.

### "ModuleNotFoundError: No module named 'app'"
Komutu `backend/` dizininden çalıştırdığınızdan emin olun.

### Cloudflare / Timeout
Site bazen yavaş yanıt veriyor. `backend/app/config.py` içindeki `page_timeout` ve `default_wait` değerlerini arttırabilirsiniz.

### Windows encoding hatası
Emojileri ve özel karakterleri ASCII'ye dönüştürdük (commit `2511a86`). Sorun devam ediyorsa `chcp 65001` ile terminal kodlamasını UTF-8'e ayarlayın.

---

## 10. Test Maçları

Geliştirme ve test için önerilen maç ID'leri:

| ID | Açıklama |
|----|----------|
| `2813084` | Kayserispor vs Karagumruk (TUR D1) — bitmiş, Excel örneği |

---

## Ek Bilgi

- **Branch**: `claude/share-files-chat-jOfdx`
- **Proje kök**: `sefaeryurek/nortverse`
- **Python**: 3.11+
- **Lisans**: Private (kişisel kullanım)
