import type { Dictionary } from "./i18n";

/** Canlı arşiv pazar etiketi: "MS ÇŞ", "2Y 0.5" … (anahtar yoksa ham değer). */
export function liveMarketLabel(period: string, market: string, t: Dictionary): string {
  return (t.live.archive.markets as Record<string, string>)[`${period}_${market}`] ?? `${period} ${market}`;
}

/** Seçim etiketi: 1/X/2/1X… olduğu gibi; under/over/yes/no sözlükten. */
export function liveSelectionLabel(selection: string, t: Dictionary): string {
  return (t.live.archive.selections as Record<string, string>)[selection] ?? selection;
}
