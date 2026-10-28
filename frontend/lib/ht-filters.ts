/**
 * İY oran panosu süzgeçleri (Sprint 94 K-2 — "çok fazla maç" şikâyeti). URL parametreleriyle çalışır, süzme sunucu
 * bileşeninde yapılır; backend değişmez (sadece açılış oranı eklendi).
 */
import type { HtMatch, HtOption } from "./api";

export type HtSort = "time" | "prob";
export type HtWindow = "all" | "3h" | "rest";
export type HtMarket = "all" | "result" | "ou";

export interface HtFilters {
  sort: HtSort;
  win: HtWindow;
  mkt: HtMarket;
  league: string | null;
  /** En güçlü seçeneğin olasılığı en az (0 = süzgeç yok) */
  min: number;
}

export const DEFAULT_FILTERS: HtFilters = { sort: "time", win: "all", mkt: "all", league: null, min: 0 };
export const ODDS_DROP_MIN = 0.08;  // açılıştan ≥%8 düşüş → rozet
const THREE_HOURS = 3 * 3600_000;

type Params = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

export function parseHtFilters(params: Params): HtFilters {
  const sort = one(params.sirala) === "olasilik" ? "prob" : "time";
  const winRaw = one(params.zaman);
  const win: HtWindow = winRaw === "3s" ? "3h" : winRaw === "kalan" ? "rest" : "all";
  const mktRaw = one(params.pazar);
  const mkt: HtMarket = mktRaw === "1x2" ? "result" : mktRaw === "au" ? "ou" : "all";
  const league = one(params.lig)?.slice(0, 80) || null;
  const minNum = Number(one(params.min));
  const min = Number.isFinite(minNum) ? Math.min(95, Math.max(0, Math.round(minNum / 5) * 5)) : 0;
  return { sort, win, mkt, league, min };
}

/** Süzgeçlerin URL'si (varsayılanlar yazılmaz). */
export function filterHref(date: string, f: HtFilters, change: Partial<HtFilters> = {}): string {
  const next = { ...f, ...change };
  const q = new URLSearchParams({ date });
  if (next.sort === "prob") q.set("sirala", "olasilik");
  if (next.win !== "all") q.set("zaman", next.win === "3h" ? "3s" : "kalan");
  if (next.mkt !== "all") q.set("pazar", next.mkt === "result" ? "1x2" : "au");
  if (next.league) q.set("lig", next.league);
  if (next.min > 0) q.set("min", String(next.min));
  return `/iy?${q}`;
}

export function marketOptions(m: HtMatch, mkt: HtMarket): HtOption[] {
  const options = Array.isArray(m.options) ? m.options : [];
  return mkt === "all" ? options : options.filter((o) => o.market === mkt);
}

/** Seçili pazarda en yüksek olasılıklı seçenek. */
export function strongestOption(m: HtMatch, mkt: HtMarket): HtOption | null {
  return marketOptions(m, mkt).reduce<HtOption | null>((best, o) => (!best || o.pct > best.pct ? o : best), null);
}

/** Açılıştan bu yana oran düşüşü (0,1 = %10); karşılaştırılamıyorsa null. */
export function oddsDrop(o: HtOption): number | null {
  if (o.open_odds == null || !(o.open_odds > 0) || !(o.odds > 0)) return null;
  return (o.open_odds - o.odds) / o.open_odds;
}

const started = (m: HtMatch, now: number) => m.final_ht != null || (m.kickoff_time != null && Date.parse(m.kickoff_time) <= now);

export interface HtView {
  upcoming: HtMatch[];
  /** Başlamış / bitmiş — sayfanın altında, katlı */
  finished: HtMatch[];
  leagues: { name: string; count: number }[];
}

export function applyHtFilters(matches: HtMatch[], f: HtFilters, now: number): HtView {
  const leagueCounts = new Map<string, number>();
  for (const m of matches) {
    if (m.league_name) leagueCounts.set(m.league_name, (leagueCounts.get(m.league_name) ?? 0) + 1);
  }
  const leagues = [...leagueCounts].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));

  const kept = matches.filter((m) => {
    if (f.league && m.league_name !== f.league) return false;
    if (m.odds_pending) return f.mkt === "all" && f.min === 0;  // oran henüz yok: sadece süzgeçsiz görünümde
    const best = strongestOption(m, f.mkt);
    if (!best) return false;
    return best.pct >= f.min;
  });
  const kick = (m: HtMatch) => (m.kickoff_time ? Date.parse(m.kickoff_time) : Number.MAX_SAFE_INTEGER);
  const byTime = (a: HtMatch, b: HtMatch) => kick(a) - kick(b);
  const byProb = (a: HtMatch, b: HtMatch) =>
    (strongestOption(b, f.mkt)?.pct ?? -1) - (strongestOption(a, f.mkt)?.pct ?? -1) || byTime(a, b);

  let upcoming = kept.filter((m) => !started(m, now));
  if (f.win === "3h") upcoming = upcoming.filter((m) => kick(m) - now <= THREE_HOURS);
  upcoming.sort(f.sort === "prob" ? byProb : byTime);
  const finished = f.win === "all" ? kept.filter((m) => started(m, now)).sort(byTime) : [];
  return { upcoming, finished, leagues };
}
