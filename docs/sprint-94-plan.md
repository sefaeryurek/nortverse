# Sprint 94 Planı — 11 ajanlı tam denetim (28 Ekim 2026)

Bu belge 28 Ekim 2026'da 11 ayrı denetim ajanının bulgularını tek plana toplar. Ajanlar repoyu, veritabanını, logları, zamanlanmış görevleri, canlı API'yi ve oran kaynağını **sadece okuyarak** inceledi; hiçbir dosya, tablo veya görev değiştirilmedi. Her ajanın ayrıntılı notları `docs/audit-2026-10-28/` klasöründe (01–11).

| # | Alan | Not dosyası |
|---|---|---|
| 1 | Backend kodu | `01-backend.md` |
| 2 | Güvenlik ve paylaşım | `02-security.md` |
| 3 | Veritabanı bütünlüğü | `03-data.md` |
| 4 | Stratejilerin gerçek performansı | `04-strategy.md` |
| 5 | Bahis oranlarına karşı değer | `05-odds.md` |
| 6 | Frontend | `06-frontend.md` |
| 7 | Test, CI, kod kalitesi | `07-tests.md` |
| 8 | Operasyon ve altyapı | `08-ops.md` |
| 9 | Anlık maçlar (inplay-v1) araştırması | `09-inplay.md` |
| 10 | Kupondaş, İY panosu, oran kazıyıcı | `10-coupons.md` |
| 11 | Kazıyıcılar, pipeline, lig kapsamı | `11-scraper.md` |

**Önem dereceleri:** Kritik (hemen, veri/güvenlik kaybı) · Yüksek (bu sprint) · Orta (sonraki) · Düşük (fırsat oldukça).
**Efor:** S (birkaç saat) · M (1 gün) · L (birkaç gün) · XL (hafta+).
**Kurallar bu planda da geçerli:** her adım ayrı commit + push; kural değişirse sürüm artar ve önce gölgede çalışır; 100 tekil karardan önce hüküm yok; bağımlılık/altyapı/büyük mimari değişiklik kullanıcı onayı ister.

---

## 1. Tek sayfalık özet

**İyi haberler (doğrulandı):**
- Testler yeşil: 1127 backend, 313 frontend; lint ve tip kontrolü temiz. Testler gerçek DB'ye veya internete hiç bağlanmıyor (bağlantı yakalayan eklentiyle doğrulandı).
- Tahmin defterindeki **5.155 sonuçlanmış kararın tamamı** skordan bağımsız olarak yeniden hesaplandı → **0 hata**.
- Kupon sonuç hesabı (`leg_return`) **87.465 senaryoda 0 hata** (Asya çeyrek/tam çizgi dahil).
- Gol dakikası verisi kusursuz (590 maçta goller = skor, İY golleri = İY skoru).
- Ekrandaki model kuralları (canlı Poisson, maç öncesi v5, live-2h) geçmiş test (backtest) aralıklarının **içinde** çalışıyor; sızıntı izi yok.

**En önemli sorunlar:**
1. **Kupondaş'ta kesin kazanan kupon yazılabiliyor (Kritik).** İlk yarı bitmiş maçta İY seçenekleri açık kalıyor (Sassuolo–Lazio 60. dk: "İY 2 @2,50" seçilebildi, İY 2-4 bitmişti); maç içinde çifte şans hiç güncellenmiyor (Lazio 2 farkla öndeyken X2 @1,29); golden sonraki 15 sn içinde gol öncesi oran kilitlenebiliyor.
2. **Veritabanı yerel ağa açık (Kritik).** Port 5433 tüm ağ arayüzlerinde dinliyor, şifresi herkese açık GitHub reposunda, kullanıcı süper kullanıcı, güvenlik duvarı Docker'a izin veriyor. Aynı Wi-Fi'daki herkes bağlanıp her şeyi okuyup silebilir.
3. **Bilgisayar elle uyutuluyor (Kritik).** Her gece ve bazen maç saatlerinde. Sonuç: 19–27 Ekim arasında 59 devre arası maçının 8'i kaydedilmedi; sabah analizi 14 günde bir kez bile 08:00'de çalışmadı; arşiv işi ve backend uyku anında öldü.
4. **Paylaşım henüz güvenli değil (Yüksek).** Next.js 16.2.4'te giriş kontrolünü atlatan bilinen açıklar var; sunucu tarafı çizim her isteğe yönetici yetkisi veriyor; adres başlığı taklit edilerek giriş kilidi atlanıyor veya sahibi kilitleniyor; giriş sonrası yönlendirme başka siteye çevrilebiliyor; site geliştirme modunda çalışıyor.
5. **Skor güncelleme bir gün takılınca tüm çalışma düşüyor (Yüksek).** O gece ne tahminler ne kuponlar sonuçlanıyor.
6. **Ertelenen/iptal maçlar hiç sonuçlanmıyor, ertelenen maçın eski tahmini geçerli sayılıyor (Yüksek).**
7. **Kural sürümü disiplininde boşluklar (Yüksek).** Arşiv tamamlama, canlı kararların dayandığı COND tablosunu sürüm artmadan değiştirdi; 4 kuralın parmak izi bağlı olduğu modeli içermiyor; eski canlı modelde 17 kayıt ~97. dakikada donduruldu ve geçerli sayılıyor.
8. **Ana Pazar Özeti beklentinin altında (Yüksek, ekranda).** 1.460 kararda gösterilen ort. %54,5, gerçek %48,1. Gösterilen sayı aslında arşiv sıklığı, ama olasılık gibi sunuluyor.
9. **Hiçbir modelde bahis oranına karşı değer yok (bilgi).** Piyasa maç öncesinde modelden belirgin şekilde iyi; v5 seçimleri kapanış oranıyla ≈ −%2,6; canlı %90+ işaretlerin oranı 1,02–1,15 (başa baş civarı). Model kararlarının ~%89'u zaten ilk yarı skorunun söylediği şey.
10. **Kapsam çok dar.** Bültenin %1,7'si ana lig, %1,1'i gölge lig; kupona eklenebilen maç bültenin %0,6–0,8'i; bültenin %24'ünün lig adı bir kazıma hatası yüzünden "?" ve pipeline'a hiç girmiyor.

---

## 2. Senden karar bekleyen sorular

Kod yazılmadan önce cevaplanması gerekenler. Önerim her satırda; karar senin.

