import type { PatternResult } from "./types";
import { type Period, periodLabels } from "./labels";

export interface Pick {
  marketKey: string;       // çelişki gruplaması için (örn. "result", "ou_25")
  field: keyof PatternResult; // ham alan adı
  marketLabel: string;     // UI: "Maç Sonucu", "2.5 Alt/Üst"
  selectionLabel: string;  // UI: "1", "Üst 2.5", "X/1"
  pct: number;             // birleştirilmiş yüzde (AB için ortalama, tek için kendi)
  pctA: number | null;
  pctB: number | null;
  matchCountA: number;
  matchCountB: number;
  marketWeight: number;
  archive: "A" | "B" | "AB";
  confidence: number;      // 0..~1.15
}

const DUAL_BONUS = 1.15;
const DUAL_THRESHOLD = 65;

function volumeWeight(matchCount: number): number {
  if (matchCount <= 0) return 0;
  return Math.min(1.0, Math.log(matchCount + 1) / Math.log(30));
}

export function computeConfidence(
  pct: number,
  matchCount: number,
  marketWeight: number,
  isDual: boolean,
): number {
  const base = (pct / 100) * volumeWeight(matchCount) * marketWeight;
  return isDual ? base * DUAL_BONUS : base;
}

interface FieldSpec {
  field: keyof PatternResult;
  selection: string;
}

interface MarketSpec {
  key: string;
  label: (lbl: ReturnType<typeof periodLabels>) => string;
  weight: number;
  fields: FieldSpec[];
  ftOnly?: boolean;       // sadece FT periyodunda hesaplanır
  excludePeriods?: Period[]; // bu periyotlarda hiç gösterilme (iddaa'da 1.01 olan ya da açılmayan pazarlar)
  ftZeroCheck?: keyof PatternResult; // bu alan 0 ise pazarı atla (HT verisi yoksa)
}

