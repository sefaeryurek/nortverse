import { describe, it, expect } from "vitest";
import {
  computeConfidence,
  dynamicMinPct,
  confidenceTier,
  resolveConflicts,
  buildPicks,
  getTopPicks,
  getMarketSummary,
  getMarkets,
} from "@/lib/confidence";
import { makePatternResult, makePick } from "./fixtures";

describe("dynamicMinPct", () => {
  it("matchCount=0 için 80 döner (sample yok → sıkı eşik)", () => {
    expect(dynamicMinPct(0)).toBe(80);
  });

  it("negatif matchCount güvenli (80 döner)", () => {
    expect(dynamicMinPct(-5)).toBe(80);
  });

  it("5 maç için ~74 (small sample, stricter)", () => {
    const v = dynamicMinPct(5);
    expect(v).toBeGreaterThan(73);
    expect(v).toBeLessThan(75);
  });

  it("30 maç için ~68", () => {
    const v = dynamicMinPct(30);
    expect(v).toBeGreaterThan(67);
    expect(v).toBeLessThan(69);
  });

  it("100 maç için ~64 floor'a yakın", () => {
    const v = dynamicMinPct(100);
    expect(v).toBeGreaterThanOrEqual(64);
    expect(v).toBeLessThan(65);
  });

  it("10000 maç için 64 floor (asla altına inmez)", () => {
    expect(dynamicMinPct(10000)).toBe(64);
  });
});

