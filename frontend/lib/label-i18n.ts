import type { Locale } from "./i18n";

/**
 * Pazar/seçim etiketleri kaynakta Türkçe tanımlı (confidence.ts, DetailedStats).
 * İngilizce modda önce tam ifadeler, sonra kelimeler çevrilir.
 */
const PHRASES: [RegExp, string][] = [
  [/^Ev (\d\+?) fark$/, "Home by $1"],
  [/^Dep (\d\+?) fark$/, "Away by $1"],
  [/^Ev (\d\+?)$/, "Home by $1"],
  [/^Dep (\d\+?)$/, "Away by $1"],
  [/^Ev İki Yarıda$/, "Home scores in both halves"],
  [/^Dep İki Yarıda$/, "Away scores in both halves"],
  [/^İki Yarı (Alt|Üst)$/, "Both halves $1"],
  [/^(\d)\. Yarı$/, "$1st half"],
];

const WORDS: [RegExp, string][] = [
  [/Karşılıklı Gol/g, "Both Teams to Score"],
  [/Çifte Şans/g, "Double Chance"],
  [/Toplam Gol Aralığı/g, "Total Goals Range"],
  [/En Çok Gol Olacak Yarı/g, "Highest Scoring Half"],
  [/Handikap/g, "Handicap"],
  [/KG Var/g, "BTTS Yes"],
  [/KG Yok/g, "BTTS No"],
  [/Berabere/g, "Draw"],
  [/Eşit/g, "Equal"],
  [/Alt/g, "Under"],
  [/Üst/g, "Over"],
  [/\bEv\b/g, "Home"],
  [/\bDep\b/g, "Away"],
  [/\bGol\b/g, "Goals"],
  [/İY/g, "HT"],
  [/\b2Y\b/g, "2H"],
  [/1\.Y/g, "1H"],
  [/2\.Y/g, "2H"],
  [/Yarı Sonucu/g, "Half Result"],
  [/Sonucu/g, "Result"],
  [/ fark/g, " margin"],
];

export function localizeLabel(label: string, locale: Locale): string {
  if (locale !== "en" || !label) return label;
  for (const [pattern, replacement] of PHRASES) {
    if (pattern.test(label)) return label.replace(pattern, replacement);
  }
  let out = label;
  for (const [pattern, replacement] of WORDS) out = out.replace(pattern, replacement);
  return out;
}
