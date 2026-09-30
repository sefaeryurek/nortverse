import { describe, it, expect } from "vitest";
import { canCombineFields } from "@/lib/selection-compatibility";

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
});
