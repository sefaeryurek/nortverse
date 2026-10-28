import { describe, expect, it } from "vitest";
import type { CouponMatch } from "@/lib/api";
import { groupCouponMatches, matchesQuery, normalizeText } from "@/lib/coupon-picker";

// Kupondaş maç seçicisi (Sprint 94 J10): Türkçe duyarsız arama, lig grupları, başlamış/analizli süzgeci
const NOW = Date.parse("2026-10-29T12:00:00Z");
const m = (id: string, home: string, league: string | null, kick: string, extra: Partial<CouponMatch> = {}): CouponMatch => ({
  match_id: id, home_team: home, away_team: "Rakip", league_name: league, kickoff_time: kick, started: false, ...extra,
});

describe("normalizeText / matchesQuery", () => {
  it("ignores case and Turkish diacritics", () => {
    expect(normalizeText("İSTANBUL Başakşehir")).toBe("istanbul basaksehir");
    expect(matchesQuery(m("1", "Başakşehir", "Turkish Super Lig", ""), "basak super")).toBe(true);
    expect(matchesQuery(m("1", "Başakşehir", "Turkish Super Lig", ""), "fener")).toBe(false);
    expect(matchesQuery(m("1", "Göztepe", null, ""), "  ")).toBe(true);
  });
});

describe("groupCouponMatches", () => {
  const list = [
    m("1", "Late", "Serie A", "2026-10-29T19:00:00Z", { analyzed: true }),
    m("2", "Cup", "Copa del Rey", "2026-10-29T15:00:00Z"),
    m("3", "Early", "Serie A", "2026-10-29T13:00:00Z"),
    m("4", "Live", "Serie A", "2026-10-29T11:00:00Z", { started: true }),
    m("5", "NoLeague", null, "2026-10-29T14:00:00Z"),
  ];

  it("groups by league in kickoff order and hides started by default", () => {
    const groups = groupCouponMatches(list, { query: "", onlyAnalyzed: false, showStarted: false }, NOW);
    expect(groups.map((g) => g.league)).toEqual(["Serie A", null, "Copa del Rey"]);
    expect(groups[0].matches.map((x) => x.match_id)).toEqual(["3", "1"]);
  });

  it("shows started on request and filters analyzed only", () => {
    const withStarted = groupCouponMatches(list, { query: "", onlyAnalyzed: false, showStarted: true }, NOW);
    expect(withStarted[0].matches.map((x) => x.match_id)).toEqual(["4", "3", "1"]);
    const analyzed = groupCouponMatches(list, { query: "", onlyAnalyzed: true, showStarted: false }, NOW);
    expect(analyzed.flatMap((g) => g.matches.map((x) => x.match_id))).toEqual(["1"]);
  });

  it("treats a passed kickoff as started even if the server flag is stale", () => {
    const stale = [m("9", "Gecikmiş", "Serie A", "2026-10-29T11:59:00Z")];
    expect(groupCouponMatches(stale, { query: "", onlyAnalyzed: false, showStarted: false }, NOW)).toEqual([]);
  });
});
