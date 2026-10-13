import type { MatchedMatch } from "./api";

export interface HTFilteredStats {
  archive: string;
  color: string;
  bgColor: string;
  matches: MatchedMatch[];
  ftScoreCounts: { score: string; count: number; pct: number }[];
  result1Pct: number;
  resultXPct: number;
  result2Pct: number;
  ust25Pct: number;
  kgVarPct: number;
}

export function filterByHT(
  matches: MatchedMatch[],
  htHome: number,
  htAway: number,
): MatchedMatch[] {
  const htStr = `${htHome}-${htAway}`;
  return matches.filter((m) => m.ht === htStr);
}

export function computeStats(
  matches: MatchedMatch[],
  archive: string,
  color: string,
  bgColor: string,
): HTFilteredStats | null {
  if (matches.length === 0) return null;

  let r1 = 0, rX = 0, r2 = 0, ust25 = 0, kgVar = 0;
  const scoreCounts: Record<string, number> = {};

  for (const m of matches) {
    if (!m.ft) continue;
    const parts = m.ft.split("-");
    if (parts.length !== 2) continue;
    const fh = parseInt(parts[0], 10);
    const fa = parseInt(parts[1], 10);
    if (isNaN(fh) || isNaN(fa)) continue;

    if (fh > fa) r1++;
    else if (fh === fa) rX++;
    else r2++;

    if (fh + fa > 2) ust25++;
    if (fh > 0 && fa > 0) kgVar++;

    scoreCounts[m.ft] = (scoreCounts[m.ft] || 0) + 1;
  }

  const total = r1 + rX + r2;
  if (total === 0) return null;

  const ftScoreCounts = Object.entries(scoreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([score, count]) => ({
      score,
      count,
      pct: Math.round((count / total) * 1000) / 10,
    }));

  return {
    archive,
    color,
    bgColor,
    matches,
    ftScoreCounts,
    result1Pct: Math.round((r1 / total) * 1000) / 10,
    resultXPct: Math.round((rX / total) * 1000) / 10,
    result2Pct: Math.round((r2 / total) * 1000) / 10,
    ust25Pct: Math.round((ust25 / total) * 1000) / 10,
    kgVarPct: Math.round((kgVar / total) * 1000) / 10,
  };
}
