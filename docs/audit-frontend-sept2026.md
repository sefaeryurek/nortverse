# Frontend Audit Raporu (25 Eylul 2026)

## Sayfalar / Rotalar

| Rota | Dosya | Aciklama |
|------|-------|----------|
| `/` | `app/page.tsx` | `/bulten`'e redirect |
| `/bulten` | `app/bulten/page.tsx` | Gunluk bulten — mac listesi, tarih gezinme, canli skor overlay, 45sn auto-refresh |
| `/sonuclar` | `app/sonuclar/page.tsx` | Sonuclar — bitmis maclar, FT+HT skor, metin arama, tarih gezinme |
| `/analyze/[match_id]` | `app/analyze/[match_id]/page.tsx` | Mac analizi — skor dagilimi, periyot sekmeleri, trend, pazar ozeti, kombo, detayli istatistik |

Layout: Dark tema (#0f1117), Turkce (lang="tr"), Sidebar + BetCart her sayfada.

---

## Component'ler (16 toplam)

| Component | Aciklama |
|-----------|----------|
| `Sidebar` | Responsive navigasyon. Desktop: 264px sidebar. Mobile: ust header bar. |
| `BetCart` | Floating bahis sepeti. Desktop: sag alt buton. Mobile: sticky alt bar. |
| `AddToCartButton` | "+"/checkmark toggle — tek tahmin ekle/cikar |
| `BultenRow` | Bulten mac satiri — saat, lig bayragi, takimlar, canli skor |
| `LiveMatchBadge` | Canli skor badge + dakika gostergesi. 15sn staleness kontrolu. |
| `AutoRefresh` | Gorunmez polling — 45sn'de router.refresh(), visibility/focus tetik |
| `DayTabs` | Yatay tarih sekmeleri (8 gun) |
| `RetryButton` | Hata durumunda "Tekrar Dene" butonu |
| `IddaaCoupon` | Analiz gorunumu container — TopPicks, MarketSummary, DetailedStats |
| `TopPicks` | Onerilen bahisler (confidence sirali, v3) |
| `MarketSummary` | Ana pazarlar ozeti (Arsiv 1 vs 2 yan yana) |
| `ComboSuggestion` | 3 hazir kombo karti (cift/uclu/super) |
| `DetailedStats` | ~130 pazar yuzdeleri (accordion, localStorage state) |
| `TrendsPanel` | Ev/Dep form + H2H trend kartlari |
| `ScoreList` | Skor chip'leri (1-0, 2-1 vb.) sonuc tipine gore gruplu |
| `StatBadge` | Renk kodlu yuzde rozeti |

---

## API Client (api.ts)

| Fonksiyon | Endpoint | Cache | Aciklama |
|-----------|----------|-------|----------|
| `getFixture(date)` | GET /api/fixture | 15sn/300sn | Gunluk bulten |
| `getResults(date)` | GET /api/results | 15sn/300sn | Bitmis mac sonuclari |
| `analyzeMatch(matchId)` | GET /api/analyze/:id | no-store | Tam mac analizi |
| `getAnalysisEvidence()` | GET /api/analysis-evidence | 300sn | Arsiv degerlendirme kapsam |
| `getAnalysisValidation()` | GET /api/analysis-validation | 300sn | V3 model dogrulama |
| `getScoreValidation()` | GET /api/score-validation | 300sn | Skor listesi dogrulama |
| `getMatches(league?, limit)` | GET /api/matches | no-store | Mac ozetleri (UI'da kullanilmiyor) |

---

## Teknoloji Stack

- **Next.js 16.2.4** (cutting-edge, AGENTS.md uyarisi var)
- **React 19.2.4**
- **Tailwind CSS v4**
- **TypeScript 5**
- **Vitest 4.1.6** + Testing Library + Playwright (E2E)
- UI kutuphanesi yok (tamamen custom)
- State yonetimi yok (localStorage + useSyncExternalStore)
- Auth kutuphanesi yok
- Chart/grafik kutuphanesi yok
- i18n kutuphanesi yok (Turkce hardcoded)

---

## AGENTS.md Uyarisi

> "This is NOT the Next.js you know. This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code."

Next.js 16'da `params` ve `searchParams` **Promise-based**. Frontend kodu degistirmeden once mutlaka `node_modules/next/dist/docs/` okunmali.

---

## Eksik Ozellikler

1. **Authentication / Kullanici Hesaplari** — login, kayit, OAuth, JWT yok
2. **Premium / Abonelik / Paywall** — monetizasyon katmani yok
3. **Kullanici Profili / Tercihler** — watchlist, favori takimlar yok
4. **Gercek Zamanli Guncellemeler** — 45sn polling var, WebSocket/SSE yok
5. **Push Bildirimler** — service worker, web push yok
6. **Mac Gecmisi / Kullanici Analitiyi** — isabet orani takibi yok
7. **Grafik / Gorsellestirme** — chart kutuphanesi yok, her sey metin/sayi
8. **Lig / Turnuva Sayfalari** — puan tablosu, lig filtreleme yok
9. **Coklu Dil** — Turkce hardcoded, i18n yok
10. **Error / 404 Sayfalari** — custom not-found.tsx yok
11. **SEO / Meta Tags** — Open Graph, Twitter cards, structured data yok

## Test Durumu

- 241 vitest birim test (yesil)
- 28 Playwright E2E test (yapi dogrulanmis)
