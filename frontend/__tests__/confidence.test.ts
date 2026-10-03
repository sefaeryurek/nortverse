import { describe, it, expect } from "vitest";
import {
  computeConfidence,
  confidenceTier,
  getMarketSummary,
  getMarkets,
  getTrendsBoost,
} from "@/lib/confidence";
import type { TrendBlock, TrendsData } from "@/lib/types";
import { makePatternResult } from "./fixtures";

function makeTrendBlock(overrides: Partial<TrendBlock> = {}): TrendBlock {
  return {
    label: "Son 10 ev maçı",
    sample_size: 10,
    win_pct: 50,
    draw_pct: 25,
    loss_pct: 25,
    kg_var_pct: 50,
    over_25_pct: 50,
    avg_goals_for: 1.5,
    avg_goals_against: 1.2,
    last_n_results: ["G", "M", "G", "B", "G"],
    ...overrides,
  };
}

function makeTrends(overrides: Partial<TrendsData> = {}): TrendsData {
  return {
    home_form: makeTrendBlock(),
    away_form: makeTrendBlock(),
    h2h: makeTrendBlock(),
    ...overrides,
  };
}

describe("computeConfidence", () => {
  it("matchCount=0 → confidence 0 (volumeWeight 0)", () => {
    expect(computeConfidence(80, 0, 1.0, false)).toBe(0);
  });

  it("matchCount=30 → volumeWeight ~1.0, formül pct/100 × weight", () => {
    const c = computeConfidence(80, 30, 1.0, false);
    expect(c).toBeCloseTo(0.8, 1);
  });

  it("dual bonus 1.25x uygulanır", () => {
    const single = computeConfidence(70, 30, 1.0, false, 1.0, "result");
    const dual = computeConfidence(70, 30, 1.0, true, 1.0, "result");
    expect(dual / single).toBeCloseTo(1.25, 2);
  });

  it("dual bonus sadece result-ilişkili pazarlara uygulanır", () => {
    const singleResult = computeConfidence(70, 30, 1.0, false, 1.0, "result");
    const dualResult = computeConfidence(70, 30, 1.0, true, 1.0, "result");
    expect(dualResult / singleResult).toBeCloseTo(1.25, 2);
    const dualOu = computeConfidence(70, 30, 1.0, true, 1.0, "ou_25");
    expect(dualOu).toBeCloseTo(0.7, 2);
  });

  it("marketWeight çarpan olarak iner (0.7 → %70 confidence)", () => {
    const full = computeConfidence(80, 30, 1.0, false);
    const reduced = computeConfidence(80, 30, 0.7, false);
    expect(reduced / full).toBeCloseTo(0.7, 2);
  });

  it("küçük örneklemde (5 maç) confidence düşük volume weight ile azalır", () => {
    const small = computeConfidence(80, 5, 1.0, false);
    const big = computeConfidence(80, 30, 1.0, false);
    expect(small).toBeLessThan(big);
  });

  it("100+ eşleşmede volumeWeight azalmaya başlar (diminishing returns)", () => {
    const c100 = computeConfidence(80, 100, 1.0, false);
    const c200 = computeConfidence(80, 200, 1.0, false);
    const c300 = computeConfidence(80, 300, 1.0, false);
    expect(c200).toBeLessThan(c100);
    expect(c300).toBeLessThan(c200);
    expect(c300).toBeGreaterThan(0);
  });

  it("tekli arşivde O/U confidence %50 düşer", () => {
    const dual = computeConfidence(80, 30, 1.0, true, 1.0, "ou_25");
    const single = computeConfidence(80, 30, 1.0, false, 1.0, "ou_25", "A");
    expect(single).toBeLessThan(dual * 0.6);
  });

  it("tekli arşivde KG confidence %50 düşer", () => {
    const dual = computeConfidence(80, 30, 1.0, true, 1.0, "kg");
    const single = computeConfidence(80, 30, 1.0, false, 1.0, "kg", "A");
    expect(single).toBeLessThan(dual * 0.6);
  });

  it("tekli arşivde result pazarına O/U cezası uygulanmaz", () => {
    const withPenalty = computeConfidence(80, 30, 1.0, false, 1.0, "result", "A");
    const base = (80 / 100) * 1.0 * 1.0 * 1.03;
    expect(withPenalty).toBeCloseTo(base, 2);
  });
});

describe("confidenceTier", () => {
  it.each([
    [0.95, "high"],
    [0.90, "high"],
    [0.89, "medium"],
    [0.70, "medium"],
    [0.69, "low"],
    [0.50, "low"],
    [0.49, "muted"],
    [0, "muted"],
  ])("c=%s → %s", (input, expected) => {
    expect(confidenceTier(input)).toBe(expected);
  });
});

