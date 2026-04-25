import type { AnalyzeResponse, FixtureMatch, MatchSummary, ResultMatch } from "./types";

// Geliştirme: BASE = "" → Next.js proxy (/api/* → localhost:8000)
// Vercel server-side (SSR): BACKEND_URL → Railway'e direkt
// Vercel client-side (browser): BACKEND_URL undefined → proxy üzerinden Railway'e
const BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.BACKEND_URL ||
  "";

export async function getFixture(date: string): Promise<FixtureMatch[]> {
  // Server-side fetch (Vercel SSR): Next.js Data Cache 60sn → tarih değişimi anlık
  const res = await fetch(`${BASE}/api/fixture?date=${date}`, {
    next: { revalidate: 60 },
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

export async function getResults(date: string): Promise<ResultMatch[]> {
  // Sonuçlar 60sn cache — _score_updater 30dk'da bir güncelliyor, 60sn yeterince taze
  const res = await fetch(`${BASE}/api/results?date=${date}`, {
    next: { revalidate: 60 },
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
