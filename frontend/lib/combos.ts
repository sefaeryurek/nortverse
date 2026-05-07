// Akıllı kombinasyon kuponu — Top Picks'ten otomatik 2/3/4-5 leg kombolar üretir.
// Joint olasılık: bağımsızlık varsayımıyla ∏ p_i (kullanıcıya "≈" ile yaklaşıklık belirtilir).

import type { Pick } from "./confidence";
import { resolveConflicts } from "./confidence";

export interface Combo {
  legs: Pick[];
  jointProb: number;        // 0..1
  estDecimalOdds: number;   // 1/jointProb
  tier: "double" | "triple" | "super";
  avgConfidence: number;
  avgPct: number;
}

// Bir leg seçildiğinde aynı "domain"den ikinci leg yasaklanır.
// Domain: mantıksal olarak ilişkili pazarlar grubu (aynı doğal olayı parçalı şekilde tarifleyen).
// Farklı domain'lerden alınan leg'ler bağımsızlık varsayımına daha uyumlu.
const DOMAIN_OF: Record<string, string> = {
  // Maç sonucu domeni — sonuç türevleri burada toplanır
  result: "match_result",
  dc: "match_result",
  fark: "match_result",
  hnd_a10: "match_result",
  hnd_h10: "match_result",
  hnd_a20: "match_result",
  hnd_h20: "match_result",

  // İY/MS bağımsız bir domain — sonuçla kombo izinli
  iy_ms: "iy_ms",

  // Toplam gol domeni
  ou_15: "total_goals",
  ou_25: "total_goals",
  ou_35: "total_goals",
  gol_aralik: "total_goals",

  // Karşılıklı gol domeni
  kg: "btts",

  // Hibrit kombineler — ayrı domain'lere konur ki birden fazla seçilebilsin
  ms_25_combo: "ms_combo_25",
  ms_15_combo: "ms_combo_15",
  ms_kg_combo: "ms_combo_kg",

  // Taraf gol toplamları
  ev_05: "home_total",
  ev_15: "home_total",
  ev_25: "home_total",
  dep_05: "away_total",
  dep_15: "away_total",
  dep_25: "away_total",

  // İY ve 2Y dönem alt pazarları
  iy_05: "iy_total",
  iy_15: "iy_total",
  iki_yari_15: "iki_yari",

  ht_result: "ht_period",
  ht_dc: "ht_period",
  ht_kg: "ht_period",

  h2_result: "h2_period",
  h2_kg: "h2_period",

  encok_yari: "encok_yari",
};

function domainOf(marketKey: string): string {
  return DOMAIN_OF[marketKey] ?? marketKey;
}

// Mantıksal sert çelişki çiftleri (field bazlı). Aynı domain filtresine ek güvence.
// Örnek: "Alt 2.5" ile "4-5 Gol" çelişir; ikisi farklı marketKey ama domain'de "total_goals" yakalar zaten.
// Bu liste DOMAIN_OF dışında kalan keskin çelişkileri yakalamak için.
const HARD_CONFLICTS: Array<[string, string]> = [
  // Berabere ile her sonuç çelişir
  ["result_x_pct", "fark_ev1_pct"],
  ["result_x_pct", "fark_ev2_pct"],
  ["result_x_pct", "fark_ev3p_pct"],
  ["result_x_pct", "fark_dep1_pct"],
  ["result_x_pct", "fark_dep2_pct"],
  ["result_x_pct", "fark_dep3p_pct"],
  ["result_1_pct", "fark_ber_pct"],
  ["result_2_pct", "fark_ber_pct"],
];

function fieldsConflict(a: string, b: string): boolean {
  for (const [x, y] of HARD_CONFLICTS) {
    if ((x === a && y === b) || (x === b && y === a)) return true;
  }
  return false;
}

function pickConflict(p: Pick, others: Pick[]): boolean {
  const dom = domainOf(p.marketKey);
  for (const o of others) {
    if (domainOf(o.marketKey) === dom) return true;
    if (fieldsConflict(p.field as string, o.field as string)) return true;
  }
  return false;
}

