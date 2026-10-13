import { describe, it, expect } from "vitest";
import { filterByHT, computeStats } from "@/lib/live-stats";
import type { MatchedMatch } from "@/lib/api";

function makeMatch(overrides: Partial<MatchedMatch> = {}): MatchedMatch {
  return {
    match_id: "100",
    home_team: "Team A",
    away_team: "Team B",
    league_code: "TUR D1",
    league_name: "Turkish Super Lig",
    ht: "1-0",
    h2: "1-1",
    ft: "2-1",
    similarity: null,
    ...overrides,
  };
}

describe("filterByHT", () => {
  it("returns matches with matching HT score", () => {
    const matches = [
      makeMatch({ match_id: "1", ht: "1-0" }),
      makeMatch({ match_id: "2", ht: "0-0" }),
      makeMatch({ match_id: "3", ht: "1-0" }),
    ];
    const result = filterByHT(matches, 1, 0);
    expect(result).toHaveLength(2);
    expect(result.map((m) => m.match_id)).toEqual(["1", "3"]);
  });

  it("returns empty array when no match", () => {
    const matches = [makeMatch({ ht: "2-1" })];
    expect(filterByHT(matches, 0, 0)).toHaveLength(0);
  });

  it("handles empty input", () => {
    expect(filterByHT([], 1, 0)).toHaveLength(0);
  });

  it("matches 0-0 correctly", () => {
    const matches = [
      makeMatch({ match_id: "1", ht: "0-0" }),
      makeMatch({ match_id: "2", ht: "1-0" }),
    ];
    expect(filterByHT(matches, 0, 0)).toHaveLength(1);
  });
});

describe("computeStats", () => {
  it("returns null for empty matches", () => {
    expect(computeStats([], "A1", "#00f", "#eef")).toBeNull();
  });

  it("returns null when no valid FT scores", () => {
    const matches = [makeMatch({ ft: "" }), makeMatch({ ft: null as unknown as string })];
    expect(computeStats(matches, "A1", "#00f", "#eef")).toBeNull();
  });

  it("calculates result percentages correctly", () => {
    const matches = [
      makeMatch({ ft: "2-1" }),
      makeMatch({ ft: "0-0" }),
      makeMatch({ ft: "0-1" }),
      makeMatch({ ft: "3-0" }),
    ];
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats).not.toBeNull();
    expect(stats!.result1Pct).toBe(50);
    expect(stats!.resultXPct).toBe(25);
    expect(stats!.result2Pct).toBe(25);
  });

  it("calculates over 2.5 percentage", () => {
    const matches = [
      makeMatch({ ft: "2-1" }),
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "3-1" }),
      makeMatch({ ft: "0-0" }),
    ];
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats!.ust25Pct).toBe(50);
  });

  it("calculates BTTS percentage", () => {
    const matches = [
      makeMatch({ ft: "2-1" }),
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "1-2" }),
      makeMatch({ ft: "0-0" }),
    ];
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats!.kgVarPct).toBe(50);
  });

  it("returns top 8 score counts sorted by frequency", () => {
    const matches = [
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "2-1" }),
      makeMatch({ ft: "2-1" }),
      makeMatch({ ft: "0-0" }),
    ];
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats!.ftScoreCounts[0]).toEqual({ score: "1-0", count: 3, pct: 50 });
    expect(stats!.ftScoreCounts[1]).toEqual({ score: "2-1", count: 2, pct: 33.3 });
    expect(stats!.ftScoreCounts).toHaveLength(3);
  });

  it("limits to 8 score entries", () => {
    const scores = ["1-0","2-1","0-0","3-1","2-0","0-1","1-1","3-2","4-0"];
    const matches = scores.map((ft, i) => makeMatch({ match_id: String(i), ft }));
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats!.ftScoreCounts).toHaveLength(8);
  });

  it("preserves archive/color metadata", () => {
    const matches = [makeMatch({ ft: "1-0" })];
    const stats = computeStats(matches, "Arşiv 1", "#0088ff", "#002244");
    expect(stats!.archive).toBe("Arşiv 1");
    expect(stats!.color).toBe("#0088ff");
    expect(stats!.bgColor).toBe("#002244");
  });

  it("skips malformed FT scores", () => {
    const matches = [
      makeMatch({ ft: "abc" }),
      makeMatch({ ft: "1-0" }),
      makeMatch({ ft: "x-y" }),
    ];
    const stats = computeStats(matches, "A1", "#00f", "#eef");
    expect(stats!.result1Pct).toBe(100);
    expect(stats!.matches).toHaveLength(3);
  });

  it("handles single match", () => {
    const stats = computeStats([makeMatch({ ft: "0-0" })], "A1", "#00f", "#eef");
    expect(stats!.result1Pct).toBe(0);
    expect(stats!.resultXPct).toBe(100);
    expect(stats!.result2Pct).toBe(0);
    expect(stats!.ust25Pct).toBe(0);
    expect(stats!.kgVarPct).toBe(0);
  });
});