| # | Soru | Seçenekler | Önerim |
|---|---|---|---|
| K1 | Arkadaşın hesabı yönetici mi olsun? | a) yönetici (eski kararın) · b) normal kullanıcı | **b** — yönetici her bilinmeyen maç ID'si için tarayıcı açtırabiliyor; normal kullanıcı her şeyi görür ama kazıma tetikleyemez. Sunucu tarafı yetki düzeltmesi (A3) yapılmazsa fark kalmaz. |
| K2 | Kupondaş canlı (maç içi) kupon kabul etsin mi? | a) sadece maç öncesi · b) canlı da, 8 sn gecikme + skor eşleşmesi + taze satır şartıyla | **a** şimdilik; canlı oran kaynağı güvenilmez (İY ve ÇŞ maç içinde güncellenmiyor). |
| K3 | Kupondaş'ta aynı maçtan birden fazla seçim? | a) maç başına tek seçim (iddaa gibi) · b) serbest · c) izin listesi (İY + MS Ü/A gibi) | **a** — yoksa MS 1 + ÇŞ 1X gibi aynı olay oranı şişirir. |
| K4 | Kupondaş'a tüm bülten (kupa maçları dahil) açılsın mı? | a) sadece analizli ana+gölge (bugün) · b) bülten tabanlı bacak (analizsiz maçlar da) | **b** (bkz. J6) — bugün bültenin %0,6'sı seçilebiliyor. |
| K5 | Next.js 16.2.4 → 16.4.x güncellemesi | onay / ret | **Onay** — kritik güvenlik açıkları; paylaşımdan önce şart. |
| K6 | FastAPI/Starlette güncellemesi | onay / ertele | Ertele (düşük-orta risk; paylaşım sonrası). |
| K7 | Ana Pazar Özeti ne olsun? | a) "arşiv sıklığı" diye yeniden etiketle + yeşil/çubuk kaldır · b) en kötü pazarları (fark, İY/MS, MS+2.5) soluk "bilgi amaçlı" · c) varsayılan kapalı akordeon · d) `market-summary-v3` (v5 olasılığı) gölgede dene · e) gizle | **a + b + c** hemen, **d** gölgede. |
| K8 | Hatalı kayıtların geçersiz sayılması | 3026759 Trabzon–Beşiktaş (50 kayıt, 48 saat kuralı ihlali) · 3003600 Kortrijk–Mechelen (38, ertelendi) · live-ms-v1 geç dondurulan 17 kayıt | Üçü de **geçersiz** (silinmez, `invalidated` çözümü). |
| K9 | COND zaman penceresi + yeni sürümler | `live-arch-v2.1`, `live-2h-v1.1`, `live-poisson-v1.2`, `ht-display-v1.1` gölgede | **Onay** — aksi halde arşiv büyüdükçe kararlar sessizce kayıyor. |
| K10 | Eski canlı model live-ms-v1 kaydı | a) durdur · b) pencereye bağlayıp `live-ms-v1.1` olarak sürdür | **a** — bilgi katmıyor (tabana göre −2,7). |
| K11 | Maç sonu oran geçmişi doldurma (~2.100 maç, 5–6 saat) + her gün otomatik oran kaydı | onay / ret | **Onay** — arşiv + gol çekimi bitince. |
| K12 | Dış servisler | healthchecks.io veya ntfy.sh (telefona uyarı) · OneDrive/Google Drive (şifreli haftalık yedek, 7-Zip kurulumu) | İkisine de **onay** öneriyorum; ücretsiz. |
| K13 | Barındırma | a) yerel + alışkanlık · b) yerel + uyandırma + dış izleme · c) VPS 4–6 €/ay · d) evde mini PC · e) karma | **b** şimdi; VPS'e geçmeden önce kaynak sitenin veri merkezi IP'sini engelleyip engellemediği 1 hafta denenmeli. |
| K14 | Pipeline sadece takip edilen ligleri analiz etsin mi? | a) evet (diğerleri haftada bir) · b) her şey (bugün) | **a** — sürenin %85'i hiç kullanılmayan liglere gidiyor. |
| K15 | H2H ≥ 5 kuralı model tahminlerini de kesiyor (ana ligde maçların ~%28'i) | a) aynen kalsın · b) "yalnız model" satırı (A1/A2/Katman A boş; v5, Poisson, A3 çalışır) — `ft-display-v5.1` gölgede | **b** gölgede. |
| K16 | Yeni lig partisi (gölge): League Two, Eerste Divisie, Yunanistan, Polonya, Çekya | onay / başka seçim | Onay (kurulum ~8–11 saat), ön koşul alias düzeltmesi (F7). |
| K17 | Avrupa kupaları | A hiçbir şey · B arşiv + canlı COND gölge (~1 hafta) · C + oran-prior maç öncesi gölge · D ligler arası model (XL) | B, iyi giderse C. |
| K18 | `prediction_backtest` eski kopyaları silme (165 MB, yedeğin çoğu) | onay / ret | Onay (koşu 2/3/4 aynı; koşu 6 eski kural). |
| K19 | Pattern B şemasındaki eksik alanlar için B sürümü 2→3 + B recompute (~15–20 dk) | onay / ret | Onay (arşiv sonrası recompute'la aynı seansta). |
| K20 | 2019/20 COVID iptali 142 maç + 19 play-off tekrarı + 2 yanlış lig satırı soft-delete | onay / ret | Onay (audit_log'a sebep düşülür). |
| K21 | Sayfalarda "piyasa olasılığı" ve "≈ adil oran" gösterimi | onay / ret | Onay — değer iddiası olmadan dürüstlük. |
| K22 | inplay-v1 (anlık maçlar) başlasın mı? Defter tablosuna migration gerekiyor | onay / ertele | Gol dakikası çekimi bitince başla; önce gölge. |

---

## 3. Senin hemen yapabileceklerin (kod gerektirmez)

1. **Bilgisayarı uyutma.** Ekranı kapatmak için uykuyu kullanma:
   - PowerShell: `powercfg /change monitor-timeout-ac 10` (ekran 10 dk sonra kapanır).
   - Denetim Masası → Güç Seçenekleri → "Güç düğmesinin ne yapacağını seçin" → güç düğmesi: **Ekranı kapat**; "Uyku"yu Güç menüsünden kaldır.
   - Arşiv tamamlama (~11–12 saat) ve gol dakikası çekimi (~30 saat) bitene kadar bilgisayar açık kalmalı.
2. **Arkadaşla paylaşımı Faz A ve Faz E bitene kadar ertele.** Tailscale'i kurmak serbest, ama `paylasim-ac.bat` çalıştırılmasın.
3. **Masaüstündeki `NORTVERSE-HATA.txt`** 27 Ekim 19:04 skor hatasını gösteriyor; sebebi bulundu (B1), dosya silinebilir.
4. **Windows Update etkin saatleri:** Ayarlar → Windows Update → Etkin saatler 08:00–02:00 (maç saatinde yeniden başlatmasın).

---

## 4. Fazlar ve adımlar

Sıralama bölüm 5'te. Her adımda: ne, neden (kanıt), nerede, nasıl test edilir, efor.

### FAZ A — Acil açıklar (Kupondaş + DB portu)

**A1 — Kupondaş kapanış mantığı (Kritik, M).**
- *Kanıt:* Kaynağın t=10 `MatchState` değeri canlıyken de bittikten sonra da **0** (2993842). `_FINISHED_STATES` ve `state in (2,3)` hiç tetiklenmiyor. İY dakikası `op` satırından okunuyor ("03"), en yeni `mt` değil. İY Ü/A geçmişinin en yeni satırı `close:true` ve oran 0, ama `parse_odds` bu satırı `_num` yüzünden atıp bir önceki açık satırı kullanıyor. `"45+2".isdigit()` False. DB skoru ~11 saat sonra geliyor.
- *Değişiklik:*
  - `scraper/odds.py`: `parse_odds` `close:true` satırını tutsun (`closed=True`); en yeni satır kapalıysa o pazar yok. `current_odds`: MS için t=10 özeti yerine t=20 h=0 geçmişinin en yeni satırı; canlı dakika/skor `op/ou/ah` arasında **en büyük `mt`** satırdan; maç içinde çifte şans gizli; maç içi satır `now − mt ≤ 90 sn` değilse kabul edilmez.
  - `api/routes_coupons._closed_reason`: evre `source_board`/`live_snapshot`'tan (1/2/3/−1 ve −10/−11/−12/−13/−14); `match_ht_observations` kaydı varsa İY kapalı; zaman sınırı İY `kickoff+47 dk`, MS `kickoff+115 dk`; dakika `re.match(r"(\d+)")`.
  - K2 = (a) ise `create_coupon`: `now ≥ kickoff_time` → 409 "Maç başladı".
  - Frontend savunması (`app/kupondas/page.tsx` `OddsPanel`): `now − kickoff > 47 dk` ise İY bölümü kapalı; yanlış canlı skor satırı gizlenir.
  - Kayıtta FT bacağı İY geçmişinden `live_minute/live_score` almasın (yanlış "03' 0-0" yazılıyor).
- *Testler:* `tests/test_odds_parser.py` (yakalanmış ham JSON fikstürleri: `close` satırı, en yeni `mt`, maç içi ÇŞ), `tests/test_routes_coupons.py`: `test_closed_reason_ft_when_actual_score_present`, `test_closed_reason_ht_when_board_2h_and_state_zero`, `test_closed_reason_ht_minute_with_stoppage_45plus2`, `test_closed_reason_time_limits_without_board`, `test_create_coupon_409_after_kickoff`; frontend `__tests__/kupondas-page.test.tsx` (60 dk geçmiş maçta İY butonu yok).
- *Migration:* yok.

**A2 — Bayat oranla kayıt (past-posting) (Kritik, S/M).** K2=(a) ise A1 ile çözülür. K2=(b) ise: maç içi kayıtta önbellek kullanılmaz (`max_age=0`), en yeni satırın skoru `source_board` skoruyla aynı ve yaşı ≤60 sn olmalı, 8 sn bekle-tekrar-çek; skor/oran aynıysa kaydet.

**A3 — Veritabanı portu ve şifresi (Kritik, S; arşiv ve gol çekimi bittikten sonra, maç saati dışında).** `docs/audit-2026-10-28/08-ops.md` Runbook A'nın özeti:
0. Uzun işler bitmiş olmalı; referans sayıları not et (`matches`, `prediction_ledger`, `alembic_version`).
1. Taze yedek (`schtasks /run /tn "\Nortverse\BackupDB"`) + `pg_restore --list` + D: diskine kopya.
2. Backend görevini durdur, frontend'i kapat.
3. Yeni şifre (`[guid]::NewGuid().ToString('N')`), `ALTER ROLE nortverse PASSWORD '…'`; `backend/.env` `DATABASE_URL`; kökte git'e girmeyen `.env` → `NV_DB_PASSWORD`; `docker-compose.yml` `POSTGRES_PASSWORD: ${NV_DB_PASSWORD}`.
4. `docker-compose.yml` `ports: ["127.0.0.1:5433:5432"]`; `docker compose up -d` (**asla `down -v`**).
5. Doğrula: `netstat -ano | findstr :5433` sadece 127.0.0.1; sayılar aynı; `audit-db`.
6. Backend'i başlat, `/api/health` 200.
7. Yerel PostgreSQL 5432 (PID 6540): kullanılmıyorsa servis durdurulup devre dışı; kullanılıyorsa `listen_addresses='localhost'`.
8. Güvenlik duvarında Docker'ın Public profil gelen kuralını kapat.
- Geri alma: port satırı + `ALTER ROLE` eski şifre; volume bozulursa `pg_restore --clean`.
- Sonra (M): uygulama için süper kullanıcı olmayan `nortverse_app` rolü.

### FAZ B — Veri doğruluğu (skor, erteleme, defter)

**B1 — update-scores gün başına dayanıklılık (Yüksek, S).**
- *Kanıt:* `cli/pipeline_cmds.py:471-484` `--pending-days` döngüsünde `try` yok; 21 Ekim 18:00 ve 27 Ekim 19:00'da tek günün zaman aşımı tüm çalışmayı `exit 1` ile düşürdü, `resolve_pending()` ve `settle_pending()` hiç çalışmadı. Ayrıca `dt=None` iken `day == dt` eşleşmediği için bugün iki kez işleniyor. 27 Ekim'de bugünün sayfası boş geldi ve "331 atlandı · 0 hata" başarılı sayıldı.
- *Değişiklik:* her `update_results(day)` kendi `try/except` bloğunda; `resolve_pending` + `settle_pending` `finally`'de; herhangi bir gün başarısızsa sonda kod 2; hedef günü atlama karşılaştırması düzeltilsin; `runner.update_results` beklenen maç >0 iken kaynak boş dönerse `errors`'a saysın; "güncellendi" sayacı sadece **değişen** satırları saysın; `result_fetched_at` sadece skor değişince yazılsın.
- *Testler:* `test_update_scores_continues_after_one_pending_day_fails`, `test_update_scores_still_resolves_ledger_and_coupons_on_day_failure`, `test_pending_days_skips_default_target_day`, `test_empty_source_page_counts_as_error`.

**B2 — Durum haritası: ertelenen / tatil / iptal / uzatma (Yüksek, M).**
- *Kanıt:* `fixture_scores.py:60` sadece "Postp." tanıyor (AET, Pen., Abd., Canc., Pend. → satır atlanıyor, maç hiç bitmiyor); `source_board.py:47-48` −10/−12/−13 ve 4/5 kodlarını sessizce atlıyor; `ledger._PENDING_SQL` (`ledger.py:45`) sadece `actual_ft_home`'a bakıyor; 3003600'ın 38 kaydı ve kupon bacakları sonsuza dek bekliyor; 2993837 Fiorentina–Atalanta muhtemelen ertelendi ama kupon listesinde seçilebilir.
- *Değişiklik:* yeni `scraper/status.py` tek harita: FT/AET/Pen → bitti (pazarlar 90. dakika skoruyla çözülür, uzatma skoru ayrı tutulur); Abd/Canc/−10/−12/−13 → `abandoned`; Postp/−14 → `postponed`. Tanınmayan etiket ve kodlar sayılıp loglansın.
  - `ledger.resolve_pending`: `abandoned` → void; kickoff + 3 gün geçmiş ve `postponed` → `invalidate_predictions(reason="postponed")`.
  - **48 saat kuralı**: maç öncesi kaydın `recorded_at` ile **gerçek** kickoff arası >48 saat → void (3026759 bunun örneği).
  - `runner.sync_kickoffs`: kickoff >6 saat kayarsa o maçın eski maç öncesi kayıtları `invalidate_predictions(reason="rescheduled")`; yeni karar için yeniden dondurma (snapshot anahtarına kickoff eklenmesi gerekebilir — migration, L).
  - Kupon: dondurulmuş kickoff + 48 saat skor yok / `abandoned` / silinmiş maç → bacak `void`, katsayı 1,0.
  - Çözücü sürümü `stats-v2`.
- *Testler:* `test_prematch_row_voided_when_kickoff_moved_beyond_capture_horizon`, `test_live_row_voided_when_match_replayed`, `test_abandoned_match_voids_ledger_and_coupon_legs`, `test_aet_resolves_on_90_minute_score`, `test_postponed_carried_fixture_not_used_for_sync`.

**B3 — Tek seferlik temizlik (K8, K20 onayıyla, S).**
- `invalidate_predictions`: 3026759 (50), 3003600 (38), live-ms-v1 geç 17 kayıt (3008288, 3008290, 3008292, 3008294, 3008295, 3013737; `details.late=true`).
- `update-scores --date 2026-10-09` ve `--date 2026-10-10` (Galatasaray–Kasımpaşa, Lens–Lyon, Dortmund–Bremen, PSV–Heerenveen, Málaga–Espanyol, Rayo–Athletic skorsuz).
- `repair-archive`'a "sezon kapanmış + kickoff geçmiş + skor yok → `deleted_reason='cancelled'`" kuralı (2019/20 NED 57, FRA 85); play-off tekrarları ("sezonda ikinci karşılaşma, sezon sonu" — Eredivisie 14, Championship 4, Serie A 1); 2 yanlış lig satırı (`HOL D2` 2007/08, `German 2. Bundesliga` 2006/07). Önce dry-run.

**B4 — Canlı kayıt pencere hataları (Yüksek, S).**
- `api/live_ledger.freeze_live_prediction`: ana live-ms-v1 satırı `archive_freeze_allowed` penceresine bağlı değil → 24 Ekim'de 17 kayıt ~97. dakikada yazıldı. K10=(a) ise live-ms-v1 kaydı durur; aksi halde pencereye bağlanır (`live-ms-v1.1`).
- `predict_live` (live-ms-v1) hata verirse v1.1 kayıtları da yazılmıyor ve "dondurulmuş mu" testi live-ms-v1 satırına bakıyor → ana kaydı v1.1'e bağla / diğer gölgeler gibi `try` içine al.
- `routes_live_ht._poisson_decisions`: dondurulmuş maçta defter satırı yoksa kararlar anlık yeniden hesaplanıyor (bitmiş maçta güncel model sonucu görmüş olur) → dondurmada `details.poisson_evaluated` yazılsın; dondurulmuş maçta defter boşsa `decisions=[]`.
- *Testler:* `test_live_ms_not_frozen_after_minute_50`, `test_frozen_match_without_poisson_rows_shows_no_decisions`.

**B5 — İY arşiv alanları "hep 0" hatası (Orta, S → M).**
- *Kök neden:* `analysis/pattern_stats.py` `ht_pairs` sadece `period == "ft"` bloğunda dolduruluyor (~296–304); `iy_*`, `ev_ht_*`, `dep_ht_*`, `ht_result_*`, `ht_dc_*`, `ht_kg_*`, `iki_yari_*`, `encok_*` alanları `if ht_pairs:` altında (384–421); İY/2Y periyodunda boş kalıp dataclass varsayılanı `0.0` (108–126) gerçek sıfır olarak yazılıyor. Ekranda sızıntı yok (frontend tüketicileri FT ile korumalı).
- *Değişiklik:* (S) okuyan her yer `ust_05_pct`/`ev_ust_05_pct` veya `pattern_ft_*.iy_*` kullansın; (M, kalıcı) bu alanlar `Optional[float] = None` ve `period != "ft"` iken None; `PATTERN_ALGO_VERSION` b/c/d artışı + recompute. `confidence.ts` `isMarketActive` `ftZeroCheck`'i gerçekten kullansın.

**B6 — Kickoff yer tutucusu 15:59 UTC (Orta, M).** Ana ligde 1.707 tarihsel satır; 574'ü aynı gün 3–9 saat sonraki 709 maça aday olarak sızıyor (backtest ve Pattern geçmişinde küçük gelecek bilgisi; defterde 0). Aday filtresinde 15:59'u "gün sonu" say; yeni algoritma sürümü + recompute (arşiv sonrası runbook'la birlikte).

**B7 — Oran geçmişini boş yanıtla ezme (Orta, S).** `odds.load_or_fetch` (`odds.py:199-206`): yeni geçmiş boşsa veya pazar başına en yeni `mt` eskisinden küçükse yazma. Test eklenir.

### FAZ C — Kural ve sürüm disiplini

**C1 — COND tablosuna zaman penceresi (Yüksek, M; K9).**
- *Kanıt:* `live_model.build_cond_table` tüm geçmişi okuyor. Arşiv tamamlama NED'e +1.513 (COND havuzunun %31'i), GER'e +1.048 (%22) maç ekledi. Eski tablo kayıttaki değerleri birebir üretiyor; yenisiyle 189 kayıtlı kararın 10'unda fark ≥1 puan (en fazla 2,1). Henüz kapı değişmedi, ama eşik yakınında değişebilir. Bugün kurulsa backtest #13 ile 420 kararlık fark.
- *Değişiklik:* COND `kickoff ≥ as_of − N yıl` (öneri: Poisson ile aynı 3 yıl veya son 10 sezon; arşiv sonrası ölçümle seç) — parametre `RULE_PARAMS`'a. Yeni sürümler gölgede: `live-arch-v2.1`, `live-2h-v1.1`, `live-poisson-v1.2` (sadece "değerli" etiketi/cond_pct değişir). `ResultsWatch` işareti sadece son 30 günün sonuçlarına baksın (arşiv eklemeleri tetiklemesin).
- *Test:* aynı `as_of` ile iki kurulum aynı sayaçları verir; eski satır eklenince pencere dışındaki sonuç değişmez.

**C2 — Parmak izi açıkları (Yüksek, S + sürüm artışı).**

| Kural | Durum | Değişiklik |
|---|---|---|
| ht-display-v1 | takım modeli parmak izi yok | `prematch_ht.rule_params_fingerprint` payload'ına `team_model_fingerprint()` → `ht-display-v1.1` |
| live-2h-v1 | Poisson/takım modeli yok | payload'a `team_model_fingerprint()` → `live-2h-v1.1` |
| live-arch-v2 | `PATTERN_ALGO_VERSION` ve `MIN_COND_N` yok (A2/A3 c4/d4 olduğunda sürüm atlamadı) | payload'a ekle → `live-arch-v2.1` (C1 ile birlikte) |
| live-ms-v1 | `RULE_PARAMS` ve sabitlenmiş test yok | K10=(a) ise kaydı durdur; aksi halde `RULE_PARAMS` + test |
| market-summary-v2 | kendi parametresi yok | `MARKET_SUMMARY_PARAMS` + sabitlenmiş test |
| ht-value-v1 | test yok | sabitlenmiş test (sadece backtest'te kullanılıyor) |

- Yeni genel test `tests/test_rule_registry.py::test_every_rule_version_has_pinned_fingerprint`: tüm `*_RULE_VERSION` sabitlerini tarar, her birinin parmak izi fonksiyonu ve sabitlenmiş değeri olduğunu doğrular.

**C3 — Geçmiş isabet çipi sadece ana lig (Düşük, S).** `live_poisson.load_hit_table` #15'ten okuyor ve kararların %38'i gölge ligden (etki ~0,2 puan). Sorguya ana lig süzgeci.

**C4 — Kapsama karnesi (Orta, S–M).** Değerlendirme sayfasına "devre arasına gelen izlenen maç / dondurulan" oranı (`/api/performance/coverage`). 19–26 Ekim: ana 50/57 (%87,7), gölge 26/36 (%72). Karneler "kapsanan maçlar" üzerinden okunmalı.

### FAZ D — Operasyon

**D1 — Görev ayarları (Yüksek, S; yönetici PowerShell).** `scripts/install-tasks.ps1`:
- UpdateScores2'nin 00:30 tetikleyicisi UpdateScores1'e taşınsın, UpdateScores2 silinsin (uyanınca ikisi paralel çalışıyor).
- RunPipeline süre sınırı 2 → 4 saat (72/87/70 dk sürdü).
- BackupDB ve RunPipeline `-WakeToRun`; tüm görevler `-RunOnlyIfNetworkAvailable`.
- Görev geçmişini aç: `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`.
- `run-pipeline.bat` ve `update-scores.bat`: `ensure-docker` sonrası ağ bekleme döngüsü (`Test-NetConnection live5.nowgoal26.com -Port 443`, 30×10 sn); pipeline hata verirse 10 dk sonra bir kez daha (21 Ekim'de uyanıştan 40 sn sonra DNS hatasıyla tüm gün kaçtı).
- `backup-db.bat` başına 5 dk gecikme (pipeline ile aynı anda DB'yi yormasın).

**D2 — Backend sarmalayıcısı (Yüksek, S → M).**
- *Kanıt:* `start-backend.bat` `timeout /t 30` gizli konsolda hiç beklemiyor (0,06 sn); uyku anında `STOPPED` boş kalıyor → çalışma süresi negatif ("-1,79e9 sn") → 10 dk sayaç sıfırlaması hiç çalışmıyor; port 8000 doluysa sessizce `exit 0` (yeniden deneme tetiklenmiyor). 22–25 Ekim "port dolu" satırları ikinci kopya şüphesi doğuruyor.
- *Ara düzeltme (S):* `ping -n 31 127.0.0.1 >nul`; `STOPPED` boşsa `UPTIME=0`; port doluysa 2 dk bekle, hâlâ doluysa `notify-error` + `exit /b 1`.
- *Kalıcı (M):* `scripts/start-backend.ps1` denetleyici — `Local\NortverseBackend` mutex (tek kopya), port sahibinin komut satırına bakar (bizimse ve health 200 ise izler; yabancıysa uyarır, 60 sn'de tekrar dener, asla sessiz çıkmaz), süreç içi süre ölçümü, dakikada bir `scripts/logs/backend.heartbeat`. Görev tetikleyicileri: oturum açılışı + **uyanma olayı** (Power-Troubleshooter EventID 1) + kilit açma + 15 dk güvenlik ağı. Elle geliştirme sunucusu `--port 8001`.
- *Test:* süreci öldür → 60 sn'de geri; 8000'i başka süreçle işgal et → uyarı; uyut/uyandır → 1 dk'da health 200.

**D3 — Yedekleme (Yüksek, S + M).**
- *Kanıt:* 7 dump C:'de (SSD %89 dolu); D: ayrı 1 TB disk, 930 GB boş, kullanılmıyor; `.env` dosyaları hiçbir yedekte yok; gerçek geri yükleme hiç denenmedi.
- (S) `backup-db.bat` sonunda `robocopy` ile `D:\NortverseYedek`, 30 gün budama; `backend\.env` ve `frontend\.env.local` kopyası.
- (S) Aylık geri yükleme testi: ayrı geçici konteyner (`postgres:16-alpine`, `127.0.0.1:5544`), `pg_restore --exit-on-error`, sayım karşılaştırması, konteyner silinir; sonuç `backup.log`'a. Komutlar `08-ops.md` Runbook B'de.
- (M, K12) Haftalık şifreli bulut kopyası (7-Zip AES-256 `-mhe=on`), son 4 hafta.
- Yıllık "felaket provası" belgesi (yeni PC'ye kurulum adımları).

**D4 — Sağlık kontrolü ve ölü adam anahtarı (Yüksek, M).**
- `scripts/health-check.ps1`, "HealthCheck" görevi, 15 dk'da bir, 11:00–01:30:
  1. DB konteyneri `healthy`.
  2. Backend kalp atışı <3 dk ve `/api/health` 200.
  3. 13:00'ten sonra bugünün pipeline'ı başarılı.
  4. **Canlı kayıt kontrolü:** başlaması 50–70 dk önce olan izlenen maç varsa son 25 dk'da `live_ht` kaydı olmalı.
  5. 18:00–01:00 arası son başarılı skor güncellemesi <2 saat.
  6. Bugünün yedeği >200 MB; D: kopyası <2 gün; bulut <8 gün.
  7. C: boş alan >20 GB.
  8. Uzun iş loglarında "durduruldu" yok; oran kaydı <24 saat.
  - Hata → `notify-error.bat`; aynı uyarı 2 saatte bir kezden fazla değil.
- (K12) Dış ölü adam anahtarı: healthchecks.io ücretsiz (backend, pipeline, scores ping'leri) veya ntfy.sh. Bilgisayar uyursa/kapanırsa telefona haber gelir — yerel hiçbir betik bunu yapamaz.

**D5 — Uzun işler canlı operasyonla yarışmasın (Orta, S).** Maç saatlerinde (hafta içi 19:00–00:30, hafta sonu 13:00–00:30) arşiv `--concurrency 1`, gol çekimi `--delay 12` ya da durdur; iki iş aynı anda değil sırayla; kalıcı olarak gizli gece görevi (01:00–12:00, kaldığı yerden). Gol çekiminde "5 hata → dur" kuralı geri çekilmeli beklemeye dönsün. 27 Ekim 19:00 skor zaman aşımı arşiv çekimiyle çakıştı.

### FAZ E — Arkadaşla paylaşım hazırlığı (Faz A3 ve bu faz bitmeden link verilmez)

**E1 — Sunucu tarafı çizim yönetici olmasın (Yüksek, M).** `auth.py:145` `_SERVER_USER = AuthUser(0,"sunucu",True)`; `lib/api.ts:18-24` her SSR isteğine `x-internal-key` ekliyor → yönetici olmayan kullanıcı `/analyze/<id>` (`page.tsx:27`) veya önbellekte olmayan `/bulten?date=` ile Playwright tetikliyor (28 Ekim 45 sn 503 örneği). Değişiklik: `withServerAuth` `cookies()` ile `nv_session`'ı da iletsin; backend iç anahtar geçerliyse çerezdeki **gerçek kullanıcıyı** kullansın; çerez yoksa `_SERVER_USER` `is_admin=False`. Kullanıcıya özel uçlara `cache: "no-store"`. Test: iç anahtar + normal kullanıcı çerezi → `/api/fixture` kazıma yok.

**E2 — Next.js 16.4.x güncellemesi (Yüksek, M; K5).** `npm audit`: 1 kritik, 4 yüksek, 1 orta (proxy atlatma GHSA-267c / 26hh / 492v, WebSocket SSRF, yönlendirme önbellek zehirlenmesi, DoS). Önce `node_modules/next/dist/docs/` güncelleme notları okunur; `next@16.4.3` + `eslint-config-next` aynı sürüm + `npm audit fix` (nanoid, source-map-js, sharp, postcss). Sonra: `proxy.ts` matcher (`/girisX`, `/apiary` gibi önekler), `AbortSignal.timeout`, `fetch` `revalidate` varsayılanları (11 çağrı), `searchParams: Promise` elle kontrol; tsc, eslint, vitest, e2e, proxy için elle 401/200/zaman aşımı denemesi.

**E3 — Adres başlığı taklidi ve giriş kilidi (Yüksek, S).** uvicorn 0.34.2 `proxy_headers` varsayılan açık + Next rewrite istemcinin `X-Forwarded-For`'unu aynen iletiyor → backend'in gördüğü IP istemcinin istediği değer (doğrulandı). Değişiklik: `uvicorn.run(..., proxy_headers=False)` (`pipeline_cmds.py:521`); giriş sınırı = kullanıcı adı başına 8/15 dk + **genel** sınır (ör. 40/15 dk), IP anahtarı kaldırılır; `_failures` sözlüğüne üst sınır; analiz/oran/kupon hız sınırları **kullanıcı kimliğine** göre; tekrarlanan `_client_ip` tek yere. CLI'ya `unlock <ad>`. Testler: sahte başlıkla genel sayaç; 8 hatada 429; log'da 127.0.0.1.

**E4 — Giriş yönlendirmesi (Yüksek, S).** `app/giris/page.tsx:7-10` `safeNext()`: `/%5Cevil.com`, `/%09/evil.com`, `/%0A/evil.com` → başka siteye gidiyor (doğrulandı). `lib/safe-next.ts`: kontrol karakteri/ters bölü reddi + `new URL(raw, origin).origin === origin`. Test `__tests__/safe-next.test.ts` (3 saldırı + 3 geçerli yol).

**E5 — `proxy.ts` hata durumunda kapıyı kapalı tutsun (Yüksek, S).** Şu an 401 dışındaki her yanıt/zaman aşımı/istisna sayfayı açıyor; çerez değeri uydurma olabilir. Sadece `res.ok` → geç; 401 → giriş; diğer → 503 sayfası. Test `__tests__/proxy.test.ts` (200/401/500/zaman aşımı/istisna, matcher). Ek: girişliyken `/giris` → `/bulten`; `/api/auth/me` için 30 sn bellek önbelleği (her prefetch'te backend'e gitmesin).

**E6 — Üretim modu (Orta, S–M).** `__nextjs_source-map` oturumsuz 204 dönüyor; hata ekranı dosya yolları ve kaynak gösteriyor; `allowedDevOrigins: ["*.ts.net"]` çok geniş. `package.json` `"start": "next start -H 127.0.0.1 -p 3000"` (**`-H` zorunlu**, yoksa tüm ağa açılır); `scripts/frontend-build.bat` (hata olursa eski `.next` korunur); `scripts/start-frontend.bat` + "Frontend" görevi (Backend ile aynı tetikleyiciler); `paylasim-ac.bat` ve `start-local.bat` üretim sunucusunu başlatsın; geliştirme `-p 3001`. WebSocket `/ws/live-ht` rewrite üzerinden elle doğrulanmalı.

**E7 — Tailscale (Orta, S).** Kurulum sonrası: yönetim panelinde ACL ile arkadaş **sadece bu cihazın 443 portuna** (`{"action":"accept","src":["<arkadaş>"],"dst":["<pc>:443"]}`); bağdaştırıcı profili kontrol (`Get-NetConnectionProfile`); arkadaşın cihazından 5433/5432/8000/3000 kapalı, 443 açık testi; `X-Forwarded-For` testi; WS çalışmazsa `tailscale serve --bg --set-path /ws http://127.0.0.1:8000/ws`. Rehbere: "funnel kullanmayın", "önce DB portu", "arkadaş hesabı" (K1).

**E8 — Paylaşım sonrası (Orta/Düşük).** `ADMIN_API_KEY` tanımla + `hmac.compare_digest`; `/api/health` girişsizde sadece durum; backend `/docs` ve `/openapi.json` kapalı; `disable-user`, `logout-all` komutları; oturum önbelleği 10–15 sn; WebSocket'te 60 sn'de bir oturum kontrolü (çıkışta bağlantı kapansın); sabit zamanlı giriş (kullanıcı yoksa sahte özetle doğrulama) + scrypt `to_thread`; POST/WS için `Origin` kontrolü; çerez `secure` (HTTPS arkasında) veya `__Host-` öneki; çıkışta `nortverse_bet_cart` temizliği.

**E9 — Kaynak koruması (Yüksek, M).** `scraper/browser.py` modül seviyesinde `Semaphore(PLAYWRIGHT_MAX_CONCURRENCY=2)`; fixture için tarih başına kilit; `/api/odds` 20/dk ve `POST /api/coupons` 6/dk kullanıcı başına (`app/api/ratelimit.py`); `scraper/odds.py` genel istek semaforu (4) ve ~1 istek/sn token bucket, 403/429'da üstel bekleme, `/api/health`'e istek sayacı. Amaç: tek bir kullanıcı/hata bilgisayarın belleğini bitirmesin, evin IP'si kaynak tarafından engellenmesin.

### FAZ F — Pipeline ve kazıyıcılar

**F1 — Maç öncesi dondurma uyanıklığa bağlı kalmasın (Kritik, M).** Pipeline 11:10–15:56 arası başlıyor, en kısa pay 1,7 saat; 21 Ekim'de Levante–Athletic v5 kaydı kaçtı; başlamış maç `runner.py:413-415`'te log'suz atlanıyor.
- (a) 22:00 skor işinden sonra `run-pipeline --date <yarın>` (48 saat penceresi buna izin veriyor).
- (b) `run_pipeline` önce takip edilen ligleri başlama saatine göre işlesin.
- (c) Bülten çekimi DNS/zaman aşımında 3 kez (5/10/15 dk) yeniden denesin.
- (d) Başlamış takip maçı atlanınca `log.warning` + `missed_started` sayacı.

**F2 — Pipeline kapsamı (Yüksek, S; K14).** `run_pipeline(scope="tracked"|"all")`, varsayılan `tracked`; `all` haftada bir ayrı görev (aday ligler için veri biriktirir). 24 Ekim'de 263 analizin 36'sı takipteydi, iş 86 dk sürdü.

**F3 — "?" lig adı hatası (Yüksek, S).** `fixture.py:82-83` `.LGname` yoksa `"?"` yazıyor ve satır 146'daki `or` onclick'teki gerçek adı eziyor → 30 günde 2.684/11.227 maç (%24) pipeline'a hiç girmiyor. `None` yaz; test.

**F4 — "champions" yanlış pozitifi (Orta, S).** `league_filter.py:24` Scottish/USL/Wales/NI Championship'i kupa sayıyor → `\bchampions\b` + test.

**F5 — Sessiz sıfır-parse korumaları (Orta, S).** `fetch_fixture` 0 satır → hata; `pipeline_failed` kaynak bülten 0 → hata; `update_results` "kaynakta maç yok" → hata ve sıfır olmayan çıkış; ana ligde `h2h_insufficient` >%50 → uyarı (lig adı eşleşmesi bozulunca erken haber).

**F6 — Kanarya komutu (Orta, M).** `scrape-canary` (yazmaz; pipeline'dan ve 18:00 skor işinden önce; sonuç `audit_log`'a; hata → `notify-error`): bülten ≥50 satır, saat ayrıştırma ≥%95, "?" <%10; altın maç 2813084 H2H (FT 1-0, İY, tablolar ≥10 satır); dünün skorları ≥%80 FT + tanınmayan etiket histogramı; `source_board` ErrCode 0 + tanınmayan kod sayısı; odds dolu; goal_events skor eşit; haftalık `fetch_league_seasons(36)`; alan adı DNS/yönlendirme hedefi değişim uyarısı. Ayrıca `tests/fixtures/nowgoal/` altına **gerçek sayfa örnekleri** (bugünkü testlerin hepsi sentetik HTML; site biçim değiştirse yakalamaz).

**F7 — Lig adı alias'ları (Orta, S; yeni lig partisinin ön koşulu).** "Spanish La Liga 2", "Turkey 1. Lig", "England League 1/2" eksik; DB'de "England League 1" (12) ve "England League One" (1) aynı lig iki adla. Alias + "her takip edilen lig için `canonical(bülten adı) == canonical(H2H kodu)`" testi + `normalize-leagues --apply`. `lib/leagues.ts`'e `German 2. Bundesliga`, `Dutch Eredivisie` bayrakları.

**F8 — Skor gecikmesi (Orta, M).** p50 ~2,5 saat, en kötü ~20 saat (00:30–18:00 arası çalışma yok). Canlı izleyici `source_board` −1 kodu + İY skorunu kesin sonuç adayı olarak yazsın (gece fixture sayfasıyla doğrulanır) ya da 14:00–17:00 saatlik görevler.

**F9 — build-archive hata takibi (Orta, M).** `archive_cmds.py:89-90` hatalı maç kimliğini yazmıyor → `scripts/logs/archive_failed.txt` + `--retry-file`; `expected_league_name` sezon JSON'undan; play-off turları JSON'daki tur anahtarıyla ayıklansın. `league.py:26-27` sabit alan adı → `SCRAPER.data_url` (Düşük).

**F10 — Canlı Playwright bütçesi (Orta, S).** `live_snapshot._refresh` 30 sn bütçe veriyor, `fetch_live_scores` 30 sn × 3 deneme + 12 sn istiyor → 13 kez "Future exception was never retrieved"; canlı maç yokken de 45 sn'de bir Chromium açılıyor. `fetch_live_scores` bütçe parametresi alsın; canlı aday yokken sadece AJAX pano.

**F11 — fixture_cache koruması (Düşük, S).** 16 Ekim kaydı 7 maçla kesik (büyük listenin üzerine yazılmış); 21 ve 29 Ekim yok. Yeni liste eskisinin %50'sinden küçükse uyar/birleştir. `skipped_analysis` 90 günden eski satırlar budansın.

### FAZ G — Arşiv tamamlandıktan sonra (runbook)

Arşiv tamamlama 28 Ekim 09:56'da yeniden başladı; 14 sezon bitti, 27 kaldı (HOL 2005-06 → 2003-04, FRA 10, TUR 10, ESP 2, ITA 2), ~11–12 saat. GER 2003-05 kaynakta yok.

| # | Adım | Komut / not | Süre |
|---|---|---|---|
| 0 | Bittiğini doğrula (`archive-done.txt` 41 sezon); gol çekimi ağır yazmalarla çakışmasın | — | — |
| 1 | Yedek | `scripts\backup-db.bat` | ~5 dk |
| 2 | Hatalı 60 maçın sezonları | `build-archive 8 2009-2010`, `8 2007-2008`, `8 2006-2007`, `16 2011-2012`, `16 2010-2011`, `16 2009-2010`, `16 2007-2008` (sadece eksikler çekilir) | ~2–3 sa |
| 3 | Temizlik (K20) | `audit-db`; `repair-archive` dry → `--apply`; `normalize-leagues` → `--apply`; yanlış lig + play-off soft-delete | ~20 dk |
| 4 | Takım gücü λ | `backfill-team-lambdas` | 15–30 dk |
| 5 | Yeni satırların arşiv istatistikleri | `recompute-patterns --stale-only --include-finished --limit 200` (deneme), sonra limitsiz | 10–15 dk |
| 6 | B sürümü (K19) | `PATTERN_ALGO_VERSION["b"]` 2→3, `recompute-patterns --stale-only --family b --include-finished` | 15–20 dk |
| 7 | Tüm satırların yeni arşivi görmesi | **Önerilmiyor**: eski sezonların bugünkü maçlara katkısı %3–5 (150 maç sınırı + 3 yıl yarı ömür), 38 bin satır ~65 dk, deftere etkisi yok. Önce 8. adımda ölç | — |
| 8 | COND kaymasını ölç (K9) | `backtest-ledger --strategy live_archive/live_poisson/live_2h --from 2023-07-01 --to 2026-10-18`; #13/#11/#14 ile karşılaştır; kararların ≥%2'si değişirse C1 penceresi zorunlu | her biri 0,5–1,5 sa |
| 9 | Bakım | `VACUUM (ANALYZE) matches; ANALYZE prediction_ledger;` (FULL değil) | ~5 dk |
| 10 | Son kontrol | `audit-db` + `self-test 2813084` | ~5 dk |
| 11 | Backend yeniden başlat (A3 havuzu + COND önbelleği), CLAUDE.md, commit | — | — |
| 12 | (K18) Eski backtest koşularını sil + VACUUM | onaylı CLI (`ON DELETE CASCADE`) | ~10 dk |
| 13 | Faz A3 (DB portu) bu noktada yapılabilir | — | ~15 dk |

### FAZ H — Ekranda dürüstlük

**H1 — Ana Pazar Özeti (Yüksek, S + M; K7).**
- *Kanıt:* market-summary-v2 ana ligde 1.460 tekil karar, gösterilen 54,5 → gerçek 48,1 (üst sınır 50,8) = **beklentinin altında**; gölge ligde de aynı. Kovalar: 50–60 gösterilen 54,5 → gerçek 41,1; 90–100 93,9 → 83,3. En kötü: MS fark %24 (gös 31,8), MS+2.5 %26,7 (36,1), İY/MS %25,9 (32,8), 2Y sonuç %37,1 (46,2). A2 266 kararda %36,8 (gös 51,7), A1 182 kararda %40,1 (54,0), A3 901 kararda %53,1 (55,5). Bu pazar için hiç backtest koşusu yok.
- *Değişiklik (S):* `components/MarketSummary.tsx` sütun başlığı "Arşiv sıklığı", hücrede `7/13` sayı/örneklem, yüzde ikincil; yeşil ton ve dolu çubuk kaldırılır; `lib/confidence.ts` `INFORMATIONAL_MARKETS`'e `fark`, `iy_ms`, `ms_25_combo` (gerekirse `hnd_*`); başlık rozetinde karne ("geçmişte gösterilen %54,5 → gerçekleşen %48,1"); varsayılan kapalı akordeon.
- *Gölge (M):* `market-summary-v3` — kazanan, v5 skor ızgarasından olasılık ile A1/A2/A3 sıklığının en iyisi; pazar başına ≥100 kararda karne.

**H2 — "Değer" çağrışımı (Orta, S; K21).** Canlı sayfa ~1,01 oranlı %99 ÇŞ X2'ye yeşil **"En iyi"** rozeti koyuyor (`LiveArchiveView.tsx:129-133`) → "En yüksek olasılık". Her canlı ve maç öncesi yüzdenin yanına "≈ adil oran 1/p" (ör. %92 → ≈1,09). Top Picks "avantaj" → "lig ortalamasının +Y puan üstü".

**H3 — "Skordan belli" etiketi (Orta, S).** Canlı Poisson kararlarının %89–96'sında COND zaten ≥%80. Kararlara "İY skoru zaten söylüyor" rozeti (gri), COND <%80 olanlar "model katkısı" (bugünkü "değerli"). Gölge kural önerisi `live-poisson-v1.2-trivial-tag` (C1 ile aynı sürüm).

**H4 — Piyasa olasılığı (Orta, M; K11, K21).** `app/analysis/market_prob.py` (payı çıkarma; Asya adil oran; Poisson ters çözüm; çeyrek çizgi/iade; `ht_value.total_return` ile birleşir) + test. Top Picks, Ana Pazar ve canlı kartta Bet365'in payı çıkarılmış olasılığı + "piyasaya göre ±X puan" (değer iddiası yok). Kupondaş'ta value ipucu **yok**; canlı ~%90 işaretlerin ~1,05 oran olduğu açıkça yazılır.

**H5 — v5 kademesi (Düşük, S).** 29 seçimin 27'si "high" (kademe "v4 aynı seçimde" demek, ayırt etmiyor). Kademe avantaj büyüklüğüne bağlansın → `ft-display-v5.1` gölgede. Ayrıca oran ajanı: model güçlü favorileri olduğundan düşük gösteriyor (%74 diyor, %84 tutuyor; ridge ortalamaya çekiyor) — v5.1'de not edilip ölçülsün.

### FAZ I — Oran altyapısı

- **I1 (S, K11):** MS oran geçmişi doldurma `backfill-odds --scope ft --since 2026-02-01 --delay 6` (~2.100 maç, ~5–6 saat; arşiv + gol çekimi bitince). Bir istek açılış, kapanış ve tüm canlı satırları (dakika, "HT", skor) getiriyor.
- **I2 (S/M):** Günlük oran kaydı: `update-scores` sonunda o gün biten takip maçları için ft + ht geçmişi (`odds_cmds --days N`, günde 30–80 istek); İY panosu için yaklaşan maçların İY oranlarının önceden çekimi (pipeline / 15 dk görev). İsteğe bağlı: canlı izleyici devre arasında `current_odds` → `details.market` (sürüm artmaz).
- **I3 (S):** Kazıyıcı hızı: `ODDS_BASE_URL=https://live.nowgoal.life` (yönlendirme 4,4 sn kazanç), `http.client` kalıcı bağlantı + DNS önbelleği, aynı maça eşzamanlı istekleri tek çekimde birleştir, `Content-Type`/JSON doğrulaması, challenge/boş yanıtı önbelleğe alma ve `_resolved_base` sıfırla.
- **I4 (M):** `backtest-market` salt okur komutu (I1'den sonra): v5 kapanış/açılış getirisi, kapanış çizgisi değeri (CLV — birincil ölçüt), karışım, canlı 1X2 kararlarının gerçek devre arası fiyatı. +%3'lük bir kenarı görmek ~2.700 seçim (3–4 sezon) ister.
- **I5 (M, Düşük):** Yedek bahisçi: `ODDS_BOOKMAKERS=[8, …]` sıralı, pazar başına yedek; `coupon_legs.bookmaker_cid smallint` (metadata işlemi); önce 10–15 cid keşfi (Pinnacle bulunursa düşük paylı referans).
- **I6 (M, gölge):** `ft-display-v6-mkt` — gösterilen olasılık `model^0,2 × piyasa^0,8` (amaç dürüstlük: testte piyasadan farksız, modelden belirgin iyi).

### FAZ J — Kupondaş geliştirmeleri (A1/A2 sonrası)

| # | Ne | Önem | Efor |
|---|---|---|---|
| J1 | `coupon_status` yarım kayıpta "iade" yazıyor (`coupons.py:58`): `isclose(r,1)` → refund, `<1` → **`partial_loss`**, `>1` → won; frontend tipi + sözlük + renk; 87 bin durumluk doğrulama testi kalıcı parametreli teste | Yüksek | S |
| J2 | `LegIn`'e `line` + `seen_odds`; çizgi farklı veya oran ±%3'ten fazla kötüleşmişse 409 + "oran değişti, onayla" diyaloğu; taslak 30 sn'de bir oran yenilesin; kayıt yanıtı kaydedilen bacakları dönsün | Yüksek | M |
| J3 | `Idempotency-Key` (10 dk bellek); `MAX_LEGS` 20 → 10; çekim `Semaphore(3)`; bir maç hata verince tüm kupon 503 olmasın (hangi maç olduğu söylensin) | Yüksek | S |
| J4 | Maç başına tek seçim (K3) — `create_coupon` + frontend `toggle` | Yüksek | S |
| J5 | Sonuçlandırma GET'ten çıksın: `update-scores` + canlı izleyici turu + 5 dk arka plan; İY bacağı `match_ht_observations`'tan (devre arasında sonuçlanır), 24 saat İY yoksa void | Yüksek | M |
| J6 | Bülten tabanlı bacak (K4): `coupon_legs` → `matches` FK kaldır/`NOT VALID` + `source varchar(10) default 'db'`; `/api/coupon-matches` = `fixture_cache` (taşınmamış) + DB bitmemiş, lig filtresi kalkar, arama + lig gruplama; `MatchRef` (önce `matches`, yoksa `fixture_cache`); sonuç `fixture_cache.matches_json`'dan (`runner._merge_fixture_scores` İY dahil yazıyor). İskelet `matches` satırı **önerilmiyor** (doğrulama, temizlik ve onlarca sorguyu bozar) | Yüksek | M–L |
| J7 | Skor düzeltmesi kupona yansımıyor: `coupon_leg_resolutions(leg_id, revision, outcome, factor, score, source_revision)` ek tablo, okumada en son revizyon | Orta | M |
| J8 | Açık kuponların canlı durumu (bacak başına skor/dakika, tutuyor/tutmuyor, 30–60 sn yenileme) | Orta | M |
| J9 | Kullanıcı karnesi / puan tablosu: kupon sayısı, kazanılan/kaybedilen, bacak isabeti, 1 birim ROI, ortalama ve en yüksek kazanılan oran; haftalık/tüm zamanlar (`/api/coupons/stats`; J4 önce) | Orta | M |
| J10 | Aramalı maç seçici (300+ maçlık `<select>` mobilde kullanılmaz), "başladı" rozeti | Orta | S |
| J11 | Kupon detay sayfası `/kupondas/[id]` (paylaşılabilir), mobil yapışkan taslak çubuğu, taslak `sessionStorage`'da (oturum düşse de kaybolmasın), boş durum ve "bu maçta oran yok" mesajları, sekme erişilebilirliği (`aria-pressed`), akış otomatik yenileme + sayfalama | Düşük | S |
| J12 | Bildirimler (kupon sonuçlandı / arkadaş kupon yazdı) — yeni altyapı, onay | Düşük | M |

### FAZ K — İY oran panosu

- **K-1 (Orta, M):** Hafta sonu ~36–38 maçın sadece 12–14'ü yükleniyor (8 sn bekleme × Semaphore(4) × medyan 2,3 sn); Next `revalidate: 60` eksik listeyi önbellekte tutuyor; eşzamanlı ikinci istekte o an yenilenen maçlar düşüyor (`routes_ht.py:48`); ağ çekilirken DB oturumu açık (`:53-54`); `wait_for` thread'i durdurmuyor. Değişiklik: oranlar I2 göreviyle önceden çekilir, sayfa **sadece DB'den** okur, eksik maçta "oran yükleniyor" yer tutucusu; `_inflight[mid]` paylaşılan görev; çekim oturum dışında; ayrı sınırlı executor.
- **K-2 (Orta, S–M; "çok fazla maç" şikâyeti):** varsayılan sıralama başlama saati ("olasılığa göre" ayrı seçenek); bitmiş maçlar altta/katlı; lig çipleri; zaman penceresi (sonraki 3 saat / bugün kalan); pazar seçimi (İY 1X2 / İY Ü/A); asgari olasılık kaydırıcısı; oran hareketi rozeti (açılıştan ≥%8 düşüş; veri `history`'de var); kompakt satır görünümü (maç · en güçlü seçim · oran · %), tıklayınca detay. Query param + sunucu bileşeninde süzme; backend değişmez.
- **K-3 (S):** Yarım kazanç "Kazandı", yarım kayıp "½" gösteriliyor (`routes_ht.py:154`) → `coupons.leg_return` ile ortak sınıflandırma. Asya çizgide "pct" kazanma olasılığı değil → etiket "ima olasılık (iade/yarım dahil)" + ipucu. 1X2 pay çıkarmada orantılı yerine power/Shin (favori/sürpriz yanlılığı).
- **K-4 (S):** Bitmiş günlerde `model_pct` sızıntılı (güncel model sonucu görmüş) → snapshot yoksa `None` veya başlama haftasının modeli.

### FAZ L — Frontend kalitesi

- **L1 (Yüksek, S/M):** İstemcide 401 → `/giris?next=…` yönlendirmesi (`lib/api.ts:35-37`; bugün Kupondaş "Henüz kupon yok", canlı sessiz eski veri gösteriyor); hata ve boş durum ayrı.
- **L2 (Yüksek, M):** Önbellekli fetch + yanıt şekli değişince çökme sınıfı (/iy olayı tek değildi). Uç bazlı hafif doğrulayıcılar (`validHtStrategy`, `validPerformanceSummary`, `validMatchOdds`); yanıtlara şema sürümü ve önbellek anahtarına `?v=`; `/iy` ve `getBacktestSummary` (3600 sn) `no-store`/düşük; ortak `fmtNum` (null → "—"). Risk satırları: `iy/page.tsx` 79/120/145/147, `degerlendirme/page.tsx` 94/173/188/189, `PerformancePanel.tsx` 151/184/268, `LiveArchiveView.tsx` 93/152, `kupondas/page.tsx` 73–82.
- **L3 (Orta, S/M):** Mobilde çıkış, dil, gölge lig düğmeleri yok (`Sidebar.tsx:203-275` sadece masaüstü) → alt menüye "⋯ Daha fazla"; kısa mobil etiketler; sepet çubuğu içeriği örtmesin; 360 px e2e kontrolü.
- **L4 (Orta, M):** `lib/format.ts` (`formatPct`, `formatOdds`) — bugün 6 ayrı yüzde yardımcısı, `LiveArchiveView.fmtPct` dili hiç dikkate almıyor; `generateMetadata` sözlükten; backend hata kodları (`{"code":"period_closed"}`) ve frontend çevirisi (İngilizce arayüzde Türkçe hata görünüyor); ~25 ölü sözlük anahtarı silinsin; i18n parite testi CI'a.
- **L5 (Düşük, S):** Değerlendirme günlük canlı listesinde v1.1 "Model (0)" → `n>0` değilse parantez gizli; Pattern geçmişi sekmesi ana lig dışını sayıyor ve 2/2'de yeşil %100 → <10 karar nötr; sürüm sabitleri elle yazılı (`degerlendirme/page.tsx:553-564`) → backend'in `rule_versions` değeri başlıkta, uyuşmazlıkta uyarı; canlı sayfada REST hatası veri varken de gösterilsin; `React.memo(MatchCard)`; `validMatchList` bozuk satırı elesin, bütün listeyi düşürmesin; sadece aktif dilin sözlüğü pakete; `DetailedStats` tembel yükleme; giriş sayfasına dil düğmesi ve `<title>`.
- **L6 (Orta, M):** `degerlendirme/page.tsx` 861 satır → `components/evaluation/*`.

### FAZ M — Test, CI, belgeler

- **M1 (Orta, M):** Uçtan uca (E2E) job kesin kırık: CI'da backend yok, `proxy.ts` çerezsiz her sayfayı `/giris`'e atıyor, `playwright.config.ts` `localhost` ama sunucu `127.0.0.1`. → `baseURL`/`webServer.url` `127.0.0.1`; `e2e/auth.setup.ts` (`storageState`); job'a `services: postgres` + `alembic upgrade head` + `create-user e2e` + `serve &`. Ya da job açıkça devre dışı + not.
- **M2 (S):** `tests/test_migrations.py::test_alembic_single_head`; `pytest -W error::RuntimeWarning` (önce `begin_nested` AsyncMock taklidi düzeltilir — `prematch_v5.py:199`, `runner.py:212` testlerde savepoint içi çalışmıyor).
- **M3 (M):** Testi hiç olmayan modüller için test dosyaları (isimler `07-tests.md`'de): `test_routes_coupons.py`, `test_routes_auth.py` (çerez, 401, 429, çıkış, proxy arkasında kullanıcı başına kilit), `test_require_session.py` (public yollar, OPTIONS, iç anahtar, WS 4401), `test_routes_ht.py`, `test_odds_parser.py`, `test_ht_value` parmak izi, `goal_events` 45+2/penaltı/kendi kalesine; frontend `safe-next`, `proxy`, `kupondas-page`, `iy-page`.
- **M4 (S):** `requirements.txt`'ye not: scikit-learn 1.5.2 SciPy 1.18 ile bozulur (birlikte yükseltilmeli); `package.json` `"engines": {"node": ">=22"}` + `.nvmrc` (CI 22, yerel 24); `vite-tsconfig-paths` gereksiz (devDependency silme → onay).
- **M5 (S):** Tekrar eden kod: `_pmf` ×3 → `analysis/poisson_utils.py`; "3 saat" elle yazılmış (`events_cmds.py:36`, `odds_cmds.py:39`, `runner.py:558`) → `RESULT_KNOWN_DELAY`; "Europe/Istanbul" 9 dosyada → `istanbulToday()`; `repair-archive` kontrolleri satır içi kopya (testler üretim kodunu değil `repair.detect_issues` kopyasını sınıyor); ölü `live_model.invalidate_cond_table`, `pattern_d.invalidate_cache`.
- **M6 (M):** CLAUDE.md ve `backend/.env.example` (13 yanlış/eski madde): test sayıları (1127/313, E2E kırık); ağaçta eksik ~30 dosya; silinmiş Akıllı Kombolar anlatımı; "15 migration" → 27, head `a1n4j9k5f663`; Katman C ±1,0 (c4), Katman D d4 (λ, en yakın 200); "Production CANLI Render/Vercel" → yerel + Tailscale; GitHub Actions cron'ları kapalı (Task Scheduler); giriş var, premium yok, oran altyapısı var; "Kaldığımız Yer" 18 Ekim → güncel; eksik CLI komutları; Top Picks artık v5; BACKEND_URL notu; `.env.example`'da `PATTERN_C_TOLERANCE=0.5`, `PATTERN_D_TOP_N` eski, `AUTH_REQUIRED`/`INTERNAL_API_KEY`/`TRUSTED_PROXIES` yok.

### FAZ N — Anlık maçlar `inplay-v1` (gölge; gol dakikası çekimi bitince — K22)

**Araştırma sonucu (590 olaylı maç, hepsi 2026/27; parametreler geçici):**
- Kalan gol payı eğrisi F_rem(t) "kalan süre/90"dan her dakikada ve her pazarda iyi: t=60 0,388 (düz 0,333), t=80 0,166 (düz 0,111). Parçalı doğrusal, 5 parametre (b1=0,201, b2=−0,065, S1=0,0255, S2=0,0571), İY payı 0,442 sabit. Global şekil (ev/dep ve lig ayrımı gerekmiyor).
- Durum çarpanı M(d): −2 1,012 · −1 1,072 · 0 0,993 · +1 0,989 · +2 0,999 (6.126 maçlık İY örnekleminden yarıya çekilmiş). Güç üssü γ=0,06. Kendi kırmızı kartı ×0,65 (karar askıya alınır).
- Model: λ_rem = λ_ft × F_rem(t) × M(d) × (λ_taraf/λ_rakip)^γ; λ_ft başlama haftasının modelinden (sızıntısız).
- Test kümesinde her kontrol noktasında V3 > V2 ≥ V1 > V0; lig ortalaması (LIG) ve COND geride → **COND kullanılmaz**. Kalibre (87,5 → 89,4; 92,4 → 92,0; 98,2 → 98,1).
- İY'de mevcut live-poisson ile eşdeğer → **İY için yeni kayıt yazılmaz**.
- ≥%85 kararların %88–99'u "skordan belli"; piyasa bu seçimlere ortanca 1,05 adil oran veriyor ve 1X2'de modelden iyi (log-loss 0,672 vs 0,744). **Değer iddiası yok.**
- Hacim ~14,6 maç/gün; maç başına ~8,3 önemsiz + ~0,5 önemli karar → **100 önemli tekil karar ~6 hafta**.

**Adımlar:**
1. (S) Pano alan 12/13'ün kırmızı kart olduğunu doğrula (mevcut pano yanıtı + goal_events; uyuşmazsa dondurma anında maç başına bir olay sayfası).
2. (S) `source_board.parse_source_board` → `FixtureScore.red_home/red_away`; `live_snapshot` korusun; test.
3. (M) Migration: `prediction_ledger` + `prediction_backtest` `checkpoint_min SMALLINT NULL`; tekillik kısıtına `checkpoint_min` (NULLS NOT DISTINCT; eski satırlar NULL); `_LEDGER_SOURCES` + `'inplay'`; kronoloji CHECK `source='inplay' AND as_of > kickoff_time AND checkpoint_min IS NOT NULL`; `performance.decision_key`'e `checkpoint_min`.
4. (M) `app/analysis/inplay.py`: `RULE_PARAMS` (şekil, M(d), γ, eşik 85, pazarlar MS 1X2/ÇŞ/Ü-A 1.5/2.5/3.5, kontrol noktaları 15/30/60/70/80, pencere, kırmızı politikası, **takım modeli parmak izi**), `frem`, `rates`, `predict`, `decide`, `ledger_rows`, `rule_params_fingerprint` + sabitlenmiş test.
5. (M) `app/api/inplay_ledger.py`: `run_inplay_tick(snapshot)` izleyici turundan; gözlenen dakika m ∈ [t, t+5] → m ile hesapla (`late = m > t+2`); kaçarsa yazma, **geriye doldurma yok**; skor iki ardışık turda aynı; pano/canlı sayfa çelişkisi → atla; kırmızı → yok; 2. yarıda sadece gerçek saat (tahmini dakika ±5 dk belirsiz).
6. (M) `backtest-ledger --strategy inplay --checkpoints …` + `live-freeze --minute 67 --score 1-0` (asla yazmaz).
7. (S) Kalite kontrolü: `update-scores`'a `backfill-goal-events --since bugün−3`; dondurulmuş skor/dakika olaylarla uyuşmazsa geçersiz.
8. (M) Değerlendirme `scope=inplay`; kontrol noktası × pazar; **önemli ve önemsiz için ayrı karne**.
9. (M) `routes_inplay.py` (`GET /api/inplay`, `/api/inplay/{id}`, `WS /ws/inplay`; yük şeması `09-inplay.md`).
10. (L) Frontend `/anlik` "Anlık maçlar": dakika rozeti (tahminiyse "≈"), skor, kırmızı ikonu, "kalan beklenen gol", MS 1/X/2 çubukları, ÇŞ, Ü/A (kesinleşenler gri), bilgi satırları (kalan sürede gol %, sıradaki gol, KG); **varsayılan sadece "model katkısı" kararları**; "skordan belli (piyasa ~1,01–1,10)" kapalı gri grup; "Deneysel" (başlama ve İY dışı), "veri eski", "Kırmızı kart: tahmin askıda" rozetleri; menü linki.
11. (M) Gol çekimi bitince (~7.800 maç) yeniden uydur: 2024/25 ile eğit, 2025/26 ile test; lig bazında İY payı, M(d) × dönem, γ; değişirse `inplay-v2`, eskisi gölgede.

### FAZ O — Yeni gölge kural fikirleri (hepsi gölge, 100 karar sonrası karne)

| Kural | Fikir | Kanıt / beklenti | Doğrulama |
|---|---|---|---|
| `live-poisson-v1.2-trivial-tag` | H3: "İY skoru zaten söylüyor" rozeti | kararların ~%90'ı önemsiz; değerli ~%10 beklenen ~%88 | 100 değerli karar, Wilson aralığı 87,9'u kapsar |
| `live-cond-filter-v1` | COND ≥%85 ama Poisson <%85 → "lig geçmişi yüksek, takımlar desteklemiyor" uyarısı | 3 yılda bu dilim %81,4 tutuyor, ~88 gösteriyor | gerçek isabetin üst sınırı COND'un gösterdiğinin altında |
| `live-comeback-v1` | İY 1 farkla geride olan ama maç öncesi açık güçlü takım | λ(geride)/λ(önde) ≥2,2: 109 maç, geride kazanır %43,1, kaybetmez %70,6, 2Y gol %79,8; <0,8: 1.224 maç %6,8 / %24,8 | önce #14/#15 backtest satırlarında bu dilimin kalibrasyonu; uygunsa live-2h "geride 2Y gol" eşiği 70 → 65 ve ≥2,2 için ÇŞ "orta güven" gölge karar |
| `market-summary-v3` | H1 | kalibrasyon farkı +6 → 0±3 | pazar başına ≥100 karar |
| `ft-display-v5.1` | H5 kademe + K15 "yalnız model" | high, medium'dan ≥5 puan iyi | #12 tekrar oynatma + gölge karne |
| `ft-display-v6-mkt` | I6 piyasa karışımı | log-loss ≤ piyasa + 0,002 | MS oran doldurma sonrası Şub–Haz ayar, Ağu+ test |

### FAZ P — Kapsam genişletme (kararlar K15–K17)

- **P1 — "yalnız model" analizi (L, K15):** `filtering.py` H2H <5 için `model_only`; `runner.py` sadece A3 (+ λ) hesaplar; v5/Poisson çalışır; `ft-display-v5.1` gölgede + backtest. Ana ligde maçların ~%28'i, 2. liglerde %70–96'sı bugün bu kurala takılıyor.
- **P2 — Lig partisi (K16):** League Two (30 günde 58 maç, H2H geçişi %50), Çekya 1. Lig (25, 8/8), Eerste Divisie (34, %61), Yunanistan (20, 6/6), Polonya (26, %71) — toplam ~114 etkin maç/30 gün, kurulum ~8–11 saat (5 sezon), sonra λ + recompute. Ön koşul F7. Yedekler: Suudi, Avusturya, Danimarka; Norveç/İsveç kış boşluğu nedeniyle sonra. Sezon derinliği `list-leagues` / `fetch_league_seasons` ile önce doğrulanmalı.
- **P3 — Gölge → ekran terfi süreci:** (1) veri: ≥5 sezon, son 3 sezonda pattern+λ ≥%95, H2H geçişi ≥%60, skor p90 <6 saat, alias testi, oran kapsaması ≥%80; (2) sızıntısız backtest: lig başı ≥300 v5 + ≥300 canlı karar, gösterilen-gerçek fark ≤2 puan; (3) gerçek gölge: havuz ≥100 tekil karar "yolunda/üstünde", lig tek başına ≥30 ve "altında" değil; (4) sahip kararı + `audit_log` + CLAUDE.md. **Teknik ön koşul:** `MAIN_LEAGUES` → `DISPLAY_LEAGUES` (ekran) + `POOL_LEAGUES` (ortak havuzlar); terfi sadece ekranı değiştirir, havuza ekleme ayrı karar ve sürüm; lig başına `promoted_at`, değerlendirme kapsamı kayıt tarihine göre.
- **P4 — Avrupa kupaları (K17):** 30 günde UCL 27, UEL 36, UECL 36 maç (gerçekte ~130). Gerekenler: ligler arası takım gücü (lig ofsetli hiyerarşik model, L) veya oran-prior (Şubat 2026 öncesi oran yok); ayrı yarışma arşivi (5 sezon ~2.500 maç; 2024 format kırılması); `TRACKED_CUPS` beyaz listesi; AET/penaltı ayrımı (B2); P1 şart. Riskler: kalibrasyon, ortak havuzlara sızıntı, iki ayaklı eşleşmeler, rotasyon, az örneklem (~1 sezon). Seçenek B (arşiv + canlı COND gölge, ~1 hafta) en düşük riskli başlangıç.

---

## 5. Önerilen sıralama

| Sıra | İş | Bağımlılık | Not |
|---|---|---|---|
| 0 | Bölüm 3 (uyku alışkanlığı vb.) | — | Bugün, kod yok |
| 1 | **A1 + A2** Kupondaş kapanış (K2) | — | Kupondaş açık olduğu için ilk iş |
| 2 | **B1** update-scores dayanıklılık | — | S, yüksek etki |
| 3 | **B4** canlı kayıt pencereleri + **B3** tek seferlik temizlik (K8, K10) | — | |
| 4 | **D1** görev ayarları + **D2** sarmalayıcı ara düzeltme + **D3** D: yedeği | yönetici PowerShell | |
| 5 | **F1–F5** pipeline (akşam ertesi gün, takip önce, "?" lig adı, champions, sıfır-parse) | K14 | |
| 6 | **C2** parmak izleri + **C1** COND penceresi + yeni gölge sürümleri | K9; C1 ölçümü G8'den sonra kesinleşir | Kural değişikliği → sürüm + gölge |
| 7 | **B2** durum haritası / erteleme / void | — | M |
| 8 | **Faz G** arşiv sonrası runbook | arşiv bitmeli | A3 (DB portu) bu pencerede |
| 9 | **J1, J3, J4, J5, J2** Kupondaş doğruluk | A1 | |
| 10 | **H1, H2** ekran dürüstlüğü | K7, K21 | S |
| 11 | **Faz E** paylaşım (E1–E7, E9) | A3, K1, K5 | Bitince Tailscale linki verilebilir |
| 12 | **D4** sağlık + ölü adam, **D2** kalıcı denetleyici, **D5** | K12 | |
| 13 | **L1, L2** frontend kalite + **M1–M3** testler | — | |
| 14 | **I1–I3** oran altyapısı | K11, uzun işler bitmeli | |
| 15 | **K-1, K-2** İY panosu | I2 | |
| 16 | **J6, J8, J9, J10** Kupondaş genişleme | K4 | |
| 17 | **Faz N** inplay-v1 | gol çekimi bitmeli, K22 | ~6 hafta gölge ölçüm |
| 18 | **M6** CLAUDE.md + `.env.example` | — | Her faz sonunda da güncellenir |
| 19 | **Faz O, P** gölge fikirler, kapsam genişletme | K15–K17 | |
| 20 | Kalan Orta/Düşük maddeler (B5–B7, F6–F11, H4–H5, I4–I6, L3–L6, M4–M5, E8, J7, J11, J12, K-3, K-4) | — | |

---

## 6. Doğrulama protokolü (her faz sonunda)

1. `cd backend; python -m pytest -q` ve `python -m ruff check app/ tests/` yeşil.
2. `cd frontend; npx vitest run`, `npx tsc --noEmit`, `npx eslint .` temiz; paylaşım fazından sonra `npm run build` (dev sunucusu kapalıyken).
3. Kural değiştiyse: sabitlenmiş parmak izi testi kırılmış ve yeni sürümle güncellenmiş olmalı; yeni sürüm gölgede yazılıyor mu (`prediction_ledger` sorgusu).
4. Kupondaş: biten İY'ye kupon denemesi → 409 (test ortamında); kısmi kayıp "kısmi kayıp" görünür.
5. Operasyon: uyut/uyandır → backend 1 dk'da ayakta; görev geçmişi kayıt tutuyor; `netstat` 5433/5432/3000/8000 sadece 127.0.0.1.
6. Paylaşım öncesi: `npm audit --omit=dev` kritik yok; `curl -H "X-Forwarded-For: 1.2.3.4"` sonrası backend log'unda 127.0.0.1; `/giris?next=/%5Cevil.com` → `/bulten`; backend kapalıyken sahte çerezle `/bulten` → 503/307; arkadaşın cihazından 5433/8000/3000 kapalı.
7. Değerlendirme sayfası: karneler API ile birebir; kapsama oranı görünür.

---

## 7. Ölçüm özeti (28 Ekim, ana ligler, tekil karar)

| Kural | Ekranda mı | Karar | İsabet | Gösterilen | Hüküm |
|---|---|---|---|---|---|
| live-poisson-v1.1 | evet | 2 | 2/2 | 96,5 | veri toplanıyor |
| live-poisson-v1 (bitti) | gölge | 68 | 97,1 | 91,8 | veri toplanıyor |
| live-arch-v2 | onay rozeti | 56 | 89,3 | 92,6 | veri toplanıyor |
| live-2h-v1 | gölge | 17 | 88,2 | 81,8 | veri toplanıyor |
| ft-display-v5 | evet (Top Picks) | 29 | 58,6 | 55,7 | veri toplanıyor (lig favorisi 44,8) |
| ft-display-v4.1 | gölge | 34 | 55,9 | 54,1 | veri toplanıyor |
| market-summary-v2 | evet (Ana Pazar) | 1.460 | 48,1 | 54,5 | **beklentinin altında** |
| live-ms-v1 | gölge | 198 | 65,7 | 66,1 | yolunda (tabana göre −2,7) |
| live-arch-v1 | eski | 123 | 75,6 | 98,0 | beklentinin altında |
| ht-display-v1 | deneme | 0 çözülmüş | — | — | — |

Backtest uyumu: Poisson #11 %91,8 · v2 #13 %92,2 · v5 #12 %62,7 · live-2h #14 %84,7 — canlı değerlerin hepsi bu aralıklarda. Tahmini 100 karara ulaşma: Poisson ~2 hafta, v5 ~3–4 hafta, live-2h ~5–6 hafta.

**Oran (piyasa) karşılaştırması:** maç öncesi log-loss piyasa 0,9792 / v5 0,9961 (fark +0,017, aralık sıfırı içermiyor); v5 seçimleri kapanış oranında −%2,6 [−7,9; +2,8], kapanış çizgisi değeri −0,27 puan; karışım w=0,2 piyasadan farksız; "model ≥X fazla" kuralları testte negatif; oran hareketi bilgi eklemiyor; canlı 1X2 işaretlerinde ortalama gerçek oran 1,057, başa baş 1,062. Yaklaşık 40 varyant denendi, hiçbiri testte pozitif değil.

---

## 8. Ekler

- Ajan notları: `docs/audit-2026-10-28/01-backend.md` … `11-scraper.md`.
- Ajanların ölçüm betikleri ve ham çıktıları oturum geçici klasöründe kaldı (repoya alınmadı); yeniden üretmek gerekirse notlarda dosya adları ve yöntem yazılı.
- Bu plan Sprint 93'ün bekleyenlerini (DB portu, inplay-v1, arşiv sonrası işler) de kapsar; Sprint 91 / 92 planlarındaki açık maddeler buraya taşınmıştır.