const MARKETS: MarketSpec[] = [
  // === ANA PAZARLAR (weight 1.0) ===
  {
    key: "result",
    label: (l) => l.sonuc,
    weight: 1.0,
    fields: [
      { field: "result_1_pct", selection: "1" },
      { field: "result_x_pct", selection: "X" },
      { field: "result_2_pct", selection: "2" },
    ],
  },
  {
    key: "dc",
    label: () => "Çifte Şans",
    weight: 1.0,
    fields: [
      { field: "dc_1x_pct", selection: "1X" },
      { field: "dc_x2_pct", selection: "X2" },
      { field: "dc_12_pct", selection: "12" },
    ],
  },
  {
    key: "ou_25",
    label: () => "2.5 Alt/Üst",
    weight: 1.0,
    excludePeriods: ["ht", "h2"], // IY/2Y'de iddaa açmaz (Alt 1.01, Üst yok)
    fields: [
      { field: "alt_25_pct", selection: "Alt 2.5" },
      { field: "ust_25_pct", selection: "Üst 2.5" },
    ],
  },
  {
    key: "kg",
    label: () => "Karşılıklı Gol",
    weight: 1.0,
    fields: [
      { field: "kg_var_pct", selection: "KG Var" },
      { field: "kg_yok_pct", selection: "KG Yok" },
    ],
  },

  // === İY/MS — sadece FT (weight 0.9) ===
  {
    key: "iy_ms",
    label: () => "İY / MS",
    weight: 0.9,
    ftOnly: true,
    ftZeroCheck: "iy_ms_xx_pct",
    fields: [
      { field: "iy_ms_11_pct", selection: "1/1" },
      { field: "iy_ms_1x_pct", selection: "1/X" },
      { field: "iy_ms_12_pct", selection: "1/2" },
      { field: "iy_ms_x1_pct", selection: "X/1" },
      { field: "iy_ms_xx_pct", selection: "X/X" },
      { field: "iy_ms_x2_pct", selection: "X/2" },
      { field: "iy_ms_21_pct", selection: "2/1" },
      { field: "iy_ms_2x_pct", selection: "2/X" },
      { field: "iy_ms_22_pct", selection: "2/2" },
    ],
  },

  // === HANDİKAP DOĞAL HAT (weight 0.9) ===
  {
    key: "hnd_a10",
    label: () => "Handikap (0:1)",
    weight: 0.9,
    excludePeriods: ["ht", "h2"], // IY/2Y'de iddaa handikap açmaz
    fields: [
      { field: "hnd_a10_1_pct", selection: "1" },
      { field: "hnd_a10_x_pct", selection: "X" },
      { field: "hnd_a10_2_pct", selection: "2" },
    ],
  },
  {
    key: "hnd_h10",
    label: () => "Handikap (1:0)",
    weight: 0.9,
    excludePeriods: ["ht", "h2"], // IY/2Y'de iddaa handikap açmaz
    fields: [
      { field: "hnd_h10_1_pct", selection: "1" },
      { field: "hnd_h10_x_pct", selection: "X" },
      { field: "hnd_h10_2_pct", selection: "2" },
    ],
  },

  // === MS+ KOMBİNELER (weight 0.7) ===
  {
    key: "ms_25_combo",
    label: (l) => l.combo25,
    weight: 0.7,
    excludePeriods: ["ht", "h2"], // 2.5 hattı IY/2Y'de açılmadığı için kombineler de anlamsız
    fields: [
      { field: "ms1_alt25_pct", selection: "1 + Alt 2.5" },
      { field: "ms1_ust25_pct", selection: "1 + Üst 2.5" },
      { field: "msx_alt25_pct", selection: "X + Alt 2.5" },
      { field: "msx_ust25_pct", selection: "X + Üst 2.5" },
      { field: "ms2_alt25_pct", selection: "2 + Alt 2.5" },
      { field: "ms2_ust25_pct", selection: "2 + Üst 2.5" },
    ],
  },
  {
    key: "ms_15_combo",
    label: (l) => l.combo15,
    weight: 0.7,
    fields: [
      { field: "ms1_alt15_pct", selection: "1 + Alt 1.5" },
      { field: "ms1_ust15_pct", selection: "1 + Üst 1.5" },
      { field: "msx_alt15_pct", selection: "X + Alt 1.5" },
      { field: "msx_ust15_pct", selection: "X + Üst 1.5" },
      { field: "ms2_alt15_pct", selection: "2 + Alt 1.5" },
      { field: "ms2_ust15_pct", selection: "2 + Üst 1.5" },
    ],
  },
  {
    key: "ms_kg_combo",
    label: (l) => l.comboKg,
    weight: 0.7,
    fields: [
      { field: "ms1_kg_var_pct", selection: "1 + KG Var" },
      { field: "ms1_kg_yok_pct", selection: "1 + KG Yok" },
      { field: "msx_kg_var_pct", selection: "X + KG Var" },
      { field: "msx_kg_yok_pct", selection: "X + KG Yok" },
      { field: "ms2_kg_var_pct", selection: "2 + KG Var" },
      { field: "ms2_kg_yok_pct", selection: "2 + KG Yok" },
    ],
  },
  {
    key: "fark",
    label: (l) => l.fark,
    weight: 0.7,
    fields: [
      { field: "fark_ev1_pct", selection: "Ev 1 fark" },
      { field: "fark_ev2_pct", selection: "Ev 2 fark" },
      { field: "fark_ev3p_pct", selection: "Ev 3+ fark" },
      { field: "fark_ber_pct", selection: "Berabere" },
      { field: "fark_dep1_pct", selection: "Dep 1 fark" },
      { field: "fark_dep2_pct", selection: "Dep 2 fark" },
      { field: "fark_dep3p_pct", selection: "Dep 3+ fark" },
    ],
  },

  // === İKİNCİL (weight 0.6) ===
  {
    key: "ou_15",
    label: () => "1.5 Alt/Üst",
    weight: 0.6,
    fields: [
      { field: "alt_15_pct", selection: "Alt 1.5" },
      { field: "ust_15_pct", selection: "Üst 1.5" },
    ],
  },
  {
    key: "ou_35",
    label: () => "3.5 Alt/Üst",
    weight: 0.6,
    excludePeriods: ["ht", "h2"], // IY/2Y'de 3.5 hattı yok
    fields: [
      { field: "alt_35_pct", selection: "Alt 3.5" },
      { field: "ust_35_pct", selection: "Üst 3.5" },
    ],
  },
  {
    key: "ev_05",
    label: () => "Ev 0.5 Alt/Üst",
    weight: 0.6,
    fields: [
      { field: "ev_alt_05_pct", selection: "Ev Alt 0.5" },
      { field: "ev_ust_05_pct", selection: "Ev Üst 0.5" },
    ],
  },
  {
    key: "ev_15",
    label: () => "Ev 1.5 Alt/Üst",
    weight: 0.6,
    fields: [
      { field: "ev_alt_15_pct", selection: "Ev Alt 1.5" },
      { field: "ev_ust_15_pct", selection: "Ev Üst 1.5" },
    ],
  },
  {
    key: "ev_25",
    label: () => "Ev 2.5 Alt/Üst",
    weight: 0.6,
    excludePeriods: ["ht", "h2"], // Ev 1Y/2Y'de 3 gol atması neredeyse imkansız → bahis yok
    fields: [
      { field: "ev_alt_25_pct", selection: "Ev Alt 2.5" },
      { field: "ev_ust_25_pct", selection: "Ev Üst 2.5" },
    ],
  },
  {
    key: "dep_05",
    label: () => "Dep 0.5 Alt/Üst",
    weight: 0.6,
    fields: [
      { field: "dep_alt_05_pct", selection: "Dep Alt 0.5" },
      { field: "dep_ust_05_pct", selection: "Dep Üst 0.5" },
    ],
  },
  {
    key: "dep_15",
    label: () => "Dep 1.5 Alt/Üst",
    weight: 0.6,
    fields: [
      { field: "dep_alt_15_pct", selection: "Dep Alt 1.5" },
      { field: "dep_ust_15_pct", selection: "Dep Üst 1.5" },
    ],
  },
  {
    key: "dep_25",
    label: () => "Dep 2.5 Alt/Üst",
    weight: 0.6,
    excludePeriods: ["ht", "h2"], // Dep 1Y/2Y'de 3 gol atması neredeyse imkansız → bahis yok
    fields: [
      { field: "dep_alt_25_pct", selection: "Dep Alt 2.5" },
      { field: "dep_ust_25_pct", selection: "Dep Üst 2.5" },
    ],
  },

  // === FT PERİYODUNDA HT/H2 ALT ===
  {
    key: "iy_05",
    label: () => "İY 0.5 Alt/Üst",
    weight: 0.6,
    ftOnly: true,
    ftZeroCheck: "iy_ust_05_pct",
    fields: [
      { field: "iy_alt_05_pct", selection: "İY Alt 0.5" },
      { field: "iy_ust_05_pct", selection: "İY Üst 0.5" },
    ],
  },
  {
    key: "iy_15",
    label: () => "İY 1.5 Alt/Üst",
    weight: 0.6,
    ftOnly: true,
    ftZeroCheck: "iy_ust_05_pct",
    fields: [
      { field: "iy_alt_15_pct", selection: "İY Alt 1.5" },
      { field: "iy_ust_15_pct", selection: "İY Üst 1.5" },
    ],
  },
  {
    key: "iki_yari_15",
    label: () => "İki Yarı 1.5 Alt/Üst",
    weight: 0.5,
    ftOnly: true,
    ftZeroCheck: "iy_ust_05_pct",
    fields: [
      { field: "iki_yari_alt15_pct", selection: "İki Yarı Alt" },
      { field: "iki_yari_ust15_pct", selection: "İki Yarı Üst" },
    ],
  },
  {
    key: "ht_result",
    label: () => "1. Yarı Sonucu",
    weight: 0.7,
    ftOnly: true,
    ftZeroCheck: "ht_result_1_pct",
    fields: [
      { field: "ht_result_1_pct", selection: "İY 1" },
      { field: "ht_result_x_pct", selection: "İY X" },
      { field: "ht_result_2_pct", selection: "İY 2" },
    ],
  },
  {
    key: "ht_dc",
    label: () => "1. Yarı Çifte Şans",
    weight: 0.7,
    ftOnly: true,
    ftZeroCheck: "ht_result_1_pct",
    fields: [
      { field: "ht_dc_1x_pct", selection: "İY 1X" },
      { field: "ht_dc_x2_pct", selection: "İY X2" },
      { field: "ht_dc_12_pct", selection: "İY 12" },
    ],
  },
  {
    key: "h2_result",
    label: () => "2. Yarı Sonucu",
    weight: 0.7,
    ftOnly: true,
    ftZeroCheck: "h2_result_1_pct",
    fields: [
      { field: "h2_result_1_pct", selection: "2Y 1" },
      { field: "h2_result_x_pct", selection: "2Y X" },
      { field: "h2_result_2_pct", selection: "2Y 2" },
    ],
  },
  {
    key: "ht_kg",
    label: () => "1. Yarı KG",
    weight: 0.6,
    ftOnly: true,
    ftZeroCheck: "ht_kg_var_pct",
    fields: [
      { field: "ht_kg_var_pct", selection: "İY KG Var" },
      { field: "ht_kg_yok_pct", selection: "İY KG Yok" },
    ],
  },
  {
    key: "h2_kg",
    label: () => "2. Yarı KG",
    weight: 0.6,
    ftOnly: true,
    ftZeroCheck: "h2_kg_var_pct",
    fields: [
      { field: "h2_kg_var_pct", selection: "2Y KG Var" },
      { field: "h2_kg_yok_pct", selection: "2Y KG Yok" },
    ],
  },

  // === DAHA DÜŞÜK ÖNEMLİ ===
  {
    key: "gol_aralik",
    label: () => "Toplam Gol Aralığı",
    weight: 0.5,
    fields: [
      { field: "gol_01_pct", selection: "0-1 Gol" },
      { field: "gol_23_pct", selection: "2-3 Gol" },
      { field: "gol_45_pct", selection: "4-5 Gol" },
      { field: "gol_6p_pct", selection: "6+ Gol" },
    ],
  },
  {
    key: "encok_yari",
    label: () => "En Çok Gol Olacak Yarı",
    weight: 0.4,
    ftOnly: true,
    ftZeroCheck: "encok_gol_1y_pct",
    fields: [
      { field: "encok_gol_1y_pct", selection: "1. Yarı" },
      { field: "encok_gol_esit_pct", selection: "Eşit" },
      { field: "encok_gol_2y_pct", selection: "2. Yarı" },
    ],
  },
  {
    key: "hnd_a20",
    label: () => "Handikap (0:2)",
    weight: 0.5,
    excludePeriods: ["ht", "h2"], // IY/2Y'de iddaa handikap açmaz
    fields: [
      { field: "hnd_a20_1_pct", selection: "1" },
      { field: "hnd_a20_x_pct", selection: "X" },
      { field: "hnd_a20_2_pct", selection: "2" },
    ],
  },
  {
    key: "hnd_h20",
    label: () => "Handikap (2:0)",
    weight: 0.5,
    excludePeriods: ["ht", "h2"], // IY/2Y'de iddaa handikap açmaz
    fields: [
      { field: "hnd_h20_1_pct", selection: "1" },
      { field: "hnd_h20_x_pct", selection: "X" },
      { field: "hnd_h20_2_pct", selection: "2" },
    ],
  },
];

