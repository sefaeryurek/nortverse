import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { isRecentScoreDate, resolvePageDate } from "@/lib/dates";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import AutoRefresh from "@/components/AutoRefresh";
import RetryButton from "@/components/RetryButton";
import { getResults } from "@/lib/api";
import { showResultMatch } from "@/lib/match-visibility";
import { leagueDisplay } from "@/lib/leagues";
import type { ResultMatch } from "@/lib/types";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sonuçlar",
  description: "Biten futbol maçları ve skorları — tahmin sonuçları",
};

/* ------------------------------------------------------------------ */
/*  Skeleton                                                          */
/* ------------------------------------------------------------------ */

function ResultSkeleton() {
  return (
    <div
      className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
      style={{ maxWidth: "var(--nv-max-content)" }}
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="nv-card p-4">
          <div className="flex items-center gap-3">
            {/* League */}
            <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
            {/* Time */}
            <div className="nv-skeleton" style={{ width: 40, height: 14 }} />
            <div className="flex-1" />
            {/* Score */}
            <div className="nv-skeleton" style={{ width: 56, height: 28 }} />
          </div>
          <div className="flex items-center gap-3 mt-3">
            {/* Home */}
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
            <div
              className="nv-skeleton"
              style={{ width: 16, height: 10 }}
            />
            {/* Away */}
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
          </div>
          <div className="flex justify-end mt-3">
            <div className="nv-skeleton" style={{ width: 64, height: 28 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

interface Props {
  searchParams: Promise<{ date?: string | string[]; q?: string | string[] }>;
}

function formatTime(iso: string | null): string {
  if (!iso) return "--:--";
  try {
    return new Date(iso).toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Istanbul",
    });
  } catch {
    return "--:--";
  }
}

/** Skor durumuna göre renk token'ı döner */
function scoreColor(
  home: number | null,
  away: number | null,
): string {
  if (home === null || away === null) return "var(--nv-text-secondary)";
  if (home > away) return "var(--nv-win)";
  if (home < away) return "var(--nv-loss)";
  return "var(--nv-draw)";
}

/* ------------------------------------------------------------------ */
/*  ResultRow                                                         */
/* ------------------------------------------------------------------ */

function ResultRow({ match }: { match: ResultMatch }) {
  const timeStr = formatTime(match.kickoff_time);
  const { flag, short } = leagueDisplay(match.league_code, match.league_name);

  const hasScore =
    match.actual_ft_home !== null && match.actual_ft_away !== null;
  const scoreStr = hasScore
    ? `${match.actual_ft_home} - ${match.actual_ft_away}`
    : null;
  const htStr =
    match.actual_ht_home !== null && match.actual_ht_away !== null
      ? `IY ${match.actual_ht_home}-${match.actual_ht_away}`
      : null;

  const color = scoreColor(match.actual_ft_home, match.actual_ft_away);

  return (
    <div className="nv-card p-3 sm:p-4 nv-fade-in">
      {/* Üst satır: Lig + Saat + Skor */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Lig */}
        <span
          className="flex items-center gap-1 flex-shrink-0"
          title={match.league_name ?? match.league_code ?? ""}
        >
          <span className="text-base leading-none" aria-hidden>
            {flag}
          </span>
          <span
            className="font-semibold truncate"
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
              maxWidth: 56,
            }}
          >
            {short}
          </span>
        </span>

        {/* Saat */}
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

        <div className="flex-1" />

        {/* Skor */}
        {scoreStr && (
          <div className="flex flex-col items-end gap-0.5 flex-shrink-0">
            <span
              className="font-bold px-3 py-1"
              style={{
                fontFamily: "var(--nv-font-mono)",
                fontSize: "var(--nv-text-lg)",
                color: "var(--nv-text-on-accent)",
                backgroundColor: color,
                borderRadius: "var(--nv-radius-md)",
                letterSpacing: "0.05em",
                lineHeight: 1.2,
              }}
            >
              {scoreStr}
            </span>
            {htStr && (
              <span
                className="nv-badge"
                style={{
                  backgroundColor: "var(--nv-bg-elevated)",
                  color: "var(--nv-text-tertiary)",
                  fontSize: 10,
                  padding: "1px 6px",
                }}
              >
                {htStr}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Alt satır: Takımlar + Analiz */}
      <div className="flex items-center gap-2 mt-2.5">
        {/* Takimlar */}
        <div className="flex-1 min-w-0 flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-2">
          <span
            className="truncate font-medium"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-text-primary)",
            }}
          >
            {match.home_team}
          </span>
          <span
            className="hidden sm:inline flex-shrink-0"
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            vs
          </span>
          <span
            className="truncate font-medium"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-text-primary)",
            }}
          >
            {match.away_team}
          </span>
        </div>

        {/* Analiz linki */}
        <Link
          href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
          prefetch={false}
          className="flex-shrink-0 flex items-center justify-center min-h-[36px] px-3 py-1.5 font-medium transition-colors"
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
/*  ResultList (async server component)                               */
/* ------------------------------------------------------------------ */

