import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import RetryButton from "@/components/RetryButton";
import { getEvaluation } from "@/lib/api";
import { resolvePageDate } from "@/lib/dates";
import { leagueDisplay } from "@/lib/leagues";
import type { DailyEvaluation, MatchEvaluation, PatternEvaluation } from "@/lib/types";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Degerlendirme",
  description: "Gunluk tahmin isabeti degerlendirmesi",
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
          {total > 0 ? `%${pct.toFixed(0)}` : "-"}
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

function PatternBadge({
  pat,
  archiveLabel,
}: {
  pat: PatternEvaluation;
  archiveLabel: string;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-1.5"
      style={{ fontSize: "var(--nv-text-xs)" }}
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
      <HitBadge hit={pat.result_hit} label={`${pat.result_pick} %${pat.result_pct.toFixed(0)}`} />
      <HitBadge hit={pat.over_25_hit} label={`${pat.over_25_pick} %${pat.over_25_pct.toFixed(0)}`} />
      <HitBadge hit={pat.btts_hit} label={`${pat.btts_pick} %${pat.btts_pct.toFixed(0)}`} />
      <span style={{ color: "var(--nv-text-tertiary)" }}>
        ({pat.match_count} mac)
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  EvalRow                                                           */
/* ------------------------------------------------------------------ */

function EvalRow({ match }: { match: MatchEvaluation }) {
  const { flag } = leagueDisplay(match.league_code, match.league_name);
  const leagueName = match.league_name || match.league_code || "";

  const timeStr = match.kickoff_time
    ? (() => {
        try {
          return new Date(match.kickoff_time).toLocaleTimeString("tr-TR", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Europe/Istanbul",
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
          <PatternBadge pat={match.pattern_b} archiveLabel="A1" />
        )}
        {match.pattern_c && (
          <PatternBadge pat={match.pattern_c} archiveLabel="A2" />
        )}
        {!match.pattern_b && !match.pattern_c && (
          <span
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            Tahmin verisi yok
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
              label={match.score_list_hit ? `${match.actual_ft} listede` : `${match.actual_ft} listede degil`}
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
          Analiz
        </Link>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  EvalList (async server component)                                 */
/* ------------------------------------------------------------------ */

async function EvalList({ date }: { date: string }) {
  let data: DailyEvaluation | null = null;
  let error = "";
  try {
    data = await getEvaluation(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Baglanti hatasi";
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
        <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
          <p
            className="font-medium"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}
          >
            {error || "Veri alinamadi"}
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
            Bu tarihte degerlendirilebilecek bitmis mac bulunamadi.
          </p>
          <Link
            href={`/sonuclar?date=${date}`}
            className="inline-block font-medium transition-colors"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}
          >
            Sonuclar sayfasina bak
          </Link>
        </div>
      </div>
    );
  }

  const s = data.summary;

  return (
    <div style={{ maxWidth: "var(--nv-max-content)" }}>
      {/* Ozet kartlari */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-[var(--nv-page-gutter)] py-4">
        <SummaryCard label="Sonuc Isabeti" hit={s.result_hit} total={s.evaluated} pct={s.result_hit_pct} />
        <SummaryCard label="2.5 Ust/Alt" hit={s.over_25_hit} total={s.evaluated} pct={s.over_25_hit_pct} />
        <SummaryCard label="KG Isabeti" hit={s.btts_hit} total={s.evaluated} pct={s.btts_hit_pct} />
        <SummaryCard label="Skor Listesi" hit={s.score_list_hit} total={s.total_matches} pct={s.score_list_hit_pct} />
      </div>

      {/* Ozet bilgi cubugu */}
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
          {s.total_matches} bitmis mac
        </span>
        <span
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
        >
          {s.evaluated} tahminli
        </span>
      </div>

      {/* Mac kartlari */}
      <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4">
        {data.matches.map((m) => (
          <EvalRow key={m.match_id} match={m} />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

interface Props {
  searchParams: Promise<{ date?: string | string[] }>;
}

export default async function DegerlendirmePage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", {
    timeZone: "Europe/Istanbul",
  });
  const date = resolvePageDate(params.date, today);
  if (date === null) redirect("/degerlendirme");

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
            Degerlendirme
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

      {/* Gun sekmeleri */}
      <DayTabs
        referenceDate={today}
        activeDate={date}
        basePath="/degerlendirme"
        range="past"
      />

      {/* Degerlendirme listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<EvalSkeleton />}>
          <EvalList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
