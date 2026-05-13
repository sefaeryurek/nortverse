import { describe, it, expect } from "vitest";
import { generateCombos, comboTierLabel, comboTierAccent } from "@/lib/combos";
import { makePick } from "./fixtures";

describe("generateCombos — temel davranış", () => {
  it("boş picks → boş combo", () => {
    expect(generateCombos([])).toEqual([]);
  });

  it("tek leg yetmez (çift kombo en az 2 leg ister)", () => {
    const picks = [makePick({ marketKey: "result", pct: 80, confidence: 0.8 })];
    expect(generateCombos(picks)).toEqual([]);
  });

  it("2 leg ≥%75 ve farklı domain → çift kombo üretilir", () => {
    const picks = [
      makePick({
        marketKey: "result",
        selectionLabel: "1",
        field: "result_1_pct",
        pct: 80,
        confidence: 0.8,
        matchCountA: 30,
      }),
      makePick({
        marketKey: "kg",
        selectionLabel: "KG Var",
        field: "kg_var_pct",
        pct: 78,
        confidence: 0.75,
        matchCountA: 30,
      }),
    ];
    const combos = generateCombos(picks);
    expect(combos).toHaveLength(1);
    expect(combos[0].tier).toBe("double");
    expect(combos[0].legs).toHaveLength(2);
    expect(combos[0].jointProb).toBeCloseTo(0.8 * 0.78, 3);
    expect(combos[0].estDecimalOdds).toBeCloseTo(1 / (0.8 * 0.78), 2);
  });

  it("aynı domain'den iki leg çift kombo'ya birlikte alınmaz (result + dc her ikisi match_result)", () => {
    const picks = [
      makePick({
        marketKey: "result",
        selectionLabel: "1",
        field: "result_1_pct",
        pct: 80,
        confidence: 0.85,
        matchCountA: 30,
      }),
      makePick({
        marketKey: "dc",
        selectionLabel: "1X",
        field: "dc_1x_pct",
        pct: 90,
        confidence: 0.9,
        matchCountA: 30,
      }),
    ];
    const combos = generateCombos(picks);
    // İkisi de match_result domeninde → tek leg seçilir, çift kombo oluşmaz
    expect(combos).toEqual([]);
  });

  it("hard conflict (result_x + fark_ev1) çift kombo'da birlikte yer almaz", () => {
    // fark zaten match_result domeninde, ama daha açık conflict ile spesifik test:
    // Burada conflict birinden DOMAIN_OF de yakalar; HARD_CONFLICTS keskin ek güvence.
    const picks = [
      makePick({
        marketKey: "result",
        selectionLabel: "X",
        field: "result_x_pct",
        pct: 80,
        confidence: 0.85,
        matchCountA: 30,
      }),
      makePick({
        marketKey: "fark",
        selectionLabel: "Ev 1 fark",
        field: "fark_ev1_pct",
        pct: 78,
        confidence: 0.8,
        matchCountA: 30,
      }),
    ];
    const combos = generateCombos(picks);
    expect(combos).toEqual([]);
  });

  it("3 leg ≥%70 farklı domain → üçlü kombo da üretilir", () => {
    const picks = [
      makePick({
        marketKey: "result",
        selectionLabel: "1",
        field: "result_1_pct",
        pct: 78,
        confidence: 0.78,
        matchCountA: 25,
      }),
      makePick({
        marketKey: "kg",
        selectionLabel: "KG Var",
        field: "kg_var_pct",
        pct: 76,
        confidence: 0.75,
        matchCountA: 25,
      }),
      makePick({
        marketKey: "ou_25",
        selectionLabel: "Üst 2.5",
        field: "ust_25_pct",
        pct: 72,
        confidence: 0.7,
        matchCountA: 25,
      }),
    ];
    const combos = generateCombos(picks);
    expect(combos.length).toBeGreaterThanOrEqual(1);
    const triple = combos.find((c) => c.tier === "triple");
    expect(triple).toBeDefined();
    expect(triple!.legs).toHaveLength(3);
    expect(triple!.jointProb).toBeCloseTo(0.78 * 0.76 * 0.72, 3);
  });

  it("süper kombo eşleşme<20 → üretilmez", () => {
    const picks = Array.from({ length: 5 }, (_, i) =>
      makePick({
        marketKey: ["result", "kg", "ou_25", "iy_ms", "ms_25_combo"][i],
        selectionLabel: `s${i}`,
        field: ["result_1_pct", "kg_var_pct", "ust_25_pct", "iy_ms_11_pct", "ms1_ust25_pct"][i] as
          | "result_1_pct"
          | "kg_var_pct"
          | "ust_25_pct"
          | "iy_ms_11_pct"
          | "ms1_ust25_pct",
        pct: 80,
        confidence: 0.8,
        matchCountA: 10, // <20 → süper kombo blok
      }),
    );
    const combos = generateCombos(picks);
    expect(combos.find((c) => c.tier === "super")).toBeUndefined();
  });

  it("süper kombo: 4-5 leg, eşleşme ≥20, avgConfidence ≥0.65 → üretilir", () => {
    const picks = [
      makePick({
        marketKey: "result",
        selectionLabel: "1",
        field: "result_1_pct",
        pct: 80,
        confidence: 0.8,
        matchCountA: 25,
      }),
      makePick({
        marketKey: "kg",
        selectionLabel: "KG Var",
        field: "kg_var_pct",
        pct: 78,
        confidence: 0.78,
        matchCountA: 25,
      }),
      makePick({
        marketKey: "ou_25",
        selectionLabel: "Üst 2.5",
        field: "ust_25_pct",
        pct: 76,
        confidence: 0.75,
        matchCountA: 25,
      }),
      makePick({
        marketKey: "iy_ms",
        selectionLabel: "1/1",
        field: "iy_ms_11_pct",
        pct: 76,
        confidence: 0.72,
        matchCountA: 25,
      }),
    ];
    const combos = generateCombos(picks);
    expect(combos.find((c) => c.tier === "super")).toBeDefined();
  });
});

describe("comboTierLabel", () => {
  it.each([
    ["double", "Çift Kombo"],
    ["triple", "Üçlü Kombo"],
    ["super", "Süper Kombo"],
  ] as const)("tier=%s → %s", (tier, expected) => {
    expect(comboTierLabel(tier)).toBe(expected);
  });
});

describe("comboTierAccent", () => {
  it("her tier için color/bg/border döner", () => {
    const tiers = ["double", "triple", "super"] as const;
    for (const t of tiers) {
      const accent = comboTierAccent(t);
      expect(accent.color).toMatch(/^#[0-9a-f]{6}$/i);
      expect(accent.bg).toMatch(/^#[0-9a-f]{6}$/i);
      expect(accent.border).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