describe("getMarketSummary", () => {
  it("null patternlerde sadece varolanı kullanır", () => {
    const a = makePatternResult({
      match_count: 20,
      result_1_pct: 60,
      result_x_pct: 20,
      result_2_pct: 20,
    });
    const rows = getMarketSummary(a, null, "ft");
    const r = rows.find((x) => x.marketKey === "result");
    expect(r).toBeDefined();
    expect(r!.winnerA?.selectionLabel).toBe("1");
    expect(r!.winnerB).toBeNull();
    expect(r!.agreement).toBe(false);
  });

  it("ikisi de aynı seçimi öneriyorsa agreement=true", () => {
    const a = makePatternResult({ match_count: 20, kg_var_pct: 70, kg_yok_pct: 30 });
    const b = makePatternResult({ match_count: 15, kg_var_pct: 65, kg_yok_pct: 35 });
    const rows = getMarketSummary(a, b, "ft");
    const kg = rows.find((x) => x.marketKey === "kg");
    expect(kg!.agreement).toBe(true);
    expect(kg!.winnerA?.selectionLabel).toBe("KG Var");
    expect(kg!.winnerB?.selectionLabel).toBe("KG Var");
  });

  it("ht periyodunda ou_25 gösterilmez (excludePeriods)", () => {
    const a = makePatternResult({ match_count: 20, alt_25_pct: 60, ust_25_pct: 40 });
    const rows = getMarketSummary(a, null, "ht");
    expect(rows.find((x) => x.marketKey === "ou_25")).toBeUndefined();
  });
});

describe("getMarkets", () => {
  it("MARKETS dizisi readonly döner, en az ana pazarları içerir", () => {
    const markets = getMarkets();
    const keys = markets.map((m) => m.key);
    expect(keys).toContain("result");
    expect(keys).toContain("dc");
    expect(keys).toContain("ou_25");
    expect(keys).toContain("kg");
    expect(keys).toContain("iy_ms");
  });
});

describe("getTrendsBoost", () => {
  it("trends=null → 1.0 (boost yok)", () => {
    expect(getTrendsBoost("result", "1", null)).toBe(1.0);
  });

  it("eşik altı home_form.win_pct → boost yok (1.0)", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ win_pct: 60 }) });
    expect(getTrendsBoost("result", "1", trends)).toBe(1.0);
  });

  it("home_form.win_pct ≥ 65 → result_1 için 1.10 boost", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ win_pct: 70 }) });
    expect(getTrendsBoost("result", "1", trends)).toBe(1.1);
  });

  it("away_form.win_pct ≥ 65 → result_2 için 1.10 boost", () => {
    const trends = makeTrends({ away_form: makeTrendBlock({ win_pct: 80 }) });
    expect(getTrendsBoost("result", "2", trends)).toBe(1.1);
  });

  it("h2h.draw_pct ≥ 40 → result_x için 1.07 boost", () => {
    const trends = makeTrends({ h2h: makeTrendBlock({ draw_pct: 45 }) });
    expect(getTrendsBoost("result", "X", trends)).toBe(1.07);
  });

  it("h2h.kg_var_pct ≥ 60 → kg+KG Var için 1.10 boost", () => {
    const trends = makeTrends({ h2h: makeTrendBlock({ kg_var_pct: 70 }) });
    expect(getTrendsBoost("kg", "KG Var", trends)).toBe(1.1);
  });

  it("home_form.over_25_pct ≥ 55 → ou_25+Üst 2.5 için 1.08 boost", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ over_25_pct: 60 }) });
    expect(getTrendsBoost("ou_25", "Üst 2.5", trends)).toBe(1.08);
  });

  it("bilinmeyen marketKey/selection → 1.0", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ win_pct: 90 }) });
    expect(getTrendsBoost("unknown_market", "X", trends)).toBe(1.0);
    expect(getTrendsBoost("result", "Y", trends)).toBe(1.0);
  });

  it("ilgili trend bloğu null → 1.0 (örn. home_form yok)", () => {
    const trends: TrendsData = { home_form: null, away_form: makeTrendBlock(), h2h: null };
    expect(getTrendsBoost("result", "1", trends)).toBe(1.0);
    expect(getTrendsBoost("result", "X", trends)).toBe(1.0); // h2h null
  });

  it("home_form.win_pct ≤ 30 → result_1 için 0.88 penaltı", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ win_pct: 25 }) });
    expect(getTrendsBoost("result", "1", trends)).toBeCloseTo(0.88, 2);
  });

  it("home_form.loss_pct ≥ 50 → result_1 için 0.85 penaltı", () => {
    const trends = makeTrends({ home_form: makeTrendBlock({ win_pct: 20, loss_pct: 55 }) });
    const factor = getTrendsBoost("result", "1", trends);
    expect(factor).toBeCloseTo(0.88 * 0.85, 2);
  });

  it("away_form.win_pct ≤ 30 → result_2 için 0.88 penaltı", () => {
    const trends = makeTrends({ away_form: makeTrendBlock({ win_pct: 20 }) });
    expect(getTrendsBoost("result", "2", trends)).toBeCloseTo(0.88, 2);
  });
});