describe("computeConfidence", () => {
  it("matchCount=0 → confidence 0 (volumeWeight 0)", () => {
    expect(computeConfidence(80, 0, 1.0, false)).toBe(0);
  });

  it("matchCount=30 → volumeWeight ~1.0, formül pct/100 × weight", () => {
    const c = computeConfidence(80, 30, 1.0, false);
    expect(c).toBeCloseTo(0.8, 1);
  });

  it("dual bonus 1.15x uygulanır", () => {
    const single = computeConfidence(70, 30, 1.0, false);
    const dual = computeConfidence(70, 30, 1.0, true);
    expect(dual / single).toBeCloseTo(1.15, 2);
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
});

describe("confidenceTier", () => {
  it.each([
    [0.85, "high"],
    [0.8, "high"],
    [0.79, "medium"],
    [0.65, "medium"],
    [0.64, "low"],
    [0.5, "low"],
    [0.49, "muted"],
    [0, "muted"],
  ])("c=%s → %s", (input, expected) => {
    expect(confidenceTier(input)).toBe(expected);
  });
});

describe("resolveConflicts", () => {
  it("aynı marketKey'den en yüksek confidence olanı bırakır", () => {
    const picks = [
      makePick({ marketKey: "result", selectionLabel: "1", confidence: 0.6 }),
      makePick({ marketKey: "result", selectionLabel: "X", confidence: 0.8 }),
      makePick({ marketKey: "result", selectionLabel: "2", confidence: 0.5 }),
    ];
    const out = resolveConflicts(picks);
    expect(out).toHaveLength(1);
    expect(out[0].selectionLabel).toBe("X");
  });

  it("farklı marketKey'leri korur, confidence sırasına göre sıralar", () => {
    const picks = [
      makePick({ marketKey: "kg", selectionLabel: "KG Var", confidence: 0.55 }),
      makePick({ marketKey: "result", selectionLabel: "1", confidence: 0.85 }),
      makePick({ marketKey: "ou_25", selectionLabel: "Üst 2.5", confidence: 0.7 }),
    ];
    const out = resolveConflicts(picks);
    expect(out).toHaveLength(3);
    expect(out[0].marketKey).toBe("result");
    expect(out[1].marketKey).toBe("ou_25");
    expect(out[2].marketKey).toBe("kg");
  });

  it("boş input → boş output", () => {
    expect(resolveConflicts([])).toEqual([]);
  });
});

describe("buildPicks", () => {
  it("patternA null, patternB null → boş", () => {
    expect(buildPicks(null, null, "ft")).toEqual([]);
  });

  it("sadece patternA → tüm pick'ler archive='A'", () => {
    const a = makePatternResult({
      match_count: 20,
      result_1_pct: 60,
      result_x_pct: 25,
      result_2_pct: 15,
      kg_var_pct: 55,
      kg_yok_pct: 45,
    });
    const picks = buildPicks(a, null, "ft");
    expect(picks.length).toBeGreaterThan(0);
    expect(picks.every((p) => p.archive === "A")).toBe(true);
  });

  it("iki arşivde de eşleşme + her ikisi ≥%65 → archive='AB' ve dual bonus uygulanır", () => {
    const a = makePatternResult({ match_count: 20, result_1_pct: 70 });
    const b = makePatternResult({ match_count: 15, result_1_pct: 75 });
    const picks = buildPicks(a, b, "ft");
    const result1 = picks.find((p) => p.marketKey === "result" && p.selectionLabel === "1");
    expect(result1).toBeDefined();
    expect(result1!.archive).toBe("AB");
    expect(result1!.pct).toBeCloseTo(72.5, 1);
    expect(result1!.pctA).toBe(70);
    expect(result1!.pctB).toBe(75);

    // Dual bonus ile karşılaştır
    const singleConf = computeConfidence(72.5, 20, 1.0, false);
    const dualConf = computeConfidence(72.5, 20, 1.0, true);
    expect(result1!.confidence).toBeCloseTo(dualConf, 2);
    expect(result1!.confidence).toBeGreaterThan(singleConf);
  });

  it("ftOnly pazarlar (iy_ms) ht periyodunda yok", () => {
    const a = makePatternResult({ match_count: 20, iy_ms_11_pct: 50, ht_result_1_pct: 60 });
    const htPicks = buildPicks(a, null, "ht");
    expect(htPicks.find((p) => p.marketKey === "iy_ms")).toBeUndefined();
  });

  it("excludePeriods içeren pazar (ou_25) ht'de gizli, ft'de açık", () => {
    const a = makePatternResult({ match_count: 20, ust_25_pct: 65, alt_25_pct: 35 });
    const htPicks = buildPicks(a, null, "ht");
    expect(htPicks.find((p) => p.marketKey === "ou_25")).toBeUndefined();
    const ftPicks = buildPicks(a, null, "ft");
    expect(ftPicks.find((p) => p.marketKey === "ou_25")).toBeDefined();
  });
});

describe("getTopPicks", () => {
  it("boş picks → boş sonuç + effectiveMinPct (80 floor)", () => {
    const res = getTopPicks([]);
    expect(res.picks).toEqual([]);
    expect(res.effectiveMinPct).toBe(80);
    expect(res.matchCount).toBe(0);
  });

  it("dinamik eşik altındaki picks elenir", () => {
    const picks = [
      makePick({ marketKey: "result", pct: 60, confidence: 0.7, matchCountA: 30 }),
      makePick({ marketKey: "kg", pct: 80, confidence: 0.7, matchCountA: 30 }),
    ];
    const res = getTopPicks(picks);
    expect(res.effectiveMinPct).toBeLessThan(70);
    expect(res.picks).toHaveLength(1);
    expect(res.picks[0].marketKey).toBe("kg");
  });

  it("minConfidence eşiği uygulanır (default 0.55)", () => {
    const picks = [
      makePick({ marketKey: "result", pct: 90, confidence: 0.4, matchCountA: 30 }),
      makePick({ marketKey: "kg", pct: 90, confidence: 0.6, matchCountA: 30 }),
    ];
    const res = getTopPicks(picks);
    expect(res.picks).toHaveLength(1);
    expect(res.picks[0].marketKey).toBe("kg");
  });

  it("limit parametresi (default 8) uygulanır", () => {
    const picks = Array.from({ length: 15 }, (_, i) =>
      makePick({
        marketKey: `m${i}`,
        pct: 90,
        confidence: 0.7,
        matchCountA: 30,
      }),
    );
    const res = getTopPicks(picks);
    expect(res.picks).toHaveLength(8);
  });

  it("minPct override dinamik eşiği bastırır", () => {
    const picks = [makePick({ pct: 70, confidence: 0.7, matchCountA: 30 })];
    const tight = getTopPicks(picks, { minPct: 80 });
    expect(tight.picks).toHaveLength(0);
    const loose = getTopPicks(picks, { minPct: 60 });
    expect(loose.picks).toHaveLength(1);
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
