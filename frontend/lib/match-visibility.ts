import type { FixtureMatch, ResultMatch } from "./types";

export function showBulletinMatch(match: FixtureMatch, nowMs: number, today: string, date: string): boolean {
  if (match.status === "live") return true;
  if (match.status !== "scheduled") return false;
  if (match.kickoff_time) return Date.parse(match.kickoff_time) > nowMs;
  return date >= today;
}

export function showResultMatch(match: ResultMatch, nowMs: number): boolean {
  return match.status === "finished"
    && match.actual_ft_home !== null
    && match.actual_ft_away !== null
    && (!match.kickoff_time || Date.parse(match.kickoff_time) <= nowMs);
}
