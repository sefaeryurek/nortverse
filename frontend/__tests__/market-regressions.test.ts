import { expect, it } from "vitest";
import { getMarketSummary } from "@/lib/confidence";
import { makePatternResult } from "./fixtures";

it("does not hide HT/FT markets when draw/draw is zero", () => {
  const pattern = makePatternResult({ match_count: 10, iy_ms_11_pct: 100, iy_ms_xx_pct: 0 });
  const row = getMarketSummary(pattern, null, "ft").find((r) => r.marketKey === "iy_ms");
  expect(row?.winnerA?.pct).toBe(100);
});

it("uses the second archive when the first has no half-time data", () => {
  const empty = makePatternResult({ match_count: 10 });
  const pattern = makePatternResult({ match_count: 5, iy_ms_11_pct: 100 });
  const row = getMarketSummary(empty, pattern, "ft").find((r) => r.marketKey === "iy_ms");
  expect(row?.winnerA).toBeNull();
  expect(row?.winnerB?.pct).toBe(100);
});
