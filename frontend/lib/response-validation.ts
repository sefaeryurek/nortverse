/**
 * Uç bazlı hafif yanıt doğrulayıcıları (Sprint 94 L2).
 *
 * Önbellekteki eski yanıt ya da backend'deki şekil değişikliği sayfayı çökertmesin (/iy olayı): sadece ekranın
 * mutlaka okuduğu alanlar denetlenir; tutmazsa istek okunabilir bir hatayla reddedilir, sayfa hata kartı gösterir.
 */
import type { HtStrategyResponse, MatchOdds, PerformanceSummary } from "./api";

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const numOrNull = (v: unknown) => v === null || isNum(v);
const strOrNull = (v: unknown) => v === null || isStr(v);

export function validHtStrategy(data: unknown): data is HtStrategyResponse {
  if (!isObj(data) || !isStr(data.date) || !Array.isArray(data.matches)) return false;
  return data.matches.every((m) =>
    isObj(m) && isStr(m.match_id) && isStr(m.home_team) && isStr(m.away_team) && strOrNull(m.kickoff_time)
    && Array.isArray(m.options)
    && m.options.every((o) => isObj(o) && isStr(o.market) && isStr(o.selection) && isNum(o.odds) && isNum(o.pct)
      && numOrNull(o.model_pct) && numOrNull(o.line ?? null))
    && (m.expected_goals === null || m.expected_goals === undefined
      || (isObj(m.expected_goals) && isNum(m.expected_goals.home) && isNum(m.expected_goals.away))));
}

function validStats(s: unknown): boolean {
  return isObj(s) && isNum(s.resolved) && isNum(s.hits) && numOrNull(s.hit_pct) && numOrNull(s.avg_prob_pct)
    && numOrNull(s.lift_pct ?? null) && numOrNull(s.brier ?? null);
}

export function validPerformanceSummary(data: unknown): data is PerformanceSummary {
  if (!isObj(data) || !validStats(data.overall) || !isObj(data.groups) || !Array.isArray(data.calibration)) return false;
  return Object.values(data.groups).every((rows) => Array.isArray(rows) && rows.every((r) => validStats(r) && isObj(r)))
    && data.calibration.every((b) => isObj(b) && isNum(b.n) && isNum(b.hit_pct) && isNum(b.avg_prob_pct));
}

export function validMatchOdds(data: unknown): data is MatchOdds {
  if (!isObj(data) || !isStr(data.match_id) || !isStr(data.home_team) || !isStr(data.away_team)) return false;
  if (!isObj(data.markets)) return false;
  return (["ft", "ht"] as const).every((period) => {
    const market = (data.markets as Record<string, unknown>)[period];
    if (!isObj(market) || !strOrNull(market.closed ?? null)) return false;
    return Object.entries(market).every(([key, value]) => {
      if (key === "closed") return true;
      if (!isObj(value)) return false;
      // ou: { line, over, under }; result/dc: { "1": 2.1, ... }
      return Object.entries(value).every(([k, v]) => (k === "line" ? numOrNull(v) : isNum(v)));
    });
  });
}
