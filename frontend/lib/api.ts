import type { AnalysisEvidence, AnalyzeResponse, FixtureMatch, MatchSummary, ResultMatch } from "./types";
import { getApiBase } from "./env";
import { isRecentScoreDate } from "./dates";
import { validMatchList } from "./list-validation";
import { validAnalysis, validSummaries } from "./analysis-validation";

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

export async function getAnalysisEvidence(): Promise<AnalysisEvidence> {
  const data = await request<unknown>("/api/analysis-evidence", {
    next: { revalidate: 300 },
    signal: AbortSignal.timeout(5_000),
  });
  const value = data as Record<string, unknown>;
  const validCount = (count: unknown) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0;
  if (!value || typeof value !== "object" || Array.isArray(value)
    || !validCount(value.eligible_matches) || !validCount(value.archive_1_evaluated)
    || !validCount(value.archive_2_evaluated) || !validCount(value.minimum_for_rate)
    || (value.archive_1_evaluated as number) > (value.eligible_matches as number)
    || (value.archive_2_evaluated as number) > (value.eligible_matches as number)) {
    throw new ApiError("Analiz doğrulama verisi geçersiz.", 200);
  }
  return value as unknown as AnalysisEvidence;
}

export async function getResults(date: string): Promise<ResultMatch[]> {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  return checkedList(await request<ResultMatch[]>(`/api/results?${new URLSearchParams({ date })}`, {
    next: { revalidate: isRecentScoreDate(date, today) ? 15 : 300 },
  }), true);
}

export async function getMatches(
  league?: string,
  limit = 100
): Promise<MatchSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (league) params.set("league", league);
  const data = await request<unknown>(`/api/matches?${params}`, {
    cache: "no-store",
  });
  if (!validSummaries(data)) {
    throw new ApiError("Sunucudan geçersiz maç özeti alındı. Lütfen yeniden deneyin.", 200);
  }
  return data;
}
