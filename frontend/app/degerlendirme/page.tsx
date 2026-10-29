import { fmtNum } from "@/lib/format";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import LiveCoverage from "@/components/LiveCoverage";
import { BacktestOverview, LiveDayList, PerformanceOverview, PredictionDayList } from "@/components/PerformancePanel";
import RetryButton from "@/components/RetryButton";
import { getEvaluation } from "@/lib/api";
import { ISTANBUL_TZ, resolvePageDate } from "@/lib/dates";
import { leagueDisplay } from "@/lib/leagues";
import type { DailyEvaluation, MatchEvaluation, PatternEvaluation } from "@/lib/types";
import Link from "next/link";
import { type Dictionary, type Locale, COOKIE_NAME, defaultLocale, getDictionary, isLocale } from "@/lib/i18n";
import { SHADOW_COOKIE, shadowFromCookie } from "@/lib/shadow";
import type { PerformanceScope } from "@/lib/api";

export const metadata: Metadata = {
  title: "Değerlendirme",
  description: "Günlük tahmin isabeti değerlendirmesi",
};

/* ------------------------------------------------------------------ */
/*  Skeleton                                                          */
/* ------------------------------------------------------------------ */

function EvalSkeleton() {
  return (
    <div
      className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
      style={{ maxWidth: "var(--nv-max-content)" }}
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="nv-card p-4">
            <div className="nv-skeleton mb-2" style={{ width: 80, height: 12 }} />
            <div className="nv-skeleton" style={{ width: 48, height: 24 }} />
          </div>
        ))}
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="nv-card p-4">
          <div className="flex items-center gap-3">
            <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
            <div className="nv-skeleton" style={{ width: 56, height: 28 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Summary Card                                                      */
/* ------------------------------------------------------------------ */

function SummaryCard({
  label,
  hit,
  total,
  pct,
}: {
  label: string;
  hit: number;
  total: number;
  pct: number;
}) {
  const color =
    total === 0
      ? "var(--nv-text-tertiary)"
      : pct >= 60
        ? "var(--nv-accent-green)"
        : pct >= 40
          ? "var(--nv-text-secondary)"
          : "var(--nv-accent-red)";

  return (
    <div className="nv-card p-4">
      <div
        style={{
          fontSize: "var(--nv-text-xs)",
          color: "var(--nv-text-tertiary)",
          fontWeight: 500,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="font-bold"
          style={{ fontSize: "var(--nv-text-xl)", color }}
        >
          {total > 0 ? `%${fmtNum(pct, 0)}` : "-"}
        </span>
        <span
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          {hit}/{total}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Hit/Miss Badge                                                    */
/* ------------------------------------------------------------------ */

function HitBadge({ hit, label }: { hit: boolean; label: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: "var(--nv-text-xs)",
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: "var(--nv-radius-sm)",
        backgroundColor: hit
          ? "var(--nv-accent-green-dim)"
          : "var(--nv-accent-red-dim)",
        color: hit ? "var(--nv-accent-green)" : "var(--nv-accent-red)",
      }}
    >
      {hit ? "✓" : "✗"} {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Pattern Badge                                                     */
/* ------------------------------------------------------------------ */

/** Backend Türkçe seçim adı döner ("Üst", "KG Var") → seçili dile çevrilir. */
function pickLabel(pick: string, t: Dictionary): string {
  const lp = t.live.prediction;
  const map: Record<string, string> = {
    "Üst": lp.over, "Alt": lp.under,
    "KG Var": `${lp.btts} ${lp.yes}`, "KG Yok": `${lp.btts} ${lp.no}`,
  };
  return map[pick] ?? pick;
}

function PatternBadge({
  pat,
  archiveLabel,
  t,
}: {
  pat: PatternEvaluation;
  archiveLabel: string;
  t: Dictionary;
}) {
  const lowConfidence = pat.match_count < 10;
  return (
    <div
      className="flex flex-wrap items-center gap-1.5"
      style={{ fontSize: "var(--nv-text-xs)", opacity: lowConfidence ? 0.6 : 1.0 }}
    >
      <span
        style={{
          fontWeight: 700,
          color: "var(--nv-text-tertiary)",
          minWidth: 20,
        }}
      >
        {archiveLabel}
      </span>
      <HitBadge hit={pat.result_hit} label={`${pat.result_pick} %${fmtNum(pat.result_pct, 0)}`} />
      {pat.is_confident && (
        <span
          style={{
            fontSize: "var(--nv-text-xs)",
            fontWeight: 700,
            padding: "1px 5px",
            borderRadius: "var(--nv-radius-sm)",
            backgroundColor: "var(--nv-accent-blue-dim)",
            color: "var(--nv-accent-blue)",
          }}
        >
          {t.evaluation.confident}
        </span>
      )}
      <HitBadge hit={pat.over_25_hit} label={`${pickLabel(pat.over_25_pick, t)} %${fmtNum(pat.over_25_pct, 0)}`} />
      <HitBadge hit={pat.btts_hit} label={`${pickLabel(pat.btts_pick, t)} %${fmtNum(pat.btts_pct, 0)}`} />
      <span style={{ color: "var(--nv-text-tertiary)" }}>
        ({pat.match_count} {t.common.match})
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  EvalRow                                                           */
/* ------------------------------------------------------------------ */

function EvalRow({ match, t }: { match: MatchEvaluation; t: Dictionary }) {
  const { flag } = leagueDisplay(match.league_code, match.league_name);
  const leagueName = match.league_name || match.league_code || "";

  const timeStr = match.kickoff_time
    ? (() => {
        try {
          return new Date(match.kickoff_time).toLocaleTimeString(t.common.timeLocale, {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: ISTANBUL_TZ,
          });
        } catch {
          return "--:--";
        }
      })()
    : "--:--";

  const scoreColor =
    match.result === "1"
      ? "var(--nv-win)"
      : match.result === "2"
        ? "var(--nv-loss)"
        : "var(--nv-draw)";

  return (
    <div className="nv-card p-3 sm:p-4 nv-fade-in">
      {/* Ust satir: Lig + Saat + Takim + Skor */}
      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
        <span className="flex items-center gap-1 flex-shrink-0">
          <span className="text-base leading-none" aria-hidden="true">
            {flag}
          </span>
          <span
            className="truncate font-medium"
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
              maxWidth: 100,
            }}
          >
            {leagueName}
          </span>
        </span>

        <span
          className="flex-shrink-0"
          style={{
            fontFamily: "var(--nv-font-mono)",
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          {timeStr}
        </span>

        <div className="flex-1 min-w-0">
          <span
            className="font-semibold truncate"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-text-primary)",
            }}
          >
            {match.home_team}
          </span>
          <span
            className="mx-1.5"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
          >
            vs
          </span>
          <span
            className="font-semibold truncate"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-text-primary)",
            }}
          >
            {match.away_team}
          </span>
        </div>

        {/* Skor */}
        <span
          className="flex-shrink-0 font-bold px-3 py-1"
          style={{
            fontSize: "var(--nv-text-base)",
            fontFamily: "var(--nv-font-mono)",
            color: scoreColor,
            backgroundColor: "var(--nv-bg-elevated)",
            borderRadius: "var(--nv-radius-md)",
          }}
        >
          {match.actual_ft}
        </span>
      </div>

      {/* Alt satir: Tahmin sonuclari */}
      <div className="mt-2 flex flex-col gap-1.5">
        {match.pattern_b && (
          <PatternBadge pat={match.pattern_b} archiveLabel="A1" t={t} />
        )}
        {match.pattern_c && (
          <PatternBadge pat={match.pattern_c} archiveLabel="A2" t={t} />
        )}
        {match.pattern_d && (
          <PatternBadge pat={match.pattern_d} archiveLabel="A3" t={t} />
        )}
        {!match.pattern_b && !match.pattern_c && !match.pattern_d && (
          <span
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            {t.evaluation.noPrediction}
          </span>
        )}

        {/* Skor listesi */}
        {match.score_list.length > 0 && (
          <div className="flex items-center gap-1.5" style={{ fontSize: "var(--nv-text-xs)" }}>
            <span style={{ fontWeight: 700, color: "var(--nv-text-tertiary)", minWidth: 20 }}>
              SL
            </span>
            <HitBadge
              hit={match.score_list_hit}
              label={match.score_list_hit
                ? t.evaluation.inList.replace("{score}", match.actual_ft)
                : t.evaluation.notInList.replace("{score}", match.actual_ft)}
            />
          </div>
        )}
      </div>

      {/* Analiz linki */}
      <div className="flex justify-end mt-2">
        <Link
          href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
          prefetch={false}
          className="flex-shrink-0 flex items-center justify-center min-h-[32px] px-3 py-1 font-medium transition-colors"
          style={{
            fontSize: "var(--nv-text-xs)",
            backgroundColor: "var(--nv-accent-blue-dim)",
            color: "var(--nv-accent-blue)",
            borderRadius: "var(--nv-radius-md)",
          }}
        >
          {t.common.analysis}
        </Link>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  EvalList (async server component)                                 */
/* ------------------------------------------------------------------ */

async function EvalList({ date, t }: { date: string; t: Dictionary }) {
  let data: DailyEvaluation | null = null;
  let error = "";
  try {
    data = await getEvaluation(date);
  } catch (e) {
    error = e instanceof Error ? e.message : t.common.connectionError;
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
        <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
          <p
            className="font-medium"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}
          >
            {error || t.common.dataError}
          </p>
          <RetryButton />
        </div>
      </div>
    );
  }

  if (data.matches.length === 0) {
    return (
      <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
        <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
          <p
            className="font-medium"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}
          >
            {t.evaluation.noEvalMatches}
          </p>
          <Link
            href={`/sonuclar?date=${date}`}
            className="inline-block font-medium transition-colors"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}
          >
            {t.evaluation.viewResults}
          </Link>
        </div>
      </div>
    );
  }

  const s = data.summary;

  return (
    <div style={{ maxWidth: "var(--nv-max-content)" }}>
      {/* Özet kartları — Arşiv 1 (Pattern B) */}
      <div className="px-[var(--nv-page-gutter)] pt-4 pb-1">
        <span style={{ fontSize: "var(--nv-text-xs)", fontWeight: 700, color: "var(--nv-accent-blue)" }}>
          {t.evaluation.archive1}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 px-[var(--nv-page-gutter)] pb-3">
        <SummaryCard label={t.evaluation.resultAccuracy} hit={s.result_hit} total={s.evaluated} pct={s.result_hit_pct} />
        <SummaryCard label={t.evaluation.confidentResult} hit={s.confident_result_hit} total={s.confident_evaluated} pct={s.confident_result_hit_pct} />
        <SummaryCard label={t.evaluation.overUnder} hit={s.over_25_hit} total={s.evaluated} pct={s.over_25_hit_pct} />
        <SummaryCard label={t.evaluation.bttsAccuracy} hit={s.btts_hit} total={s.evaluated} pct={s.btts_hit_pct} />
        <SummaryCard label={t.evaluation.scoreList} hit={s.score_list_hit} total={s.score_list_evaluated ?? s.total_matches} pct={s.score_list_hit_pct} />
      </div>

      {/* Özet kartları — Arşiv 2 (Pattern C) */}
      {s.evaluated_c > 0 && (
        <>
          <div className="px-[var(--nv-page-gutter)] pt-2 pb-1">
            <span style={{ fontSize: "var(--nv-text-xs)", fontWeight: 700, color: "var(--nv-accent-green)" }}>
              {t.evaluation.archive2}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-[var(--nv-page-gutter)] pb-3">
            <SummaryCard label={t.evaluation.resultAccuracy} hit={s.c_result_hit} total={s.evaluated_c} pct={s.c_result_hit_pct} />
            <SummaryCard label={t.evaluation.confidentResult} hit={s.confident_c_result_hit} total={s.confident_c_evaluated} pct={s.confident_c_result_hit_pct} />
            <SummaryCard label={t.evaluation.overUnder} hit={s.c_over_25_hit} total={s.evaluated_c} pct={s.c_over_25_hit_pct} />
            <SummaryCard label={t.evaluation.bttsAccuracy} hit={s.c_btts_hit} total={s.evaluated_c} pct={s.c_btts_hit_pct} />
          </div>
        </>
      )}

      {/* Özet kartları — Arşiv 3 (Pattern D) */}
      {s.evaluated_d > 0 && (
        <>
          <div className="px-[var(--nv-page-gutter)] pt-2 pb-1">
            <span style={{ fontSize: "var(--nv-text-xs)", fontWeight: 700, color: "var(--nv-accent-amber)" }}>
              {t.evaluation.archive3}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-[var(--nv-page-gutter)] pb-3">
            <SummaryCard label={t.evaluation.resultAccuracy} hit={s.d_result_hit} total={s.evaluated_d} pct={s.d_result_hit_pct} />
            <SummaryCard label={t.evaluation.confidentResult} hit={s.confident_d_result_hit} total={s.confident_d_evaluated} pct={s.confident_d_result_hit_pct} />
            <SummaryCard label={t.evaluation.overUnder} hit={s.d_over_25_hit} total={s.evaluated_d} pct={s.d_over_25_hit_pct} />
            <SummaryCard label={t.evaluation.bttsAccuracy} hit={s.d_btts_hit} total={s.evaluated_d} pct={s.d_btts_hit_pct} />
          </div>
        </>
      )}

      {/* Brier score + özet bilgi çubuğu */}
      <div
        className="flex flex-wrap items-center gap-3 px-[var(--nv-page-gutter)] py-3"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <span
          className="flex items-center gap-1.5"
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
        >
          <span
            className="flex-shrink-0"
            style={{
              width: 6,
              height: 6,
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: "var(--nv-accent-green)",
            }}
          />
          {t.evaluation.finishedMatches.replace("{count}", String(s.total_matches))}
        </span>
        <span
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
        >
          {t.evaluation.evaluatedCount.replace("{count}", String(s.evaluated))}
        </span>
        {(s.brier_result_b != null || s.brier_result_c != null || s.brier_result_d != null) && (
          <span
            className="flex items-center gap-2 ml-auto"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
            title={t.evaluation.brierTooltip}
          >
            {t.evaluation.brier}
            {s.brier_result_b != null && (
              <span style={{ color: "var(--nv-accent-blue)" }}>A1 {fmtNum(s.brier_result_b, 3)}</span>
            )}
            {s.brier_result_c != null && (
              <span style={{ color: "var(--nv-accent-green)" }}>A2 {fmtNum(s.brier_result_c, 3)}</span>
            )}
            {s.brier_result_d != null && (
              <span style={{ color: "var(--nv-accent-amber)" }}>A3 {fmtNum(s.brier_result_d, 3)}</span>
            )}
          </span>
        )}
      </div>

      {/* Mac kartlari */}
      <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4">
        {data.matches.map((m) => (
          <EvalRow key={m.match_id} match={m} t={t} />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

interface Props {
  searchParams: Promise<{ date?: string | string[]; tab?: string | string[]; run?: string | string[]; aralik?: string | string[]; kapsam?: string | string[] }>;
}

/** Özet aralığı: seçili gün, o güne kadar 7 gün, ya da tüm kayıtlar. */
const RANGES = ["gun", "7g", "tum"] as const;
type Range = (typeof RANGES)[number];

function resolveRange(raw: string | string[] | undefined): Range {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return (RANGES as readonly string[]).includes(value ?? "") ? (value as Range) : "tum";
}

function shiftDay(day: string, delta: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

function rangeBounds(range: Range, day: string): { from?: string; to?: string } {
  if (range === "gun") return { from: day, to: day };
  if (range === "7g") return { from: shiftDay(day, -6), to: day };
  return {};
}

function rangeHeadline(range: Range, day: string, t: Dictionary): string {
  const p = t.evaluation.perf;
  if (range === "gun") return p.headline_day.replace("{day}", day);
  if (range === "7g") return p.headline_week.replace("{from}", shiftDay(day, -6)).replace("{to}", day);
  return p.allTime;
}

const TABS = ["canli", "mac-oncesi", "backtest", "pattern"] as const;
type Tab = (typeof TABS)[number];
/** Canlı sekmesi ekrandaki kararı ölçer: 27 Ekim'den beri takım gücü modeli (live-poisson-v1.1). */
const LIVE_RULE_VERSION = "live-poisson-v1.1";
/** 19–27 Ekim ekrandaki kural; şimdi onay olarak duruyor. */
const LIVE_ARCHIVE_RULE_VERSION = "live-arch-v2";
/** Takım gücü modelinin gölge dönemi (19–27 Ekim). */
const LIVE_POISSON_SHADOW_VERSION = "live-poisson-v1";
/** Eski kural (18 Ekim 2026'ya kadar): arşiv başına işaret, n<5 dahil — geçmiş ayrı gösterilir. */
const LIVE_ARCHIVE_OLD_VERSION = "live-arch-v1";
/** Maç öncesi: ekranda Dixon-Coles (v5); arşiv havuzu (v4) gölgede ölçülmeye devam eder. */
const PREMATCH_RULE_VERSION = "ft-display-v5";
const PREMATCH_SHADOW_VERSION = "ft-display-v4.1";
const HT_RULE_VERSION = "ht-display-v1";
const TAB_SOURCE = { canli: "live_ht", "mac-oncesi": "top_pick" } as const;
const TAB_GROUPS = {
  canli: ["period_market", "league", "week"],
  "mac-oncesi": ["tier", "agreement", "market", "league", "week"],
} as const satisfies Record<keyof typeof TAB_SOURCE, readonly string[]>;

function resolveTab(raw: string | string[] | undefined): Tab {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return (TABS as readonly string[]).includes(value ?? "") ? (value as Tab) : "canli";
}

function RangeBar({ active, date, tab, t, scopeQuery }: { active: Range; date: string; tab: Tab; t: Dictionary; scopeQuery: string }) {
  const p = t.evaluation.perf;
  const labels: Record<Range, string> = { gun: p.range_day, "7g": p.range_week, tum: p.range_all };
  return (
    <div role="group" aria-label={p.rangeLabel} className="flex flex-wrap items-center gap-1">
      <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{p.rangeLabel}:</span>
      {RANGES.map((r) => (
        <Link
          key={r}
          href={`/degerlendirme?date=${date}&tab=${tab}&aralik=${r}${scopeQuery}`}
          aria-current={r === active ? "true" : undefined}
          className="px-2.5 py-1 font-semibold"
          style={{
            fontSize: "var(--nv-text-xs)",
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: r === active ? "var(--nv-accent-blue-dim)" : "var(--nv-bg-elevated)",
            color: r === active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
          }}
        >
          {labels[r]}
        </Link>
      ))}
    </div>
  );
}

/** Gölge ligler açıkken: ana ligler ile gölgedeki (deneme) liglerin karnesi ayrı ayrı. */
function ScopeBar({ active, date, tab, range, t }: { active: PerformanceScope; date: string; tab: Tab; range: Range; t: Dictionary }) {
  const p = t.evaluation.perf;
  const items: [PerformanceScope, string, string][] = [["main", p.scopeMain, ""], ["shadow", p.scopeShadow, "&kapsam=golge"]];
  return (
    <div role="group" aria-label={t.nav.shadowHint} className="flex flex-wrap items-center gap-1">
      {items.map(([key, label, query]) => (
        <Link
          key={key}
          href={`/degerlendirme?date=${date}&tab=${tab}&aralik=${range}${query}`}
          aria-current={key === active ? "true" : undefined}
          className="px-2.5 py-1 font-semibold"
          style={{
            fontSize: "var(--nv-text-xs)",
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: key === active ? (key === "shadow" ? "var(--nv-accent-amber-dim)" : "var(--nv-accent-blue-dim)") : "var(--nv-bg-elevated)",
            color: key === active ? (key === "shadow" ? "var(--nv-accent-amber)" : "var(--nv-accent-blue)") : "var(--nv-text-secondary)",
          }}
        >
          {label}
        </Link>
      ))}
    </div>
  );
}

function TabBar({ active, date, range, t, scopeQuery }: { active: Tab; date: string; range: Range; t: Dictionary; scopeQuery: string }) {
  const labels: Record<Tab, string> = {
    canli: t.evaluation.tabs.live,
    "mac-oncesi": t.evaluation.tabs.prematch,
    backtest: t.evaluation.tabs.backtest,
    pattern: t.evaluation.tabs.pattern,
  };
  return (
    // Sekmeler ayrı sayfalara giden bağlantılar → ARIA sekme değil, gezinme (ok tuşu davranışı gerekmez).
    <nav aria-label={t.evaluation.title} className="flex gap-1 px-[var(--nv-page-gutter)] pt-3 overflow-x-auto">
      {TABS.map((tab) => (
        <Link
          key={tab}
          aria-current={tab === active ? "page" : undefined}
          href={`/degerlendirme?date=${date}&tab=${tab}&aralik=${range}${scopeQuery}`}
          className="px-3 py-1.5 font-semibold whitespace-nowrap"
          style={{
            fontSize: "var(--nv-text-sm)",
            borderRadius: "var(--nv-radius-md)",
            backgroundColor: tab === active ? "var(--nv-accent-blue-dim)" : "transparent",
            color: tab === active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
          }}
        >
          {labels[tab]}
        </Link>
      ))}
    </nav>
  );
}

export default async function DegerlendirmePage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", {
    timeZone: ISTANBUL_TZ,
  });
  const date = resolvePageDate(params.date, today);
  if (date === null) redirect("/degerlendirme");
  const tab = resolveTab(params.tab);
  const range = resolveRange(params.aralik);
  const bounds = rangeBounds(range, date);
  const rawRun = Array.isArray(params.run) ? params.run[0] : params.run;
  const runId = rawRun && /^\d{1,9}$/.test(rawRun) ? Number(rawRun) : null;

  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  const locale: Locale = isLocale(raw) ? raw : defaultLocale;
  const t = getDictionary(locale);
  // Gölge ligler sadece kenar menüdeki anahtar açıkken seçilebilir
  const shadowOn = shadowFromCookie(cookieStore.get(SHADOW_COOKIE)?.value);
  const rawScope = Array.isArray(params.kapsam) ? params.kapsam[0] : params.kapsam;
  const scope: PerformanceScope = shadowOn && rawScope === "golge" ? "shadow" : "main";
  const scopeQuery = scope === "shadow" ? "&kapsam=golge" : "";

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      {/* Baslik */}
      <div
        className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <div className="flex items-center justify-between">
          <h1
            className="font-bold"
            style={{
              fontSize: "var(--nv-text-xl)",
              color: "var(--nv-text-primary)",
              letterSpacing: "var(--nv-tracking-tight)",
            }}
          >
            {t.evaluation.title}
          </h1>
          <span
            className="nv-badge"
            style={{
              backgroundColor: "var(--nv-bg-elevated)",
              color: "var(--nv-text-secondary)",
            }}
          >
            {date}
          </span>
        </div>
      </div>

      <TabBar active={tab} date={date} range={range} t={t} scopeQuery={scopeQuery} />

      {/* Gün sekmeleri — backtest bir tarih aralığını özetler, güne bağlı değil */}
      {tab !== "backtest" && (
        <DayTabs
          referenceDate={today}
          activeDate={date}
          basePath="/degerlendirme"
          range="past"
          locale={locale}
          extraQuery={`tab=${tab}&aralik=${range}${scopeQuery}`}
        />
      )}

      <div className="flex-1 overflow-y-auto">
        {tab === "backtest" ? (
          <div className="grid gap-4 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
            <Suspense fallback={<EvalSkeleton />}>
              <BacktestOverview runId={runId} t={t} />
            </Suspense>
          </div>
        ) : tab === "pattern" ? (
          <>
            <p className="px-[var(--nv-page-gutter)] pt-3" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", maxWidth: "var(--nv-max-content)" }}>
              {t.evaluation.patternNote}
            </p>
            <Suspense fallback={<EvalSkeleton />}>
              <EvalList date={date} t={t} />
            </Suspense>
          </>
        ) : (
          <div className="grid gap-4 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
            {shadowOn && <ScopeBar active={scope} date={date} tab={tab} range={range} t={t} />}
            <RangeBar active={range} date={date} tab={tab} t={t} scopeQuery={scopeQuery} />
            {tab === "canli" && (
              <Suspense fallback={null}>
                <LiveCoverage t={t} scope={scope} />
              </Suspense>
            )}
            <Suspense fallback={<EvalSkeleton />}>
              <PerformanceOverview
                scope={scope}
                source={TAB_SOURCE[tab]}
                t={t}
                groups={TAB_GROUPS[tab]}
                ruleVersion={tab === "canli" ? LIVE_RULE_VERSION : PREMATCH_RULE_VERSION}
                hint={tab === "canli" ? t.evaluation.perf.liveSummaryNote : undefined}
                dateFrom={bounds.from}
                dateTo={bounds.to}
                headline={rangeHeadline(range, date, t)}
              />
            </Suspense>
            <Suspense fallback={<EvalSkeleton />}>
              {tab === "canli" ? <LiveDayList day={date} t={t} scope={scope} /> : <PredictionDayList source={TAB_SOURCE[tab]} day={date} t={t} ruleVersion={PREMATCH_RULE_VERSION} scope={scope} />}
            </Suspense>
            {tab === "canli" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="live_ht"
                  t={t}
                  groups={["period_market", "archive"]}
                  ruleVersion={LIVE_ARCHIVE_RULE_VERSION}
                  title={t.evaluation.perf.liveV2Title}
                  hint={t.evaluation.perf.liveV2Hint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
            {tab === "canli" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="live_ht"
                  t={t}
                  groups={["period_market"]}
                  ruleVersion={LIVE_POISSON_SHADOW_VERSION}
                  title={t.evaluation.perf.livePoissonV1Title}
                  hint={t.evaluation.perf.livePoissonV1Hint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
            {tab === "canli" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="live_ht"
                  t={t}
                  groups={["risk", "archive"]}
                  ruleVersion={LIVE_ARCHIVE_OLD_VERSION}
                  title={t.evaluation.perf.liveOldTitle}
                  hint={t.evaluation.perf.liveOldHint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
            {tab === "mac-oncesi" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="top_pick"
                  t={t}
                  groups={["market", "tier"]}
                  ruleVersion={HT_RULE_VERSION}
                  title={t.evaluation.perf.htTitle}
                  hint={t.evaluation.perf.htHint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
            {tab === "mac-oncesi" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="top_pick"
                  t={t}
                  groups={["tier", "market"]}
                  ruleVersion={PREMATCH_SHADOW_VERSION}
                  title={t.evaluation.perf.prematchShadowTitle}
                  hint={t.evaluation.perf.prematchShadowHint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
            {tab === "mac-oncesi" && (
              <Suspense fallback={<EvalSkeleton />}>
                <PerformanceOverview
                  scope={scope}
                  source="market_summary"
                  t={t}
                  groups={["archive", "period_market"]}
                  title={t.evaluation.perf.marketSummaryTitle}
                  hint={t.evaluation.perf.marketSummaryHint}
                  dateFrom={bounds.from}
                  dateTo={bounds.to}
                  headline={rangeHeadline(range, date, t)}
                />
              </Suspense>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
