import { PATTERN_PERCENT_FIELDS } from "./pattern-fields";
import type { AnalyzeResponse, MatchSummary } from "./types";

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
const text = (value: unknown) => typeof value === "string" && value.trim().length > 0;
const nullableText = (value: unknown) => value === null || typeof value === "string";
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const count = (value: unknown) => finite(value) && Number.isSafeInteger(value) && value >= 0;
const percentage = (value: unknown) => finite(value) && value >= 0 && value <= 100;
const score = (value: unknown) => value === null || count(value) && (value as number) <= 30;
const scoreLabel = (value: unknown) => typeof value === "string" && /^(?:[0-9]|[12][0-9]|30)-(?:[0-9]|[12][0-9]|30)$/.test(value);
const scores = (value: unknown) => Array.isArray(value) && value.every(scoreLabel);

function identity(value: unknown): value is Record<string, unknown> {
  return record(value) && typeof value.match_id === "string" && /^\d{1,12}$/.test(value.match_id)
    && text(value.home_team) && text(value.away_team);
}

function period(value: unknown): boolean {
  return record(value) && ["scores_1", "scores_x", "scores_2"].every((key) => scores(value[key]));
}

function pattern(value: unknown): boolean {
  return value === null || record(value) && count(value.match_count) && (value.match_count as number) > 0
    && Object.keys(PATTERN_PERCENT_FIELDS).every((key) => percentage(value[key]))
    && record(value.score_freq) && Object.entries(value.score_freq).every(([key, frequency]) =>
      scoreLabel(key) && count(frequency) && (frequency as number) <= (value.match_count as number));
}

function trend(value: unknown): boolean {
  return value === null || record(value) && text(value.label) && count(value.sample_size)
    && (value.sample_size as number) > 0
    && ["win_pct", "draw_pct", "loss_pct", "kg_var_pct", "over_25_pct"].every((key) => percentage(value[key]))
    && ["avg_goals_for", "avg_goals_against"].every((key) => finite(value[key]) && value[key] >= 0)
    && Array.isArray(value.last_n_results) && value.last_n_results.every((v) => ["G", "B", "M"].includes(v));
}

export function validAnalysis(value: unknown, requestedId: string): value is AnalyzeResponse {
  return identity(value) && value.match_id === requestedId
    && typeof value.league_code === "string" && typeof value.season === "string"
    && typeof value.skipped === "boolean" && nullableText(value.skip_reason)
    && ["ht", "half2", "ft"].every((key) => period(value[key]))
    && ["ht_b", "ht_c", "h2_b", "h2_c", "ft_b", "ft_c"].every((key) => pattern(value[key]))
    && (value.trends === null || record(value.trends)
      && ["home_form", "away_form", "h2h"].every((key) => trend((value.trends as Record<string, unknown>)[key])));
}

export function validSummaries(value: unknown): value is MatchSummary[] {
  if (!Array.isArray(value)) return false;
  const ids = new Set();
  return value.every((row) => {
    if (!identity(row) || ids.has(row.match_id) || !nullableText(row.league_code) || !nullableText(row.season)
      || !["actual_ft_home", "actual_ft_away", "actual_ht_home", "actual_ht_away"].every((key) => score(row[key]))
      || !["ft_scores_1", "ft_scores_x", "ft_scores_2"].every((key) => row[key] === null || scores(row[key]))) return false;
    ids.add(row.match_id);
    return true;
  });
}
