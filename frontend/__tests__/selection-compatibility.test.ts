import { describe, it, expect } from "vitest";
import { canCombineFields } from "@/lib/selection-compatibility";
import { generateCombos } from "@/lib/combos";
import { makePick } from "./fixtures";

describe("score compatibility", () => {
  it.each([
    ["kg_var_pct", "alt_15_pct"],
    ["result_1_pct", "ms2_ust25_pct"],
    ["iy_ms_12_pct", "ht_result_2_pct"],
    ["hnd_a10_1_pct", "alt_15_pct"],
    ["ev_alt_05_pct", "kg_var_pct"],
    ["result_1_pct", "future_unknown_pct"],
  ])("rejects incompatible or unknown fields: %s + %s", (a, b) => {
    expect(canCombineFields([a, b])).toBe(false);
  });
  it("checks the whole group, not just pairs", () => {
    const fields = ["result_1_pct", "kg_var_pct", "alt_25_pct"];
    expect(canCombineFields(fields.slice(0, 2))).toBe(true);
    expect(canCombineFields([fields[0], fields[2]])).toBe(true);
    expect(canCombineFields(fields.slice(1))).toBe(true);
    expect(canCombineFields(fields)).toBe(false);
  });
  it("keeps compatible selections even when they are statistically dependent", () => {
    expect(canCombineFields(["result_1_pct", "kg_var_pct", "ust_25_pct", "iy_ms_11_pct"])).toBe(true);
  });
  it("excludes impossible automatic combinations", () => {
    expect(generateCombos([
      makePick({ field: "kg_var_pct", marketKey: "kg", pct: 90 }),
      makePick({ field: "alt_15_pct", marketKey: "ou_15", pct: 90 }),
    ])).toEqual([]);
  });
  it("requires enough samples for every super combo selection", () => {
    const fields = ["result_1_pct", "kg_var_pct", "ust_25_pct", "iy_ms_11_pct"] as const;
    const keys = ["result", "kg", "ou_25", "iy_ms"];
    const picks = fields.map((field, i) => makePick({ field, marketKey: keys[i],
      pct: 85, confidence: 0.8, matchCountA: i === 0 ? 100 : 5 }));
    expect(generateCombos(picks).some((c) => c.tier === "super")).toBe(false);
  });
});
