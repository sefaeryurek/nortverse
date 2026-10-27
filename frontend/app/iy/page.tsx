import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import DayTabs from "@/components/DayTabs";
import { getHtStrategy } from "@/lib/api";
import type { HtMatch, HtPick } from "@/lib/api";
import { formatTime, resolvePageDate } from "@/lib/dates";
import { type Dictionary, type Locale, COOKIE_NAME, defaultLocale, getDictionary, isLocale } from "@/lib/i18n";
import { leagueDisplay } from "@/lib/leagues";
import { liveMarketLabel, liveSelectionLabel } from "@/lib/live-labels";
import { SHADOW_COOKIE, shadowFromCookie } from "@/lib/shadow";

export const metadata: Metadata = {
  title: "İY Strateji",
  description: "Maç öncesi ilk yarı tahminleri",
};

interface Props {
  searchParams: Promise<{ date?: string | string[] }>;
}

function pct(value: number, locale: Locale): string {
  const v = value.toFixed(1);
  return locale === "en" ? `${v}%` : `%${v.replace(".", ",")}`;
}

function PickChip({ pick, t, locale }: { pick: HtPick; t: Dictionary; locale: Locale }) {
  const strong = pick.tier === "high";
  return (
    <div
      className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 px-2.5 py-1.5 min-w-0"
      style={{
        borderRadius: "var(--nv-radius-md)",
        backgroundColor: strong ? "var(--nv-accent-green-dim)" : "var(--nv-bg-elevated)",
        border: "1px solid var(--nv-border-subtle)",
      }}
    >
      <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{liveMarketLabel("ht", pick.market, t)}</span>
      <span className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{liveSelectionLabel(pick.selection, t)}</span>
      <span className="font-extrabold" style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-sm)", color: strong ? "var(--nv-accent-green)" : "var(--nv-text-primary)" }}>
        {pct(pick.pct, locale)}
      </span>
      {pick.base_pct != null && (
        <span style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
          {t.ht.leagueAvg.replace("{pct}", locale === "en" ? pick.base_pct.toFixed(1) : pick.base_pct.toFixed(1).replace(".", ","))}
        </span>
      )}
    </div>
  );
}

function Bar({ label, value, locale }: { label: string; value: number; locale: Locale }) {
  return (
    <div className="min-w-0">
      <div className="flex justify-between gap-2" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
        <span className="truncate">{label}</span>
        <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>{pct(value, locale)}</span>
      </div>
      <div className="nv-pct-bar mt-1" style={{ height: 4 }}>
        <div style={{ width: `${Math.min(100, value)}%`, height: "100%", backgroundColor: "var(--nv-accent-blue)", borderRadius: 2 }} />
      </div>
    </div>
  );
}

function MatchCard({ match, t, locale }: { match: HtMatch; t: Dictionary; locale: Locale }) {
  const { flag, short } = leagueDisplay(null, match.league_name);
  const p = match.probs;
  return (
    <article className="nv-card p-3 space-y-3 min-w-0">
      <header className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
        <span aria-hidden="true">{flag}</span>
        <span style={{ color: "var(--nv-text-tertiary)" }}>{short}{match.kickoff_time ? ` · ${formatTime(match.kickoff_time)}` : ""}</span>
        {match.shadow && (
          <span className="px-1.5 font-semibold" title={t.common.shadowBadgeHint}
            style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-accent-amber-dim)", color: "var(--nv-accent-amber)" }}>
            {t.common.shadowBadge}
          </span>
        )}
        <span className="flex-1" />
        {match.final_ht ? (
          <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{t.ht.finalHt} {match.final_ht}</span>
        ) : (
          <span style={{ fontSize: "var(--nv-text-2xs)", color: match.frozen ? "var(--nv-accent-green)" : "var(--nv-text-tertiary)" }}>
            {match.frozen ? t.ht.frozen : t.ht.notFrozen}
          </span>
        )}
      </header>
      <Link href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
        className="block font-semibold hover:underline" style={{ fontSize: "var(--nv-text-base)", color: "var(--nv-text-primary)" }}>
        {match.home_team} - {match.away_team}
      </Link>

      {match.picks.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {match.picks.map((pick) => <PickChip key={`${pick.market}:${pick.selection}`} pick={pick} t={t} locale={locale} />)}
        </div>
      ) : (
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.ht.noPick}</p>
      )}

      {p && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2 min-w-0">
            <Bar label={`${liveMarketLabel("ht", "result", t)} 1`} value={p.result["1"]} locale={locale} />
            <Bar label={`${liveMarketLabel("ht", "result", t)} X`} value={p.result["X"]} locale={locale} />
            <Bar label={`${liveMarketLabel("ht", "result", t)} 2`} value={p.result["2"]} locale={locale} />
          </div>
          <div className="space-y-2 min-w-0">
            <Bar label={t.ht.goal} value={p.ou_05.over} locale={locale} />
            <Bar label={t.ht.under15} value={p.ou_15.under} locale={locale} />
            <Bar label={t.ht.homeScores} value={p.ev_05.over} locale={locale} />
          </div>
          <div className="sm:col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
            <span>{t.ht.expectedGoals}: <b style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>{p.lambda.home.toFixed(2)} – {p.lambda.away.toFixed(2)}</b></span>
            <span>{t.ht.topScores}: {p.top_scores.map((s) => `${s.score} (${pct(s.pct, locale)})`).join(" · ")}</span>
          </div>
        </div>
      )}
    </article>
  );
}

async function MatchList({ date, locale, shadow }: { date: string; locale: Locale; shadow: boolean }) {
  const t = getDictionary(locale);
  let matches: HtMatch[] = [];
  try {
    matches = (await getHtStrategy(date, shadow)).matches;
  } catch {
    return <p className="nv-card p-4 m-4" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{t.common.loadError}</p>;
  }
  if (matches.length === 0) {
    return <p className="nv-card p-6 m-4 text-center" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{t.ht.empty}</p>;
  }
  // Kararı olan maçlar önce
  const sorted = [...matches].sort((a, b) => (b.picks.length > 0 ? 1 : 0) - (a.picks.length > 0 ? 1 : 0));
  return (
    <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
      {sorted.map((m) => <MatchCard key={m.match_id} match={m} t={t} locale={locale} />)}
    </div>
  );
}

export default async function IyPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const date = resolvePageDate(params.date, today, true);
  if (date === null) redirect("/iy");
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  const locale: Locale = isLocale(raw) ? raw : defaultLocale;
  const shadow = shadowFromCookie(cookieStore.get(SHADOW_COOKIE)?.value);
  const t = getDictionary(locale);

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-tight)" }}>
            {t.ht.title}
          </h1>
          <span className="px-2 py-0.5 font-semibold" style={{ fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-accent-amber-dim)", color: "var(--nv-accent-amber)" }}>
            {t.ht.trialBadge}
          </span>
        </div>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.ht.subtitle}</p>
        <p className="mt-2" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", maxWidth: "65ch" }}>{t.ht.trialNote}</p>
      </div>
      <DayTabs referenceDate={today} activeDate={date} basePath="/iy" locale={locale} />
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<p className="p-6" style={{ color: "var(--nv-text-tertiary)" }}>…</p>}>
          <MatchList date={date} locale={locale} shadow={shadow} />
        </Suspense>
      </div>
    </div>
  );
}
