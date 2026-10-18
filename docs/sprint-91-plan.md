# Nortverse Sprint 91+ planı (7 ajan raporu, 2026-10-19)

## Kullanıcı kararları (2026-10-19)
- Canlı: live-arch-v2 hemen; Poisson modeli (live-poisson-v1) 1 hafta gölgede, sonra karşılaştırıp geçiş. scipy requirements.txt'ye açıkça sabitlenecek (zaten kurulu).
- Maç öncesi: Dixon-Coles (ft-display-v5) ana; v4 gölgede (kaydedilmeye devam); iki model aynı seçimde = yüksek kademe.
- Arşivler: ekranda kalsın, kararlardan çıksın. A3 → λ-uzayında en yakın 200 (liste en yakın 20 + tümü), A2 → sabit ±1.0; A1 aynı. PATTERN_ALGO_VERSION artırılır.
- Operasyon: backend oturum açılışında penceresiz başlasın; görev hatasında ekranda uyarı. (Uyandırma ve OneDrive kopyası seçilmedi.)

## Ana bulgular
- Arşivler canlıda "aynı lig + aynı İY skoru" tabanına bilgi katmıyor (lift ≈0). Maç öncesi A1 %41,4 < lig %43,5; A2 %42,7; A3 %44,2.
- A3 kök neden: oran(h,a)=f(h)+g(a); rastgele iki maç kosinüsü medyan 0,85 → 0,97 gevşek. λ-kNN Top-200 MS %50,7.
- live-arch-v1 %85+ gösterilen ~%98, gerçek %66 (n=1 %58); zayıf pazarlar: h2·result, h2·ou_15, ft·kg, h2·kg.
- 18 Ekim tekil: 93/123 (%76); normal 32/33, riskli 61/90 (aynı karar A1/A2/A3/Genel 4 kez sayılıyordu).
- Poisson-GLM canlı %85+: %92,8; LR(İY+Elo+lig) %92; DC maç öncesi %51,7 (fark≥10: %61), v4 %46-52.

## Fazlar
- Faz 0 (hata/dürüst sayım): tekil sayım; ertelenen maç senkronu (stale cache); maç sonrası "maç öncesi" kayıt koruması + 3026756'nın 23 kaydını geçersiz say; update_results maç başına hataya dayanıklı; geç kayıt işareti + canlı arşiv sadece devre arası; view cache anahtarı pattern hash; gün süzme matches.kickoff_time join; lig kaynağı tek yardımcı; pattern_as_of kickoff yoksa; özet gün/7 gün/tümü + ana lig filtresi + geçersizleri listeden çıkar; eksik testler.
- Faz 1 live-arch-v2: n<5 kaldır; 4 zayıf pazar kaldır; COND ≥%85 kapısı; çelişen işaretlerde büyük n kazanır; tek satır/seçim; ana sayı gerçekçi oran.
- Faz 2 live-poisson-v1 (gölge): DC λ + 2Y Poisson GLM (skor durumu); %85+ + "değerli" (COND<80); maç başına en iyi tek işaret; backtest kabul; 1 hafta gölge.
- Faz 3 ft-display-v5 DC: fark≥10, X değil; v4 gölgede; Ü/A-KG bilgi amaçlı.
- Faz 4 arşivler: karardan çıkar; A3 λ-kNN Top-200; A2 ±1.0 sabit; recompute.
- Faz 5 değerlendirme protokolü: tekil karne (beklenen vs gerçek, Wilson); ≥100 tekil işaret olmadan kural değişmez; üst sınır < beklenen → pazar askı; her değişiklik yeni sürüm + gölge; oran verisi yok → kârlılık iddiası yok.
- Faz 6 operasyon: backend autostart (logon, run-hidden, ensure-docker, IgnoreNew, restart); hata uyarısı (masaüstü not + msg).

## Raporlar/simülasyonlar
scratchpad: C:\Users\Sefa\AppData\Local\Temp\claude\c--Users-Sefa-Desktop-NORTVERSE---CODEX\af8bc0f9-3e53-4b58-99f8-9fd4897902ad\scratchpad\ (lib.py, eval_live.py, eval_prematch.py, sim.py, qstrat/)
