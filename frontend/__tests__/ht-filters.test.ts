import { describe, expect, it } from "vitest";
import type { HtMatch } from "@/lib/api";
import { applyHtFilters, DEFAULT_FILTERS, filterHref, oddsDrop, parseHtFilters, strongestOption } from "@/lib/ht-filters";

// İY panosu süzgeçleri (Sprint 94 K-2): URL ↔ süzgeç, zaman penceresi, pazar, lig, asgari olasılık, oran hareketi
const NOW = Date.parse("2026-10-28T12:00:00Z");

const match = (id: string, kickoff: string, opts: Partial<HtMatch> = {}): HtMatch => ({
  match_id: id, home_team: `Ev ${id}`, away_team: `Dep ${id}`, league_name: "English Premier League",
  kickoff_time: kickoff, shadow: false, final_ht: null, odds_at: null, expected_goals: null,
  options: [
    { market: "result", selection: "X", line: null, odds: 2.05, pct: 46, margin_pct: 5, model_pct: null },
    { market: "ou", selection: "under", line: 1.0, odds: 1.7, pct: 58, margin_pct: 4, model_pct: null },
  ],
  ...opts,
});

describe("parseHtFilters / filterHref", () => {
  it("defaults when params are missing or invalid", () => {
    expect(parseHtFilters({})).toEqual(DEFAULT_FILTERS);
    expect(parseHtFilters({ min: "abc", zaman: "x", pazar: "y" })).toEqual(DEFAULT_FILTERS);
  });

  it("parses and clamps values, roundtrips through the URL", () => {
    const f = parseHtFilters({ sirala: "olasilik", zaman: "3s", pazar: "au", lig: "Serie A", min: "62" });
    expect(f).toEqual({ sort: "prob", win: "3h", mkt: "ou", league: "Serie A", min: 60 });
    expect(parseHtFilters({ min: "500" }).min).toBe(95);
    const href = filterHref("2026-10-28", f);
    const params = Object.fromEntries(new URL(href, "http://x").searchParams);
    expect(parseHtFilters(params)).toEqual(f);
  });

  it("omits defaults from the URL", () => {
    expect(filterHref("2026-10-28", DEFAULT_FILTERS)).toBe("/iy?date=2026-10-28");
  });
});

describe("applyHtFilters", () => {
  const matches = [
    match("late", "2026-10-28T19:00:00Z"),
    match("soon", "2026-10-28T13:00:00Z", { league_name: "Serie A" }),
    match("done", "2026-10-28T09:00:00Z", { final_ht: "0-0" }),
    match("pending", "2026-10-28T14:00:00Z", { options: [], odds_pending: true }),
  ];

  it("sorts upcoming by kickoff and moves started matches to the folded section", () => {
    const v = applyHtFilters(matches, DEFAULT_FILTERS, NOW);
    expect(v.upcoming.map((m) => m.match_id)).toEqual(["soon", "pending", "late"]);
    expect(v.finished.map((m) => m.match_id)).toEqual(["done"]);
    expect(v.leagues[0]).toEqual({ name: "English Premier League", count: 3 });
  });

  it("time window keeps only the next 3 hours and hides finished", () => {
    const v = applyHtFilters(matches, { ...DEFAULT_FILTERS, win: "3h" }, NOW);
    expect(v.upcoming.map((m) => m.match_id)).toEqual(["soon", "pending"]);
    expect(v.finished).toEqual([]);
  });

  it("market, league and minimum probability filters; pending only in unfiltered view", () => {
    const strong = match("strong", "2026-10-28T18:00:00Z", { options: [
      { market: "result", selection: "1", line: null, odds: 1.4, pct: 70, margin_pct: 5, model_pct: null }] });
    const all = [...matches, strong];
    expect(applyHtFilters(all, { ...DEFAULT_FILTERS, min: 60 }, NOW).upcoming.map((m) => m.match_id)).toEqual(["strong"]);
    expect(applyHtFilters(all, { ...DEFAULT_FILTERS, mkt: "result", min: 50 }, NOW).upcoming.map((m) => m.match_id))
      .toEqual(["strong"]);
    expect(applyHtFilters(all, { ...DEFAULT_FILTERS, league: "Serie A" }, NOW).upcoming.map((m) => m.match_id))
      .toEqual(["soon"]);
    const byProb = applyHtFilters(all, { ...DEFAULT_FILTERS, sort: "prob" }, NOW).upcoming.map((m) => m.match_id);
    expect(byProb[0]).toBe("strong");
  });

  it("strongest option respects the chosen market", () => {
    const m = matches[0];
    expect(strongestOption(m, "all")?.market).toBe("ou");
    expect(strongestOption(m, "result")?.selection).toBe("X");
  });
});

describe("oddsDrop", () => {
  const o = { market: "result" as const, selection: "1" as const, line: null, odds: 1.8, pct: 50, margin_pct: 5, model_pct: null };
  it("relative drop from opening; null when not comparable", () => {
    expect(oddsDrop({ ...o, open_odds: 2.0 })).toBeCloseTo(0.1);
    expect(oddsDrop({ ...o, open_odds: null })).toBeNull();
    expect(oddsDrop({ ...o, open_odds: 0 })).toBeNull();
  });
});
