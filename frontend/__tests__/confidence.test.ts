import { describe, it, expect } from "vitest";
import {
  getMarketSummary,
} from "@/lib/confidence";
import { makePatternResult } from "./fixtures";

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
