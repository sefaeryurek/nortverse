import type { AnalyzeResponse, DailyEvaluation, FixtureMatch, ResultMatch } from "./types";
import { getApiBase } from "./env";
import { isRecentScoreDate } from "./dates";
import { validMatchList } from "./list-validation";
import { validAnalysis } from "./analysis-validation";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit & { next?: { revalidate: number } } = {}): Promise<T> {
  const timeout = AbortSignal.timeout(95_000);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(`${getApiBase()}${path}`, { ...options, signal });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(timeout.aborted
      ? "İşlem beklenenden uzun sürdü. Lütfen yeniden deneyin."
      : "Sunucuya ulaşılamadı. Lütfen bağlantınızı kontrol edip yeniden deneyin.", 0);
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      400: "İstek geçersiz. Lütfen seçtiğiniz tarih veya maç bilgisini kontrol edin.",
      404: "Maç bulunamadı veya artık erişilebilir değil.",
      422: "Tarih veya maç bilgisi geçerli değil.",
      429: "Çok fazla istek gönderildi. Lütfen biraz sonra yeniden deneyin.",
      503: "Veri hizmeti geçici olarak kullanılamıyor. Lütfen biraz sonra yeniden deneyin.",
      504: "Veri kaynağı zamanında yanıt vermedi. Lütfen yeniden deneyin.",
    };
    throw new ApiError(messages[response.status] ?? "Veriler yüklenemedi. Lütfen yeniden deneyin.", response.status);
  }
  try { return await response.json() as T; }
  catch (error) {
    if (options.signal?.aborted) throw error;
    if (timeout.aborted) throw new ApiError("İşlem beklenenden uzun sürdü. Lütfen yeniden deneyin.", 0);
    throw new ApiError("Sunucudan geçersiz bir yanıt alındı. Lütfen yeniden deneyin.", response.status);
  }
}

function checkedList<T>(value: T, results = false): T {
  if (!validMatchList(value, results)) {
    throw new ApiError("Sunucudan geçersiz maç verisi alındı. Lütfen yeniden deneyin.", 200);
  }
  return value;
}

export async function getFixture(date: string): Promise<FixtureMatch[]> {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  return checkedList(await request<FixtureMatch[]>(`/api/fixture?${new URLSearchParams({ date })}`, {
    next: { revalidate: isRecentScoreDate(date, today) ? 15 : 300 },
  }));
}

export async function analyzeMatch(matchId: string, signal?: AbortSignal): Promise<AnalyzeResponse> {
  const data = await request<unknown>(`/api/analyze/${encodeURIComponent(matchId)}`, {
    cache: "no-store",
    signal,
  });
  if (!validAnalysis(data, matchId)) {
    throw new ApiError("Sunucudan geçersiz analiz verisi alındı. Lütfen yeniden deneyin.", 200);
  }
  return data;
}

export type PatternStatusMap = Record<string, { has_b: boolean; has_c: boolean; agreement?: boolean }>;

export async function getPatternStatus(matchIds: string[]): Promise<PatternStatusMap> {
  if (matchIds.length === 0) return {};
  return request<PatternStatusMap>(
    `/api/fixture/pattern-status?${new URLSearchParams({ match_ids: matchIds.join(",") })}`,
    { next: { revalidate: 300 } },
  );
}

export interface MatchedMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  league_code: string | null;
  ht: string | null;
  h2: string | null;
  ft: string | null;
  kickoff_time: string | null;
}

export interface MatchedMatchesResponse {
  archive_b: MatchedMatch[];
  archive_c: MatchedMatch[];
}

export async function getMatchedMatches(matchId: string): Promise<MatchedMatchesResponse> {
  return request<MatchedMatchesResponse>(`/api/analyze/${encodeURIComponent(matchId)}/matched-matches`, {
    cache: "no-store",
  });
}

export async function getEvaluation(date: string): Promise<DailyEvaluation> {
  return request<DailyEvaluation>(
    `/api/evaluation?${new URLSearchParams({ date })}`,
    { next: { revalidate: 300 } },
  );
}

export async function getResults(date: string): Promise<ResultMatch[]> {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  return checkedList(await request<ResultMatch[]>(`/api/results?${new URLSearchParams({ date })}`, {
    next: { revalidate: isRecentScoreDate(date, today) ? 15 : 300 },
  }), true);
}