export function getMarkets(): readonly MarketSpec[] {
  return MARKETS;
}

function isMarketActive(market: MarketSpec, period: Period, sample: PatternResult): boolean {
  if (market.ftOnly && period !== "ft") return false;
  if (market.excludePeriods?.includes(period)) return false;
  if (market.ftZeroCheck && (sample[market.ftZeroCheck] as number) <= 0) return false;
  return true;
}

interface RawSelection {
  marketKey: string;
  marketLabel: string;
  selectionLabel: string;
  field: keyof PatternResult;
  weight: number;
  pct: number;
}

function extractRaw(result: PatternResult, period: Period): RawSelection[] {
  const lbl = periodLabels(period);
  const out: RawSelection[] = [];
  for (const m of MARKETS) {
    if (!isMarketActive(m, period, result)) continue;
    const label = m.label(lbl);
    for (const f of m.fields) {
      out.push({
        marketKey: m.key,
        marketLabel: label,
        selectionLabel: f.selection,
        field: f.field,
        weight: m.weight,
        pct: result[f.field] as number,
      });
    }
  }
  return out;
}

/**
 * İki arşivi (Pattern B = "A", Pattern C = "B") birleştirip Pick listesi üretir.
 * Aynı (marketKey, selectionLabel) kombinasyonu ikisinde de varsa archive="AB" olur ve dual_bonus uygulanır.
 */
