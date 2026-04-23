import type { AnalyzeResponse, FixtureMatch, MatchSummary, ResultMatch } from "./types";

// Geliştirme: boş string → Next.js rewrite proxy (/api/* → localhost:8000)
// Üretim: NEXT_PUBLIC_API_URL env var ile tam URL ver
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function getFixture(date: string): Promise<FixtureMatch[]> {
  const res = await fetch(`${BASE}/api/fixture?date=${date}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Fixture alınamadı: ${res.status}`);
  return res.json();
}

export async function analyzeMatch(matchId: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/api/analyze/${matchId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Analiz başarısız: ${res.status}`);
  return res.json();
}

export async function prefetchAnalyze(matchId: string): Promise<void> {
  try {
    await fetch(`${BASE}/api/analyze/${matchId}`, { cache: "no-store" });
  } catch {
    // sessiz başarısızlık — prefetch arka planda çalışır
  }
}

export async function getResults(date: string): Promise<ResultMatch[]> {
  const res = await fetch(`${BASE}/api/results?date=${date}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Sonuçlar alınamadı: ${res.status}`);
  return res.json();
}

export async function getMatches(
  league?: string,
  limit = 100
): Promise<MatchSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (league) params.set("league", league);
  const res = await fetch(`${BASE}/api/matches?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Maçlar alınamadı: ${res.status}`);
  return res.json();
}
