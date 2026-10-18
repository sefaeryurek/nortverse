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
  const timeout = AbortSignal.timeout(30_000);
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

export type PatternStatusMap = Record<string, { has_b: boolean; has_c: boolean; has_d?: boolean; agreement?: boolean; agreement_bcd?: boolean }>;

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
  league_name?: string | null;
  ht: string | null;
  h2: string | null;
  ft: string | null;
  kickoff_time?: string | null;
  similarity?: number | null;
}

export interface MatchedMatchesResponse {
  period?: "ht" | "h2" | "ft";
  archive_b: MatchedMatch[];
  archive_c: MatchedMatch[];
  archive_d?: MatchedMatch[];
  list_available?: Record<"archive_b" | "archive_c" | "archive_d", boolean>;
}

export async function getMatchedMatches(
  matchId: string,
  period: "ht" | "h2" | "ft" = "ft",
): Promise<MatchedMatchesResponse> {
  return request<MatchedMatchesResponse>(
    `/api/analyze/${encodeURIComponent(matchId)}/matched-matches?${new URLSearchParams({ period })}`,
    { cache: "no-store" },
  );
}

export async function getEvaluation(date: string): Promise<DailyEvaluation> {
  return request<DailyEvaluation>(
    `/api/evaluation?${new URLSearchParams({ date })}`,
    { next: { revalidate: 300 } },
  );
}

export type PredictionSource = "live_ht" | "top_pick" | "market_summary";
export type SampleStage = "cok_erken" | "on_bulgu" | "tam";

export interface PerformanceStats {
  total: number;
  resolved: number;
  pending: number;
  void: number;
  hits: number;
  hit_pct: number | null;
  ci_low: number | null;
  ci_high: number | null;
  avg_prob_pct: number | null;
  calibration_gap: number | null;
  brier: number | null;
  baseline_resolved: number;
  baseline_hit_pct: number | null;
  lift_pct: number | null;
  stage: SampleStage;
}

export interface PerformanceSummary {
  source: PredictionSource;
  rule_versions: string[];
  overall: PerformanceStats;
  /** Arşiv bazında sonuçlanan kayıt sayısı; overall tekil karar sayar (aynı seçim tek kez). */
  raw_resolved?: number;
  groups: Record<string, (PerformanceStats & { key: string })[]>;
  calibration: { lower: number; upper: number; n: number; avg_prob_pct: number; hit_pct: number }[];
}

export interface LedgerPrediction {
  id: number;
  match_id: string;
  home_team: string;
  away_team: string;
  league_name: string;
  kickoff_time: string;
  recorded_at: string;
  rule_version: string;
  period: "ht" | "h2" | "ft";
  market: string;
  selection: string;
  archive: string | null;
  prob_pct: number;
  tier: string | null;
  informational: boolean;
  sample_n: number | null;
  baseline_selection: string | null;
  baseline_outcome: "hit" | "miss" | null;
  ht: string | null;
  final_ht: string | null;
  final_ft: string | null;
  outcome: "hit" | "miss" | "void" | "pending";
  late: boolean;
}

export async function getPerformanceSummary(
  source: PredictionSource, groupBy = "tier,market", ruleVersion?: string,
  dateFrom?: string, dateTo?: string,
): Promise<PerformanceSummary> {
  const params = new URLSearchParams({ source, group_by: groupBy });
  if (ruleVersion) params.set("rule_version", ruleVersion);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return request<PerformanceSummary>(
    `/api/performance/summary?${params}`,
    { next: { revalidate: 120 } },
  );
}

export interface BacktestRun {
  id: number;
  strategy: PredictionSource;
  rule_version: string;
  params: Record<string, unknown>;
  date_from: string;
  date_to: string;
  notes: string | null;
  created_at: string;
  n: number;
  /** Bugünkü ayarlarla üretilmiş mi (değilse deneme koşusu). */
  current: boolean;
}

export interface BacktestSummary extends PerformanceSummary {
  run_id: number;
  informational: PerformanceStats;
}

export async function getBacktestRuns(): Promise<BacktestRun[]> {
  return request<BacktestRun[]>("/api/performance/backtest/runs", { next: { revalidate: 30 } });
}

export async function getBacktestSummary(runId: number): Promise<BacktestSummary> {
  return request<BacktestSummary>(`/api/performance/backtest/${runId}/summary`, { next: { revalidate: 3600 } });
}