export function buildPicks(
  patternA: PatternResult | null,
  patternB: PatternResult | null,
  period: Period,
): Pick[] {
  const rawA = patternA ? extractRaw(patternA, period) : [];
  const rawB = patternB ? extractRaw(patternB, period) : [];
  const matchCountA = patternA?.match_count ?? 0;
  const matchCountB = patternB?.match_count ?? 0;

  const mapKey = (r: RawSelection) => `${r.marketKey}|${r.selectionLabel}`;
  const aMap = new Map<string, RawSelection>();
  for (const r of rawA) aMap.set(mapKey(r), r);
  const bMap = new Map<string, RawSelection>();
  for (const r of rawB) bMap.set(mapKey(r), r);

  const allKeys = new Set<string>([...aMap.keys(), ...bMap.keys()]);
  const picks: Pick[] = [];

  for (const k of allKeys) {
    const a = aMap.get(k);
    const b = bMap.get(k);
    const ref = a ?? b!;
    const pctA = a?.pct ?? null;
    const pctB = b?.pct ?? null;
    const dual = a !== undefined && b !== undefined && pctA! >= DUAL_THRESHOLD && pctB! >= DUAL_THRESHOLD;

    let archive: "A" | "B" | "AB";
    let combinedPct: number;
    let combinedMatchCount: number;
    if (a && b) {
      archive = "AB";
      combinedPct = (pctA! + pctB!) / 2;
      combinedMatchCount = Math.max(matchCountA, matchCountB);
    } else if (a) {
      archive = "A";
      combinedPct = pctA!;
      combinedMatchCount = matchCountA;
    } else {
      archive = "B";
      combinedPct = pctB!;
      combinedMatchCount = matchCountB;
    }

    const confidence = computeConfidence(combinedPct, combinedMatchCount, ref.weight, dual);

    picks.push({
      marketKey: ref.marketKey,
      field: ref.field,
      marketLabel: ref.marketLabel,
      selectionLabel: ref.selectionLabel,
      pct: combinedPct,
      pctA,
      pctB,
      matchCountA,
      matchCountB,
      marketWeight: ref.weight,
      archive,
      confidence,
    });
  }

  return picks;
}

