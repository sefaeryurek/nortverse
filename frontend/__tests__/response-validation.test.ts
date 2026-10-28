import { afterEach, describe, expect, it, vi } from "vitest";
import { fmtNum } from "@/lib/format";
import { validHtStrategy, validMatchOdds, validPerformanceSummary } from "@/lib/response-validation";
import { API_SCHEMA_VERSION, getHtStrategy, getPerformanceSummary } from "@/lib/api";

// Sprint 94 L2: önbellekteki eski / değişmiş yanıt şekli sayfayı çökertmesin

const option = { market: "result", selection: "1", line: null, odds: 2.1, pct: 45.2, margin_pct: 5.1, model_pct: null };
const htMatch = {
  match_id: "1", home_team: "A", away_team: "B", league_name: null, kickoff_time: null, shadow: false,
  final_ht: null, options: [option], odds_at: null, expected_goals: { home: 0.6, away: 0.4 },
};
const stats = { total: 3, resolved: 2, pending: 1, void: 0, hits: 1, hit_pct: 50, ci_low: 9, ci_high: 91,
  avg_prob_pct: 60, calibration_gap: -10, brier: 0.2, baseline_resolved: 0, baseline_hit_pct: null, lift_pct: null };
const summary = { source: "top_pick", rule_versions: ["v"], overall: stats, groups: { market: [{ ...stats, key: "result" }] },
  calibration: [{ lower: 50, upper: 60, n: 2, avg_prob_pct: 55, hit_pct: 50 }] };
const odds = { match_id: "1", home_team: "A", away_team: "B", league_name: null, live: null, markets: {
  ft: { closed: null, result: { "1": 2.1, X: 3.3, "2": 3.4 }, ou: { line: 2.5, over: 1.9, under: 1.95 } },
  ht: { closed: "İlk yarı bitti" } } };

describe("validators", () => {
  it("accept well-formed responses", () => {
    expect(validHtStrategy({ date: "2026-10-28", matches: [htMatch, { ...htMatch, expected_goals: null }] })).toBe(true);
    expect(validPerformanceSummary(summary)).toBe(true);
    expect(validMatchOdds(odds)).toBe(true);
  });

  it.each([
    ["missing options", { date: "d", matches: [{ ...htMatch, options: undefined }] }],
    ["odds as text", { date: "d", matches: [{ ...htMatch, options: [{ ...option, odds: "2.1" }] }] }],
    ["expected goals without away", { date: "d", matches: [{ ...htMatch, expected_goals: { home: 1 } }] }],
    ["old shape (list)", [htMatch]],
  ])("reject İY strategy: %s", (_n, data) => expect(validHtStrategy(data)).toBe(false));

  it("reject performance summary with missing overall numbers", () => {
    expect(validPerformanceSummary({ ...summary, overall: { ...stats, hit_pct: undefined } })).toBe(false);
    expect(validPerformanceSummary({ ...summary, calibration: undefined })).toBe(false);
  });

  it("reject odds with missing period or text price", () => {
    expect(validMatchOdds({ ...odds, markets: { ft: odds.markets.ft } })).toBe(false);
    expect(validMatchOdds({ ...odds, markets: { ...odds.markets, ft: { closed: null, result: { "1": "2.1" } } } })).toBe(false);
  });
});

describe("fmtNum", () => {
  it("writes a dash for missing values instead of crashing", () => {
    expect(fmtNum(1.234, 2)).toBe("1.23");
    expect(fmtNum(null, 1)).toBe("—");
    expect(fmtNum(undefined, 1)).toBe("—");
    expect(fmtNum(Number.NaN, 1)).toBe("—");
  });
});

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("rejects a malformed İY response with a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([htMatch]))));
    await expect(getHtStrategy("2026-10-28")).rejects.toThrow("geçersiz bir yanıt");
  });

  it("adds the schema version only to cached requests", async () => {
    const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify(summary)));
    vi.stubGlobal("fetch", mock);
    await getPerformanceSummary("top_pick");
    expect(mock.mock.calls[0][0]).toContain(`v=${API_SCHEMA_VERSION}`);
    mock.mockResolvedValue(new Response(JSON.stringify({ date: "d", matches: [] })));
    await getHtStrategy("2026-10-28");
    expect(mock.mock.calls[1][0]).not.toContain("v=");
  });
});
