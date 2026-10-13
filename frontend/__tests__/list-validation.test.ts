import { describe, it, expect } from "vitest";
import { validMatchList } from "@/lib/list-validation";

function fixtureRow(overrides: Record<string, unknown> = {}) {
  return {
    match_id: "123456",
    home_team: "Galatasaray",
    away_team: "Fenerbahce",
    league_code: "TUR D1",
    league_name: "Turkish Super Lig",
    kickoff_time: "2026-10-13T19:00:00Z",
    status: "scheduled",
    live_home: null,
    live_away: null,
    live_minute: null,
    score_checked_at: null,
    ...overrides,
  };
}

function resultRow(overrides: Record<string, unknown> = {}) {
  return {
    match_id: "123456",
    home_team: "Galatasaray",
    away_team: "Fenerbahce",
    league_code: "TUR D1",
    league_name: "Turkish Super Lig",
    kickoff_time: "2026-10-13T19:00:00Z",
    status: "finished",
    actual_ft_home: 2,
    actual_ft_away: 1,
    actual_ht_home: 1,
    actual_ht_away: 0,
    result: "1",
    kg_var: true,
    over_25: true,
    katman_a_covered: true,
    ...overrides,
  };
}

describe("validMatchList — fixture mode", () => {
  it("accepts valid fixture array", () => {
    expect(validMatchList([fixtureRow()])).toBe(true);
  });

  it("accepts empty array", () => {
    expect(validMatchList([])).toBe(true);
  });

  it("rejects non-array", () => {
    expect(validMatchList("string")).toBe(false);
    expect(validMatchList(null)).toBe(false);
    expect(validMatchList({})).toBe(false);
  });

  it("rejects missing match_id", () => {
    expect(validMatchList([fixtureRow({ match_id: undefined })])).toBe(false);
  });

  it("rejects non-numeric match_id", () => {
    expect(validMatchList([fixtureRow({ match_id: "abc" })])).toBe(false);
  });

  it("rejects empty home_team", () => {
    expect(validMatchList([fixtureRow({ home_team: "" })])).toBe(false);
  });

  it("rejects empty away_team", () => {
    expect(validMatchList([fixtureRow({ away_team: "  " })])).toBe(false);
  });

  it("rejects duplicate match_ids", () => {
    expect(validMatchList([fixtureRow(), fixtureRow()])).toBe(false);
  });

  it("accepts unique match_ids", () => {
    expect(validMatchList([
      fixtureRow({ match_id: "111" }),
      fixtureRow({ match_id: "222" }),
    ])).toBe(true);
  });

  it("accepts null league_code", () => {
    expect(validMatchList([fixtureRow({ league_code: null })])).toBe(true);
  });

  it("rejects numeric league_code", () => {
    expect(validMatchList([fixtureRow({ league_code: 123 })])).toBe(false);
  });

  it("accepts live status with scores", () => {
    expect(validMatchList([fixtureRow({
      status: "live",
      live_home: 1,
      live_away: 0,
      live_minute: "45",
    })])).toBe(true);
  });

  it("rejects live status without scores", () => {
    expect(validMatchList([fixtureRow({
      status: "live",
      live_home: null,
      live_away: null,
    })])).toBe(false);
  });

  it("accepts pending status", () => {
    expect(validMatchList([fixtureRow({ status: "pending" })])).toBe(true);
  });

  it("rejects finished status in fixture mode", () => {
    expect(validMatchList([fixtureRow({ status: "finished" })])).toBe(false);
  });

  it("accepts HT live_minute", () => {
    expect(validMatchList([fixtureRow({
      status: "live", live_home: 0, live_away: 0, live_minute: "HT",
    })])).toBe(true);
  });

  it("accepts 45+2 live_minute", () => {
    expect(validMatchList([fixtureRow({
      status: "live", live_home: 0, live_away: 0, live_minute: "45+2",
    })])).toBe(true);
  });

  it("rejects invalid live_minute format", () => {
    expect(validMatchList([fixtureRow({
      status: "live", live_home: 0, live_away: 0, live_minute: "abc",
    })])).toBe(false);
  });

  it("rejects negative live_home", () => {
    expect(validMatchList([fixtureRow({ live_home: -1 })])).toBe(false);
  });

  it("rejects score > 30", () => {
    expect(validMatchList([fixtureRow({ live_home: 31 })])).toBe(false);
  });
});

describe("validMatchList — results mode", () => {
  it("accepts valid result array", () => {
    expect(validMatchList([resultRow()], true)).toBe(true);
  });

  it("rejects non-finished status", () => {
    expect(validMatchList([resultRow({ status: "live" })], true)).toBe(false);
  });

  it("rejects null ft scores", () => {
    expect(validMatchList([resultRow({ actual_ft_home: null })], true)).toBe(false);
  });

  it("accepts null ht scores", () => {
    expect(validMatchList([resultRow({ actual_ht_home: null, actual_ht_away: null })], true)).toBe(true);
  });

  it("accepts valid result values", () => {
    for (const r of ["1", "X", "2", null]) {
      expect(validMatchList([resultRow({ result: r })], true)).toBe(true);
    }
  });

  it("rejects invalid result value", () => {
    expect(validMatchList([resultRow({ result: "W" })], true)).toBe(false);
  });

  it("accepts boolean kg_var/over_25/katman_a_covered", () => {
    expect(validMatchList([resultRow({
      kg_var: false, over_25: false, katman_a_covered: false,
    })], true)).toBe(true);
  });

  it("accepts null kg_var/over_25/katman_a_covered", () => {
    expect(validMatchList([resultRow({
      kg_var: null, over_25: null, katman_a_covered: null,
    })], true)).toBe(true);
  });

  it("rejects non-boolean kg_var", () => {
    expect(validMatchList([resultRow({ kg_var: "yes" })], true)).toBe(false);
  });

  it("rejects negative actual scores", () => {
    expect(validMatchList([resultRow({ actual_ft_home: -1 })], true)).toBe(false);
  });

  it("rejects scores over 30", () => {
    expect(validMatchList([resultRow({ actual_ft_home: 31 })], true)).toBe(false);
  });

  it("rejects non-integer scores", () => {
    expect(validMatchList([resultRow({ actual_ft_home: 1.5 })], true)).toBe(false);
  });

  it("accepts invalid kickoff_time as null", () => {
    expect(validMatchList([resultRow({ kickoff_time: null })], true)).toBe(true);
  });
});