/**
 * Aynı marketKey'de en yüksek confidence olanı bırakır.
 * (örn: result_1, result_x, result_2'den sadece en yüksek olan)
 */
export function resolveConflicts(picks: Pick[]): Pick[] {
  const byMarket = new Map<string, Pick>();
  for (const p of picks) {
    const cur = byMarket.get(p.marketKey);
    if (!cur || p.confidence > cur.confidence) {
      byMarket.set(p.marketKey, p);
    }
  }
  return Array.from(byMarket.values()).sort((a, b) => b.confidence - a.confidence);
}

export interface TopPicksOptions {
  minConfidence?: number;  // default 0.55
  limit?: number;          // default 8
  minPct?: number;         // override: dinamik eşik yerine sabit eşik
  matchCount?: number;     // dinamik eşik için örneklem boyutu (yoksa picks'ten en yüksek alınır)
}

export interface TopPicksResult {
  picks: Pick[];
  effectiveMinPct: number; // gerçekten uygulanan eşik (UI gösterimi için)
  matchCount: number;
}

/**
 * Örneklem boyutuna göre minimum yüzde eşiğini ayarlar.
 * 5 maç → ~74%, 15 maç → ~70%, 30 maç → ~68%, 50 maç → ~66%, 100+ → ~64%
 * Wilson lower bound benzeri pragmatik formül.
 */