function jointProb(legs: Pick[]): number {
  return legs.reduce((acc, p) => acc * (p.pct / 100), 1);
}

function avgPct(legs: Pick[]): number {
  if (legs.length === 0) return 0;
  return legs.reduce((s, p) => s + p.pct, 0) / legs.length;
}

function avgConf(legs: Pick[]): number {
  if (legs.length === 0) return 0;
  return legs.reduce((s, p) => s + p.confidence, 0) / legs.length;
}

/**
 * Greedy: confidence sırasıyla picks'ten leg seçer, her ekleme öncesi domain ve hard-conflict kontrolü yapar.
 * targetCount kadar leg toplandığında veya pick havuzu bittiğinde durur.
 */
function buildLegs(picks: Pick[], minPct: number, targetCount: number): Pick[] {
  const sorted = [...picks].sort((a, b) => b.confidence - a.confidence);
  const legs: Pick[] = [];
  for (const p of sorted) {
    if (p.pct < minPct) continue;
    if (pickConflict(p, legs)) continue;
    legs.push(p);
    if (legs.length >= targetCount) break;
  }
  return legs;
}

/**
 * 3 hazır kombo üretir: çift (2 leg), üçlü (3 leg), süper (4-5 leg).
 * Pick'ler önce resolveConflicts ile aynı marketKey çakışmasından arındırılır.
 */
export function generateCombos(picks: Pick[]): Combo[] {
  const cleaned = resolveConflicts(picks);
  const out: Combo[] = [];

  // Çift kombo: 2 leg, ≥%75 — en güvenli
  const doubleLegs = buildLegs(cleaned, 75, 2);
  if (doubleLegs.length === 2) {
    const jp = jointProb(doubleLegs);
    out.push({
      legs: doubleLegs,
      jointProb: jp,
      estDecimalOdds: 1 / jp,
      tier: "double",
      avgConfidence: avgConf(doubleLegs),
      avgPct: avgPct(doubleLegs),
    });
  }

  // Üçlü kombo: 3 leg, ≥%70 — dengeli
  const tripleLegs = buildLegs(cleaned, 70, 3);
  if (tripleLegs.length === 3) {
    const jp = jointProb(tripleLegs);
    out.push({
      legs: tripleLegs,
      jointProb: jp,
      estDecimalOdds: 1 / jp,
      tier: "triple",
      avgConfidence: avgConf(tripleLegs),
      avgPct: avgPct(tripleLegs),
    });
  }

  // Süper kombo: 4-5 leg, ≥%75, sadece yüksek eşleşme (≥20 maç) ve avg confidence ≥0.65
  const minMatchCount = Math.max(
    cleaned.reduce((m, p) => Math.max(m, p.matchCountA, p.matchCountB), 0),
  );
  if (minMatchCount >= 20) {
    const superLegs = buildLegs(cleaned, 75, 5);
    if (superLegs.length >= 4 && avgConf(superLegs) >= 0.65) {
      const jp = jointProb(superLegs);
      out.push({
        legs: superLegs,
        jointProb: jp,
        estDecimalOdds: 1 / jp,
        tier: "super",
        avgConfidence: avgConf(superLegs),
        avgPct: avgPct(superLegs),
      });
    }
  }

  return out;
}

export function comboTierLabel(tier: Combo["tier"]): string {
  if (tier === "double") return "Çift Kombo";
  if (tier === "triple") return "Üçlü Kombo";
  return "Süper Kombo";
}

export function comboTierAccent(tier: Combo["tier"]): { color: string; bg: string; border: string } {
  if (tier === "double") return { color: "#22c55e", bg: "#031a0d", border: "#14532d" };
  if (tier === "triple") return { color: "#38bdf8", bg: "#031624", border: "#0c4a6e" };
  return { color: "#fbbf24", bg: "#1c1200", border: "#92400e" };
}
