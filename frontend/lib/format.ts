/** Sayı biçimleri (Sprint 94 H2; L4'te diğer yüzde/oran yardımcıları da buraya toplanacak). */

/**
 * Olasılığa karşılık gelen "adil" bahis oranı (1/p, bahisçi payı yok). %92 → 1,09.
 * Değer iddiası değil: gerçek oran bunun altındaysa (çoğu yüksek olasılıklı seçimde öyle) seçimin bahis değeri yoktur.
 */
export function fairOdds(pct: number | null | undefined, locale: string): string | null {
  if (pct == null || !Number.isFinite(pct) || pct <= 0 || pct > 100) return null;
  const odds = (100 / pct).toFixed(2);
  return locale === "en" ? odds : odds.replace(".", ",");
}
