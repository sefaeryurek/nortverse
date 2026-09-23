import type { AnalysisEvidence, AnalysisValidation, AnalyzeResponse, FixtureMatch, MatchSummary, ResultMatch, ScoreValidation } from "./types";
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
    || !validCount(value.score_list_evaluated) || !validCount(value.score_list_hits)
    || (value.archive_1_evaluated as number) > (value.eligible_matches as number)
    || (value.archive_2_evaluated as number) > (value.eligible_matches as number)
    || (value.score_list_evaluated as number) > (value.eligible_matches as number)
    || (value.score_list_hits as number) > (value.score_list_evaluated as number)) {
    throw new ApiError("Analiz doğrulama verisi geçersiz.", 200);
  }
  return value as unknown as AnalysisEvidence;
}

export async function getAnalysisValidation(): Promise<AnalysisValidation> {
  const data = await request<unknown>("/api/analysis-validation", {
    next: { revalidate: 300 },
    signal: AbortSignal.timeout(5_000),
  });
  const value = data as Record<string, unknown>;
  const vc = (n: unknown) => typeof n === "number" && Number.isSafeInteger(n) && n >= 0;
  const vf = (n: unknown) => n === null || (typeof n === "number" && Number.isFinite(n));
  const validTier = (t: unknown) => ["cok_erken", "on_bulgu", "tam"].includes(String(t));
  if (!value || typeof value !== "object" || Array.isArray(value)
    || value.rule_version !== "ft-display-v3"
    || typeof value.baseline_version !== "string" || !(value.baseline_version as string).length
    || !vc(value.total_snapshots)
    || typeof value.brier_note !== "string" || !(value.brier_note as string).length
    || !Array.isArray(value.markets) || value.markets.length > 3
    || !value.markets.every((row: unknown) => {
      if (!row || typeof row !== "object" || Array.isArray(row)) return false;
      const m = row as Record<string, unknown>;
      return ["result", "over_25", "btts"].includes(String(m.market))
        && vc(m.opportunities) && vc(m.issued) && vc(m.abstained) && vc(m.resolved_issued)
        && vc(m.paired) && vc(m.both_hit) && vc(m.model_only) && vc(m.baseline_only) && vc(m.neither)
        && (m.issued as number) + (m.abstained as number) === (m.opportunities as number)
        && (m.both_hit as number) + (m.model_only as number)
           + (m.baseline_only as number) + (m.neither as number) === (m.paired as number)
        && (m.resolved_issued as number) <= (m.issued as number)
        && vf(m.coverage) && vf(m.coverage_ci_low) && vf(m.coverage_ci_high)
        && vf(m.model_hit_rate) && vf(m.model_hit_rate_ci_low) && vf(m.model_hit_rate_ci_high)
        && vf(m.baseline_hit_rate) && vf(m.baseline_hit_rate_ci_low) && vf(m.baseline_hit_rate_ci_high)
        && vf(m.paired_difference) && vf(m.avg_published_frequency)
        && vf(m.observed_hit_rate) && vf(m.calibration_gap) && vf(m.selected_event_brier)
        && validTier(m.display_tier);
    })) {
    throw new ApiError("İleri dönem analiz verisi geçersiz.", 200);
  }
  return value as unknown as AnalysisValidation;
}

export async function getScoreValidation(): Promise<ScoreValidation> {
  const data = await request<unknown>("/api/score-validation", {
    next: { revalidate: 300 },
    signal: AbortSignal.timeout(5_000),
  });
  const value = data as Record<string, unknown>;
  const validCount = (count: unknown) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0;
  if (!value || typeof value !== "object" || Array.isArray(value)
    || value.rule_version !== "score-list-v1"
    || !["recorded", "resolved", "evaluated", "paired", "list_hits", "paired_model_hits",
      "baseline_hits", "both_hit", "model_only", "baseline_only", "neither", "minimum_for_rate"]
      .every((key) => validCount(value[key]))
    || (value.resolved as number) > (value.recorded as number)
    || (value.evaluated as number) > (value.resolved as number)
    || (value.paired as number) > (value.evaluated as number)
    || (value.list_hits as number) > (value.evaluated as number)
    || (value.paired_model_hits as number) > (value.paired as number)
    || (value.baseline_hits as number) > (value.paired as number)
    || (value.both_hit as number) + (value.model_only as number) !== value.paired_model_hits
    || (value.both_hit as number) + (value.baseline_only as number) !== value.baseline_hits
    || (value.both_hit as number) + (value.model_only as number)
      + (value.baseline_only as number) + (value.neither as number) !== value.paired
    || !["coverage_difference_pp", "difference_ci_low_pp", "difference_ci_high_pp"]
      .every((key) => value[key] === null || typeof value[key] === "number" && Number.isFinite(value[key])
        && (value[key] as number) >= -100 && (value[key] as number) <= 100)
    || (value.paired === 0 && ["coverage_difference_pp", "difference_ci_low_pp", "difference_ci_high_pp"]
      .some((key) => value[key] !== null))
    || (value.paired > 0 && ["coverage_difference_pp", "difference_ci_low_pp", "difference_ci_high_pp"]
      .some((key) => value[key] === null))
    || (value.paired > 0 && ((value.difference_ci_low_pp as number) > (value.coverage_difference_pp as number)
      || (value.coverage_difference_pp as number) > (value.difference_ci_high_pp as number)))) {
    throw new ApiError("Skor karşılaştırması verisi geçersiz.", 200);
  }
  return value as unknown as ScoreValidation;
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
