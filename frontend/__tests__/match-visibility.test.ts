import { expect, it } from "vitest";
import { showBulletinMatch, showResultMatch } from "@/lib/match-visibility";
import type { FixtureMatch, ResultMatch } from "@/lib/types";

const now = Date.parse("2026-09-22T08:00:00Z");
const fixture = {
  match_id: "1", home_team: "A", away_team: "B", league_code: "ENG PR",
  league_name: "English Premier League", kickoff_time: "2026-09-21T22:00:00Z",
  status: "scheduled", live_home: null, live_away: null, live_minute: null,
  score_checked_at: null,
} satisfies FixtureMatch;

it("hides started fixtures without a verified live score", () => {
  expect(showBulletinMatch(fixture, now, "2026-09-22", "2026-09-22")).toBe(false);
  expect(showBulletinMatch({ ...fixture, status: "pending" }, now, "2026-09-22", "2026-09-22")).toBe(false);
  expect(showBulletinMatch({ ...fixture, status: "live" }, now, "2026-09-22", "2026-09-22")).toBe(true);
  expect(showBulletinMatch({ ...fixture, kickoff_time: "2026-09-22T12:00:00Z" }, now,
    "2026-09-22", "2026-09-22")).toBe(true);
});

it("only shows confirmed results for matches that have started", () => {
  const result = { ...fixture, status: "finished", actual_ft_home: 2, actual_ft_away: 1 } as ResultMatch;
  expect(showResultMatch(result, now)).toBe(true);
  expect(showResultMatch({ ...result, status: "pending" }, now)).toBe(false);
  expect(showResultMatch({ ...result, actual_ft_away: null }, now)).toBe(false);
  expect(showResultMatch({ ...result, kickoff_time: "2026-09-22T12:00:00Z" }, now)).toBe(false);
});
