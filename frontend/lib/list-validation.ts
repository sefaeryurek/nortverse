function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
const text = (value: unknown) => typeof value === "string" && value.trim().length > 0;
const nullableText = (value: unknown) => value === null || typeof value === "string";
const score = (value: unknown) => value === null || typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 30;

export function validMatchList(value: unknown, results = false): boolean {
  if (!Array.isArray(value)) return false;
  const ids = new Set<string>();
  return value.every((row) => {
    if (!record(row) || typeof row.match_id !== "string" || !/^\d{1,12}$/.test(row.match_id)
      || ids.has(row.match_id) || !text(row.home_team) || !text(row.away_team)
      || !nullableText(row.league_code) || !nullableText(row.league_name)
      || !(row.kickoff_time === null || typeof row.kickoff_time === "string"
        && Number.isFinite(Date.parse(row.kickoff_time)))) return false;
    ids.add(row.match_id);
    if (!results) return true;
    if (!["scheduled", "pending", "live", "finished", "postponed"].includes(String(row.status))) return false;
    if (!["actual_ft_home", "actual_ft_away", "actual_ht_home", "actual_ht_away"].every((key) => score(row[key]))) return false;
    if (!["live_home", "live_away"].every((key) => row[key] === undefined || score(row[key]))) return false;
    if (row.score_checked_at !== undefined && row.score_checked_at !== null
      && (typeof row.score_checked_at !== "string" || !Number.isFinite(Date.parse(row.score_checked_at)))) return false;
    if (row.status === "finished" && (row.actual_ft_home === null || row.actual_ft_away === null)) return false;
    if (row.status === "live" && (row.live_home == null || row.live_away == null)) return false;
    return [null, "1", "X", "2"].includes(row.result as string | null)
      && ["kg_var", "over_25", "katman_a_covered"].every((key) => row[key] === null || typeof row[key] === "boolean");
  });
}
