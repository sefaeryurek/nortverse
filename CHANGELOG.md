# Changelog

## Sprint 1.2 — Hot Filtresi + Debug Modu

**Kritik bulgular:**
- Nowgoal sitesi sayfa açılışında "Hot" modunu zaten aktif ediyor (`li_FilterHot class="on"`)
- HTML'de 547 maç var ama 453'ü `style="display: none;"` ile gizli
- Kalan ~94 maç site Hot modunda gösterdikleri
- Önceki `isleatop=1` yaklaşımı yanlıştı, sadece 4 maç döndürüyordu

### Fixture Parser
- ✅ `display: none` olan maç satırları atlanıyor (Hot modu filtresi)
- ✅ `--all` flag'i gizli maçları da getirir (debug için)

### CLI Geliştirmeleri
- ✅ `analyze --ratios` artık 35 skor × 3 periyot = 105 hücrenin hepsini gösteriyor
- ✅ **Yeni komut `analyze-debug`**: Excel karşılaştırması için:
  - Alınan son 5 ev maçı (her birinin İY/2Y/MS gol sayısı)
  - Alınan son 5 dep maçı
  - Alınan son 5 h2h maçı
  - Her takım × her periyot için gol dağılımı (formülün girdileri)
  - 35 skor oranı tablosu

### Dokümantasyon
- ✅ `CLAUDE.md` — Claude Code için proje brifingi

## Sprint 1.1 — Scraper Düzeltildi

### Fixture Parser
- ✅ Takım ve lig bilgisi `onclick="soccerInPage.analysis(...)"` attribute'undan
- ✅ Kick-off zamanı `td.time[data-t]` attribute'undan

### Match Detail Parser
- ✅ Takım isimleri `.home` ve `.guest` class'ından
- ✅ Lig kısa kodu (TUR D1 vs) **otomatik tespit**
- ✅ Her maç satırı: lig kodu, tarih, takımlar, **FT ve HT skorları**
- ✅ Ana maçın lig koduyla eşleşen satırlar → `is_league_match=True`

## Sprint 1.0 — İlk Kurulum

- Proje iskeleti + Analiz motoru + Filtreleme + CLI + 8 test
