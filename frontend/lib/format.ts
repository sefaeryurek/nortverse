/** Sayı biçimleri (Sprint 94 H2; L4'te diğer yüzde/oran yardımcıları da buraya toplanacak). */

/**
 * API'den gelen sayıyı güvenle yazar: null / eksik / NaN → "—" (Sprint 94 L2). Yanıt şekli değişince
 * `undefined.toFixed()` sayfayı çökertiyordu (/iy olayı).
 */
export function fmtNum(value: number | null | undefined, digits: number): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

/**
 * Olasılığa karşılık gelen "adil" bahis oranı (1/p, bahisçi payı yok). %92 → 1,09.
 * Değer iddiası değil: gerçek oran bunun altındaysa (çoğu yüksek olasılıklı seçimde öyle) seçimin bahis değeri yoktur.
 */
export function fairOdds(pct: number | null | undefined, locale: string): string | null {
  if (pct == null || !Number.isFinite(pct) || pct <= 0 || pct > 100) return null;
  const odds = (100 / pct).toFixed(2);
  return locale === "en" ? odds : odds.replace(".", ",");
}