export interface LiveMatchPick {
  period: "ft" | "h2";
  market: string;
  selection: string;
  archive: LiveArchiveKey;
  label: string;
  /** Aynı seçimi işaret eden tüm arşivler (tekil sayım: tek işaret, birden çok kaynak). */
  labels: string[];
  pct: number;
  n: number;
  risky: boolean;
  outcome: "hit" | "miss" | "void" | "pending";
}

export interface LiveMatchEvaluation {
  match_id: string;
  home_team: string;
  away_team: string;
  league_name: string;
  kickoff_time: string;
  recorded_at: string;
  ht: string;
  final_ht: string | null;
  final_ft: string | null;
  picks: LiveMatchPick[];
  hits: number;
  resolved: number;
}

/** Canlıya giren (devre arasında kaydedilen) her maç ve %85+ işaretlerinin sonucu. */
export async function getLiveMatchEvaluations(day: string): Promise<LiveMatchEvaluation[]> {
  return request<LiveMatchEvaluation[]>(
    `/api/performance/live-matches?${new URLSearchParams({ day })}`,
    { next: { revalidate: 60 } },
  );
}

export async function getPerformancePredictions(source: PredictionSource, day: string): Promise<LedgerPrediction[]> {
  return request<LedgerPrediction[]>(
    `/api/performance/predictions?${new URLSearchParams({ source, day })}`,
    { next: { revalidate: 60 } },
  );
}

export async function getResults(date: string): Promise<ResultMatch[]> {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  return checkedList(await request<ResultMatch[]>(`/api/results?${new URLSearchParams({ date })}`, {
    next: { revalidate: isRecentScoreDate(date, today) ? 15 : 300 },
  }), true);
}

export type LiveOutcome = "1" | "X" | "2";
export type LiveArchiveKey = "a1" | "a2" | "a3" | "genel";

/** Bir pazarın en yüksek seçimi ve tüm seçimlerin oranları (yüzde). */
export interface LiveArchiveCell {
  period: "ft" | "h2";
  market: string;
  selection: string;
  pct: number;
  options: Record<string, number>;
}

export interface LiveArchiveMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  kickoff_time: string | null;
  ht: string;
  ft: string;
  result: LiveOutcome;
  similarity: number | null;
}

export interface LiveArchiveSource {
  archive: LiveArchiveKey;
  label: string;
  n: number;
  /** 0 < n < risky_below_n */
  risky: boolean;
  cells: LiveArchiveCell[];
  /** Sadece detay isteğinde: İY'si aynı biten eşleşen maçlar, en yeni önce. */
  matches?: LiveArchiveMatch[];
}

export interface LiveHistorical {
  /** Backtest'te aynı pazar + örneklem kovasındaki %85+ işaretlerin gerçek isabeti. */
  pct: number;
  n: number;
  bucket: string;
  /** Pazarda az veri vardı → kovanın tüm pazar ortalaması. */
  pooled: boolean;
}

export interface LiveHighlight {
  period: "ft" | "h2";
  market: string;
  selection: string;
  pct: number;
  archive: LiveArchiveKey;
  label: string;
  n: number;
  risky: boolean;
  historical?: LiveHistorical | null;
}

export interface LiveArchiveView {
  rule_version: string;
  ht: { home: number; away: number };
  threshold_pct: number;
  risky_below_n: number;
  sources: LiveArchiveSource[];
  /** ≥ threshold_pct seçimler; maç kaydedildiyse defterdeki kayıt. */
  highlights: LiveHighlight[];
}

export interface LiveArchiveDetail {
  frozen: boolean;
  frozen_at: string | null;
  archive_view: LiveArchiveView;
}

export interface LiveHTMatch {
  match_id: string;
  home_team: string | null;
  away_team: string | null;
  ht_home: number;
  ht_away: number;
  live_home: number | null;
  live_away: number | null;
  live_minute: string | null;
  phase?: "1h" | "ht" | "2h" | null;
  league_name: string | null;
  kickoff_time: string | null;
  frozen?: boolean;
  frozen_at?: string | null;
  archive_view?: LiveArchiveView | null;
}

export async function getLiveHTMatches(): Promise<LiveHTMatch[]> {
  return request<LiveHTMatch[]>("/api/live-ht", { cache: "no-store" });
}

export async function getLivePrediction(matchId: string, detail = false): Promise<LiveArchiveDetail> {
  return request<LiveArchiveDetail>(
    `/api/live-ht/${encodeURIComponent(matchId)}/prediction?${new URLSearchParams({ detail: detail ? "1" : "0" })}`,
    { cache: "no-store" },
  );
}

