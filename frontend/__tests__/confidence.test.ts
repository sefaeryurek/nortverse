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
    expect(r!.winnerA1?.selectionLabel).toBe("1");
    expect(r!.winnerA2).toBeNull();
    expect(r!.agreement).toBe(false);
  });

  it("ikisi de aynı seçimi öneriyorsa agreement=true", () => {
    const a = makePatternResult({ match_count: 20, kg_var_pct: 70, kg_yok_pct: 30 });
    const b = makePatternResult({ match_count: 15, kg_var_pct: 65, kg_yok_pct: 35 });
    const rows = getMarketSummary(a, b, "ft");
    const kg = rows.find((x) => x.marketKey === "kg");
    expect(kg!.agreement).toBe(true);
    expect(kg!.winnerA1?.selectionLabel).toBe("KG Var");
    expect(kg!.winnerA2?.selectionLabel).toBe("KG Var");
  });

  it("A3 de uyuma sayılır: A1+A3 aynı seçimde → 2 arşiv uyumu", () => {
    const a = makePatternResult({ match_count: 20, result_1_pct: 60, result_x_pct: 20, result_2_pct: 20 });
    const c = makePatternResult({ match_count: 15, result_1_pct: 20, result_x_pct: 60, result_2_pct: 20 });
    const d = makePatternResult({ match_count: 25, result_1_pct: 55, result_x_pct: 25, result_2_pct: 20 });
    const r = getMarketSummary(a, c, "ft", d).find((x) => x.marketKey === "result")!;
    expect(r.agreementCount).toBe(2);
    expect(r.agreement).toBe(true);
    expect(r.winnerA3?.selectionLabel).toBe("1");
  });

  it("Ü/A 2.5 ve KG bilgi amaçlı işaretlenir, 1X2 değil", () => {
    const a = makePatternResult({ match_count: 20 });
    const rows = getMarketSummary(a, null, "ft");
    expect(rows.find((x) => x.marketKey === "ou_25")!.informational).toBe(true);
    expect(rows.find((x) => x.marketKey === "kg")!.informational).toBe(true);
    expect(rows.find((x) => x.marketKey === "result")!.informational).toBe(false);
  });

  it("ht periyodunda ou_25 gösterilmez (excludePeriods)", () => {
    const a = makePatternResult({ match_count: 20, alt_25_pct: 60, ust_25_pct: 40 });
    const rows = getMarketSummary(a, null, "ht");
    expect(rows.find((x) => x.marketKey === "ou_25")).toBeUndefined();
  });
});