export function dynamicMinPct(matchCount: number): number {
  if (matchCount <= 0) return 80;
  return Math.max(64, 80 - Math.log10(matchCount + 1) * 8);
}

/**
 * Top Picks: çelişkisiz, confidence sırasına göre en güçlü tahminler.
 * Eşleşme sayısı ile dinamik eşik: küçük örneklemde daha yüksek pct ister, büyük örneklemde daha gevşek.
 */
export function getTopPicks(picks: Pick[], opts: TopPicksOptions = {}): TopPicksResult {
  const minConf = opts.minConfidence ?? 0.55;
  const limit = opts.limit ?? 8;
  const matchCount =
    opts.matchCount ?? picks.reduce((m, p) => Math.max(m, p.matchCountA, p.matchCountB), 0);
  const minPct = opts.minPct ?? dynamicMinPct(matchCount);
  const filtered = resolveConflicts(picks)
    .filter((p) => p.confidence >= minConf && p.pct >= minPct)
    .slice(0, limit);
  return {
    picks: filtered,
    effectiveMinPct: minPct,
    matchCount,
  };
}

export interface MarketSummaryRow {
  marketKey: string;
  marketLabel: string;
  // Her arşivin kendi en yüksek seçimi
  winnerA: { selectionLabel: string; pct: number } | null;
  winnerB: { selectionLabel: string; pct: number } | null;
  agreement: boolean; // ikisi de aynı seçimi öneriyor mu?
}

const SUMMARY_MARKET_KEYS = [
  "result",
  "dc",
  "ou_25",
  "kg",
  "iy_ms",
  "hnd_a10",
  "hnd_h10",
  "ms_25_combo",
  "fark",
];

/**
 * Piyasa Özeti: sadece ana pazarların kazananlarını Arşiv-A ve Arşiv-B için ayrı gösterir.
 */
export function getMarketSummary(
  patternA: PatternResult | null,
  patternB: PatternResult | null,
  period: Period,
): MarketSummaryRow[] {
  const lbl = periodLabels(period);
  const rows: MarketSummaryRow[] = [];

  for (const key of SUMMARY_MARKET_KEYS) {
    const market = MARKETS.find((m) => m.key === key);
    if (!market) continue;
    const sampleForCheck = patternA ?? patternB;
    if (!sampleForCheck) continue;
    if (!isMarketActive(market, period, sampleForCheck)) continue;

    const pickWinner = (result: PatternResult | null) => {
      if (!result) return null;
      let best: { selectionLabel: string; pct: number } | null = null;
      for (const f of market.fields) {
        const pct = result[f.field] as number;
        if (!best || pct > best.pct) {
          best = { selectionLabel: f.selection, pct };
        }
      }
      return best;
    };

    const winnerA = pickWinner(patternA);
    const winnerB = pickWinner(patternB);
    const agreement = !!winnerA && !!winnerB && winnerA.selectionLabel === winnerB.selectionLabel;

    rows.push({
      marketKey: key,
      marketLabel: market.label(lbl),
      winnerA,
      winnerB,
      agreement,
    });
  }

  return rows;
}

/**
 * Confidence'a göre renk: ≥0.80 yüksek (yeşil dolu), 0.65-0.79 orta (yeşil çerçeve),
 * 0.50-0.64 düşük (gri çerçeve), <0.50 silik.
 */
export type ConfidenceTier = "high" | "medium" | "low" | "muted";
export function confidenceTier(c: number): ConfidenceTier {
  if (c >= 0.8) return "high";
  if (c >= 0.65) return "medium";
  if (c >= 0.5) return "low";
  return "muted";
}
