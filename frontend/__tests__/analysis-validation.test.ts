import { afterEach, expect, it, vi } from "vitest";
import { analyzeMatch, getMatches } from "@/lib/api";
import { validAnalysis } from "@/lib/analysis-validation";
import { makePatternResult } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function analysis() {
  return {
    match_id: "123", home_team: "Home", away_team: "Away", league_code: "ENG PR", season: "2026/2027",
    ht: { scores_1: [], scores_x: ["0-0"], scores_2: [] },
    half2: { scores_1: [], scores_x: [], scores_2: [] },
    ft: { scores_1: ["1-0"], scores_x: [], scores_2: [] },
    ht_b: null, ht_c: null, h2_b: null, h2_c: null,
    ft_b: makePatternResult({ match_count: 5 }), ft_c: null,
    trends: null, skipped: false, skip_reason: null,
  };
}

it("accepts a complete analysis with legitimately missing archive matches", async () => {
  const data = analysis();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
  await expect(analyzeMatch("123")).resolves.toEqual(data);
});

it.each([
  { match_id: "999" }, { ft: null }, { ft: { scores_1: [42], scores_x: [], scores_2: [] } },
  { ft_b: {} }, { ft_b: makePatternResult({ result_1_pct: 101, match_count: 5 }) },
  { ft_b: makePatternResult({ score_freq: { "1-0": 6 }, match_count: 5 }) },
  { trends: { home_form: {}, away_form: null, h2h: null } },
  { skipped: "false" },
])("rejects malformed analysis instead of exposing it to components: %s", async (changes) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...analysis(), ...changes }))));
  await expect(analyzeMatch("123")).rejects.toThrow("geçersiz analiz verisi");
});

it("requires every percentage field instead of silently accepting missing markets", () => {
  const data = analysis();
  const partial = { ...data.ft_b } as Record<string, unknown>;
  delete partial.result_1_pct;
  expect(validAnalysis({ ...data, ft_b: partial }, "123")).toBe(false);
});

it("accepts a skipped match without pattern data", () => {
  expect(validAnalysis({ ...analysis(), skipped: true, skip_reason: "h2h_insufficient", ft_b: null }, "123")).toBe(true);
});

it("rejects malformed summaries at the API boundary", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{ match_id: "123" }]))));
  await expect(getMatches()).rejects.toThrow("geçersiz maç özeti");
});

it("accepts complete summaries with unknown scores", async () => {
  const rows = [{ match_id: "123", home_team: "Home", away_team: "Away", league_code: null, season: null,
    actual_ft_home: null, actual_ft_away: null, actual_ht_home: null, actual_ht_away: null,
    ft_scores_1: [], ft_scores_x: [], ft_scores_2: [] }];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(rows))));
  await expect(getMatches()).resolves.toEqual(rows);
});