async function ResultList({ date, q }: { date: string; q: string }) {
  let matches: ResultMatch[] = [];
  let error = "";
  try {
    const now = new Date();
    matches = (await getResults(date)).filter((match) =>
      showResultMatch(match, now.getTime()),
    );
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
  }

  /* --- Hata durumu --- */
  if (error) {
    return (
      <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
        <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
          <div className="flex justify-center">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--nv-accent-red)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <p
            className="font-medium"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-accent-red)",
            }}
          >
            {error}
          </p>
          <RetryButton />
        </div>
      </div>
    );
  }

  /* --- Boş durum --- */
  if (matches.length === 0) {
    const today = new Date().toLocaleDateString("sv-SE", {
      timeZone: "Europe/Istanbul",
    });
    const isToday = date === today;
    return (
      <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
        <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
          <div className="flex justify-center">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--nv-text-tertiary)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          <p
            className="font-medium"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-text-secondary)",
            }}
          >
            {isToday
              ? "Bugün için henüz doğrulanmış maç sonucu kaydı yok."
              : "Bu tarihte doğrulanmış maç sonucu kaydı bulunamadı."}
          </p>
          {isToday && (
            <p
              style={{
                fontSize: "var(--nv-text-xs)",
                color: "var(--nv-text-tertiary)",
              }}
            >
              Başlayacak ve süren maçlar Bülten sayfasında görünür.
            </p>
          )}
          <Link
            href={`/bulten?date=${date}`}
            className="inline-block font-medium transition-colors"
            style={{
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-accent-blue)",
            }}
          >
            Bültendeki maçlara bak
          </Link>
        </div>
      </div>
    );
  }

  /* --- Filtreleme ve listeleme --- */
  const normalized = q.toLocaleLowerCase("tr-TR");
  const visible = matches.filter(
    (match) =>
      !normalized ||
      [
        match.home_team,
        match.away_team,
        match.league_name ?? match.league_code ?? "",
      ].some((value) => value.toLocaleLowerCase("tr-TR").includes(normalized)),
  );
  const lastChecked = matches.reduce<string | null>(
    (latest, match) =>
      match.score_checked_at && (!latest || match.score_checked_at > latest)
        ? match.score_checked_at
        : latest,
    null,
  );

  return (
    <div style={{ maxWidth: "var(--nv-max-content)" }}>
      {/* Özet çubuğu */}
      <div
        className="flex flex-wrap items-center gap-3 px-[var(--nv-page-gutter)] py-3"
        style={{
          borderBottom: "1px solid var(--nv-border)",
        }}
      >
        <span
          className="flex items-center gap-1.5"
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-secondary)",
          }}
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
          {matches.length} biten maç
        </span>

        {lastChecked && (
          <span
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            Son kontrol:{" "}
            {new Date(lastChecked).toLocaleString("tr-TR", {
              timeZone: "Europe/Istanbul",
              dateStyle: "short",
              timeStyle: "short",
            })}
          </span>
        )}
      </div>

      {/* Arama */}
      <div
        className="px-[var(--nv-page-gutter)] py-3 space-y-2"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <form action="/sonuclar" className="flex max-w-xl gap-2">
          <input type="hidden" name="date" value={date} />
          <input
            name="q"
            defaultValue={q}
            maxLength={80}
            aria-label="Takım veya lig ara"
            placeholder="Takım veya lig ara"
            className="min-w-0 flex-1 px-3 py-2 transition-colors"
            style={{
              fontSize: "var(--nv-text-sm)",
              backgroundColor: "var(--nv-bg-surface)",
              border: "1px solid var(--nv-border)",
              borderRadius: "var(--nv-radius-md)",
              color: "var(--nv-text-primary)",
            }}
          />
          <button
            type="submit"
            className="px-4 py-2 font-semibold transition-colors"
            style={{
              fontSize: "var(--nv-text-sm)",
              backgroundColor: "var(--nv-accent-blue)",
              color: "var(--nv-text-inverse)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            Ara
          </button>
        </form>
        {q && (
          <p
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-secondary)",
            }}
          >
            {visible.length} eşleşen maç
          </p>
        )}
      </div>

      {/* Sonuç kartları */}
      {visible.length === 0 && (
        <div className="flex items-center justify-center py-16 px-[var(--nv-page-gutter)]">
          <div className="nv-card p-6 text-center max-w-sm w-full">
            <div className="flex justify-center mb-3">
              <svg
                width="36"
                height="36"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--nv-text-tertiary)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <p
              style={{
                fontSize: "var(--nv-text-sm)",
                color: "var(--nv-text-secondary)",
              }}
            >
              Bu filtreyle eşleşen maç bulunamadı.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4">
        {visible.map((m) => (
          <ResultRow key={m.match_id} match={m} />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default async function SonuclarPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", {
    timeZone: "Europe/Istanbul",
  });
  const date = resolvePageDate(params.date, today);
  if (date === null) redirect("/sonuclar");
  const q =
    typeof params.q === "string" ? params.q.trim().slice(0, 80) : "";

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      {/* Başlık */}
      <div
        className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0"
        style={{
          borderBottom: "1px solid var(--nv-border)",
        }}
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
            Sonuçlar
          </h1>
          <span className="nv-badge" style={{
            backgroundColor: "var(--nv-bg-elevated)",
            color: "var(--nv-text-secondary)",
          }}>
            {date}
          </span>
        </div>
      </div>

      {/* Gün sekmeleri */}
      <DayTabs
        referenceDate={today}
        activeDate={date}
        basePath="/sonuclar"
        range="past"
      />
      {isRecentScoreDate(date, today) && <AutoRefresh />}

      {/* Sonuç listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<ResultSkeleton />}>
          <ResultList date={date} q={q} />
        </Suspense>
      </div>
    </div>
  );
}
