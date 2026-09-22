export const LIVE_SCORE_FRESH_MS = 120_000;

export function isLiveScoreStale(checkedAt: string | null, now = Date.now()): boolean {
  if (!checkedAt) return true;
  const checkedMs = Date.parse(checkedAt);
  const age = now - checkedMs;
  return !Number.isFinite(checkedMs) || age < -30_000 || age >= LIVE_SCORE_FRESH_MS;
}
