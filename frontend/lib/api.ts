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
  const msg = errorMessages();
  let response: Response;
  try {
    response = await fetch(`${getApiBase()}${path}`, { ...options, signal });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(timeout.aborted ? msg.timeout : msg.network, 0);
  }
  if (!response.ok) {
    throw new ApiError(msg.status[response.status] ?? msg.generic, response.status);
  }
  try { return await response.json() as T; }
  catch (error) {
    if (options.signal?.aborted) throw error;
    if (timeout.aborted) throw new ApiError(msg.timeout, 0);
    throw new ApiError(msg.invalid, response.status);
  }
}

const ERROR_MESSAGES = {
  tr: {
    timeout: "İşlem beklenenden uzun sürdü. Lütfen yeniden deneyin.",
    network: "Sunucuya ulaşılamadı. Lütfen bağlantınızı kontrol edip yeniden deneyin.",
    generic: "Veriler yüklenemedi. Lütfen yeniden deneyin.",
    invalid: "Sunucudan geçersiz bir yanıt alındı. Lütfen yeniden deneyin.",
    status: {
      400: "İstek geçersiz. Lütfen seçtiğiniz tarih veya maç bilgisini kontrol edin.",
      404: "Maç bulunamadı veya artık erişilebilir değil.",
      422: "Tarih veya maç bilgisi geçerli değil.",
      429: "Çok fazla istek gönderildi. Lütfen biraz sonra yeniden deneyin.",
      503: "Veri hizmeti geçici olarak kullanılamıyor. Lütfen biraz sonra yeniden deneyin.",
      504: "Veri kaynağı zamanında yanıt vermedi. Lütfen yeniden deneyin.",
    } as Record<number, string>,
  },
  en: {
    timeout: "The request took longer than expected. Please try again.",
    network: "Could not reach the server. Please check your connection and try again.",
    generic: "Data could not be loaded. Please try again.",
    invalid: "The server returned an invalid response. Please try again.",
    status: {
      400: "Invalid request. Please check the selected date or match.",
      404: "Match not found or no longer available.",
      422: "The date or match information is not valid.",
      429: "Too many requests. Please try again in a moment.",
      503: "The data service is temporarily unavailable. Please try again shortly.",
      504: "The data source did not respond in time. Please try again.",
    } as Record<number, string>,
  },
};

/** Tarayıcıda dil çerezine göre (sunucu bileşenleri kendi sözlük metnini gösterir → Türkçe varsayılan). */
function errorMessages() {
  const english = typeof document !== "undefined" && /(?:^|;\s*)nv_lang=en(?:;|$)/.test(document.cookie);
  return ERROR_MESSAGES[english ? "en" : "tr"];
}

function checkedList<T>(value: T, results = false): T {
  if (!validMatchList(value, results)) {
    throw new ApiError("Sunucudan geçersiz maç verisi alındı. Lütfen yeniden deneyin.", 200);
  }
  return value;
}

export async function getFixture(date: string, shadow = false): Promise<FixtureMatch[]> {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const params = new URLSearchParams({ date });
  if (shadow) params.set("shadow", "1");
  return checkedList(await request<FixtureMatch[]>(`/api/fixture?${params}`, {
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
  /** Kural karnesi (Sprint 91): <100 tekil karar → collecting; Wilson aralığı beklenenin altı → below. */
  verdict?: Verdict;
  expected_hits?: number | null;
}

export type Verdict = "collecting" | "below" | "above" | "on_track";

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

/** Değerlendirme kapsamı: ekrandaki 7 ana lig ya da gölgedeki (deneme) ligler — karneleri ayrı. */
export type PerformanceScope = "main" | "shadow";

export async function getPerformanceSummary(
  source: PredictionSource, groupBy = "tier,market", ruleVersion?: string,
  dateFrom?: string, dateTo?: string, scope: PerformanceScope = "main",
): Promise<PerformanceSummary> {
  const params = new URLSearchParams({ source, group_by: groupBy });
  if (scope !== "main") params.set("scope", scope);
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
export async function getLiveMatchEvaluations(day: string, scope: PerformanceScope = "main"): Promise<LiveMatchEvaluation[]> {
  const params = new URLSearchParams({ day });
  if (scope !== "main") params.set("scope", scope);
  return request<LiveMatchEvaluation[]>(
    `/api/performance/live-matches?${params}`,
    { next: { revalidate: 60 } },
  );
}

export async function getPerformancePredictions(
  source: PredictionSource, day: string, ruleVersion?: string, scope: PerformanceScope = "main",
): Promise<LedgerPrediction[]> {
  const params = new URLSearchParams({ source, day });
  if (scope !== "main") params.set("scope", scope);
  if (ruleVersion) params.set("rule_version", ruleVersion);
  return request<LedgerPrediction[]>(
    `/api/performance/predictions?${params}`,
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
  /** live-arch-v2: aynı seçimi işaret eden arşivler (tek karar). v1 kayıtlarında yok. */
  sources?: string[];
  /** v2: kazanan arşivin oranı (ikincil); `pct` = aynı lig + aynı İY geçmişinin oranı. */
  archive_pct?: number | null;
  cond_n?: number | null;
  cond_level?: "league" | "global";
  conflict?: boolean;
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

/** Canlı ana karar (live-poisson-v1.1): takım gücü modeli, %85+ pazarlar. */
export interface LivePoissonDecision {
  period: string;
  market: string;
  selection: string;
  pct: number;
  /** Aynı lig + aynı İY skorlu geçmiş maçlarda bu seçimin oranı */
  cond_pct: number | null;
  cond_n: number | null;
  best: boolean;
  rule_version: string;
  /** Arşiv + lig geçmişi kuralı (live-arch-v2) aynı seçimi yaptı */
  confirmed: boolean;
  /** Bu pazarda geçmiş testteki isabet */
  historical: { pct: number; n: number } | null;
}

export interface LiveArchiveDetail {
  frozen: boolean;
  frozen_at: string | null;
  archive_view: LiveArchiveView;
  decisions?: LivePoissonDecision[];
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
  decisions?: LivePoissonDecision[];
  /** Gölgedeki lig — ekran varsayılan olarak gizler. */
  shadow?: boolean;
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


/* ---- İY strateji (ht-display-v1, Deneme) ---- */
export interface HtPick {
  period: "ht";
  market: string;
  selection: string;
  pct: number;
  tier: "high" | "medium";
  base_pct: number | null;
}

export interface HtProbs {
  lambda: { home: number; away: number };
  result: Record<"1" | "X" | "2", number>;
  dc: Record<"1X" | "X2" | "12", number>;
  ou_05: Record<"over" | "under", number>;
  ou_15: Record<"over" | "under", number>;
  ev_05: Record<"over" | "under", number>;
  top_scores: { score: string; pct: number }[];
}

export interface HtMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  league_name: string | null;
  kickoff_time: string | null;
  shadow: boolean;
  final_ht: string | null;
  probs: HtProbs | null;
  picks: HtPick[];
  frozen: boolean;
  frozen_at: string | null;
}

export async function getHtStrategy(date: string, shadow = false): Promise<{ date: string; matches: HtMatch[] }> {
  const params = new URLSearchParams({ date });
  if (shadow) params.set("shadow", "1");
  return request<{ date: string; matches: HtMatch[] }>(`/api/ht-strategy?${params}`, { next: { revalidate: 60 } });
}
