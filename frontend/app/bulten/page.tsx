import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { formatTime, isRecentScoreDate, istanbulDate, resolvePageDate } from "@/lib/dates";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import RetryButton from "@/components/RetryButton";
import BultenRow from "@/components/BultenRow";
import AutoRefresh from "@/components/AutoRefresh";
import { getFixture, getPatternStatus } from "@/lib/api";
import type { PatternStatusMap } from "@/lib/api";
import { showBulletinMatch } from "@/lib/match-visibility";
import type { FixtureMatch } from "@/lib/types";
import { leagueDisplay } from "@/lib/leagues";
import Link from "next/link";
import { type Locale, COOKIE_NAME, defaultLocale, getDictionary, isLocale } from "@/lib/i18n";
import { SHADOW_COOKIE, shadowFromCookie } from "@/lib/shadow";

export const metadata: Metadata = {
  title: "Bülten",
  description: "Günün futbol maçları — istatistiksel analiz ve tahminler",
};

function BultenSkeleton() {
  return (
    <div style={{ padding: "var(--nv-space-sm) var(--nv-page-gutter)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="nv-card"
          style={{
            marginBottom: "var(--nv-space-sm)",
            padding: "var(--nv-space-md) var(--nv-space-lg)",
            display: "flex",
            alignItems: "center",
            gap: "var(--nv-space-md)",
          }}
        >
          {/* Saat iskeleti */}
          <div
            className="nv-skeleton"
            style={{
              width: 52,
              height: 36,
              flexShrink: 0,
              borderRadius: "var(--nv-radius-sm)",
            }}
          />
          {/* Lig iskeleti */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div
              className="nv-skeleton"
              style={{ width: 20, height: 20, borderRadius: "var(--nv-radius-full)" }}
            />
            <div
              className="nv-skeleton"
              style={{ width: 72, height: 12, borderRadius: "var(--nv-radius-sm)" }}
            />
          </div>
          {/* Takim iskeleti */}
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
            <div
              className="nv-skeleton"
              style={{ height: 14, flex: 1, borderRadius: "var(--nv-radius-sm)" }}
            />
            <div
              className="nv-skeleton"
              style={{ width: 24, height: 12, borderRadius: "var(--nv-radius-sm)" }}
            />
            <div
              className="nv-skeleton"
              style={{ height: 14, flex: 1, borderRadius: "var(--nv-radius-sm)" }}
            />
          </div>
          {/* Chevron iskeleti */}
          <div
            className="nv-skeleton"
            style={{ width: 28, height: 28, borderRadius: "var(--nv-radius-full)", flexShrink: 0 }}
          />
        </div>
      ))}
    </div>
  );
}

interface Props {
  searchParams: Promise<{ date?: string | string[] }>;
}



function sortMatches(
  matches: FixtureMatch[],
): { match: FixtureMatch; timeStr: string }[] {
  const withTime = matches.map((m) => ({
    match: m,
    timeStr: formatTime(m.kickoff_time),
    ts: m.kickoff_time ? new Date(m.kickoff_time).getTime() : Infinity,
  }));

  return withTime
    .sort((a, b) => a.ts - b.ts)
    .map(({ match, timeStr }) => ({ match, timeStr }));
}

async function MatchList({ date, locale, shadow }: { date: string; locale: Locale; shadow: boolean }) {
  const t = getDictionary(locale);
  let matches: FixtureMatch[] = [];
  let patternStatus: PatternStatusMap = {};
  let error = "";
  try {
    const now = new Date();
    const today = istanbulDate(now);
    matches = (await getFixture(date, shadow))
      .filter((match) => showBulletinMatch(match, now.getTime(), today, date))
      .filter((match) => match.has_prediction);
    if (matches.length > 0) {
      try {
        patternStatus = await getPatternStatus(matches.map((m) => m.match_id));
      } catch {
        /* Pattern status opsiyonel — hata olursa boş kalır */
      }
    }
  } catch (e) {
    error = e instanceof Error ? e.message : t.common.connectionError;
  }

  if (error) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ padding: "var(--nv-space-3xl) var(--nv-page-gutter)" }}
      >
        <div
          className="nv-card nv-fade-in"
          style={{
            maxWidth: 400,
            width: "100%",
            padding: "var(--nv-space-2xl)",
            textAlign: "center",
            borderColor: "var(--nv-accent-red)",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              margin: "0 auto var(--nv-space-md)",
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: "var(--nv-accent-red-dim)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "var(--nv-text-lg)",
              color: "var(--nv-accent-red)",
              fontWeight: 700,
            }}
          >
            !
          </div>
          <p
            style={{
              fontSize: "var(--nv-text-sm)",
              fontWeight: 500,
              color: "var(--nv-accent-red)",
              marginBottom: "var(--nv-space-sm)",
            }}
          >
            {error}
          </p>
          <p
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
              marginBottom: "var(--nv-space-lg)",
            }}
          >
            {t.common.loadError}
          </p>
          <RetryButton />
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ padding: "var(--nv-space-3xl) var(--nv-page-gutter)" }}
      >
        <div
          className="nv-card nv-fade-in"
          style={{
            maxWidth: 400,
            width: "100%",
            padding: "var(--nv-space-2xl)",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              margin: "0 auto var(--nv-space-md)",
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: "var(--nv-accent-blue-dim)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "var(--nv-text-lg)",
            }}
          >
            --
          </div>
          <p
            style={{
              fontSize: "var(--nv-text-sm)",
              fontWeight: 500,
              color: "var(--nv-text-secondary)",
              marginBottom: "var(--nv-space-sm)",
            }}
          >
            {t.bulletin.noMatches}
          </p>
          <p
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
              marginBottom: "var(--nv-space-md)",
            }}
          >
            {t.bulletin.pipelineNote}
          </p>
          <Link
            href={`/sonuclar?date=${date}`}
            style={{
              display: "inline-block",
              marginTop: "var(--nv-space-md)",
              fontSize: "var(--nv-text-sm)",
              color: "var(--nv-accent-blue)",
              textDecoration: "none",
              fontWeight: 500,
            }}
          >
            {t.bulletin.viewResults}
          </Link>
        </div>
      </div>
    );
  }

  const sorted = sortMatches(matches);
  const liveCount = matches.filter((m) => m.status === "live").length;
  const scheduledCount = matches.filter((m) => m.status === "scheduled").length;

  return (
    <>
      {/* Ozet bar */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "var(--nv-space-md)",
          padding: "var(--nv-space-sm) var(--nv-page-gutter)",
          borderBottom: "1px solid var(--nv-border)",
          fontSize: "var(--nv-text-xs)",
          color: "var(--nv-text-tertiary)",
        }}
      >
        <span className="nv-badge nv-badge-blue">{t.bulletin.matchCount.replace("{count}", String(matches.length))}</span>
        {liveCount > 0 && (
          <span className="nv-badge nv-badge-red nv-live-pulse">
            {t.bulletin.liveCount.replace("{count}", String(liveCount))}
          </span>
        )}
        {scheduledCount > 0 && (
          <span className="nv-badge nv-badge-green">
            {t.bulletin.scheduledCount.replace("{count}", String(scheduledCount))}
          </span>
        )}
      </div>

      {/* Mac listesi — lig bazli gruplama */}
      <div style={{ padding: "var(--nv-space-sm) var(--nv-page-gutter)" }}>
        {(() => {
          const groups: { league: string; flag: string; short: string; items: typeof sorted }[] = [];
          const seen = new Map<string, number>();
          for (const entry of sorted) {
            const key = entry.match.league_code || "other";
            let idx = seen.get(key);
            if (idx === undefined) {
              const ld = leagueDisplay(key, entry.match.league_name);
              idx = groups.length;
              seen.set(key, idx);
              groups.push({ league: entry.match.league_name || key, flag: ld.flag, short: ld.short, items: [] });
            }
            groups[idx].items.push(entry);
          }
          return groups.map((g) => (
            <div key={g.league} style={{ marginBottom: "var(--nv-space-md)" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "var(--nv-space-xs) 0",
                  fontSize: "var(--nv-text-xs)",
                  fontWeight: 600,
                  color: "var(--nv-text-secondary)",
                  letterSpacing: "0.02em",
                }}
              >
                <span>{g.flag}</span>
                <span>{g.league}</span>
                <span style={{ color: "var(--nv-text-tertiary)", fontWeight: 400 }}>
                  ({g.items.length})
                </span>
              </div>
              {g.items.map(({ match, timeStr }) => (
                <BultenRow
                  key={match.match_id}
                  match={match}
                  timeStr={timeStr}
                  patternStatus={patternStatus[match.match_id]}
                  t={t}
                  dateLocale={locale === "tr" ? "tr-TR" : "en-GB"}
                />
              ))}
            </div>
          ));
        })()}
      </div>
    </>
  );
}

export default async function BultenPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = istanbulDate();
  const date = resolvePageDate(params.date, today, true);
  if (date === null) redirect("/bulten");

  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  const shadow = shadowFromCookie(cookieStore.get(SHADOW_COOKIE)?.value);
  const locale: Locale = isLocale(raw) ? raw : defaultLocale;
  const t = getDictionary(locale);

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      {/* Header */}
      <div
        style={{
          padding: "var(--nv-space-lg) var(--nv-page-gutter)",
          borderBottom: "1px solid var(--nv-border)",
        }}
      >
        <div className="flex items-center justify-between">
          <h1
            style={{
              fontSize: "var(--nv-text-xl)",
              fontWeight: 700,
              color: "var(--nv-text-primary)",
              letterSpacing: "var(--nv-tracking-tight)",
            }}
          >
            {t.bulletin.title}
          </h1>
          <span className="nv-badge nv-badge-blue">
            {date}
          </span>
        </div>
      </div>

      {/* Gun sekmeleri */}
      <DayTabs referenceDate={today} activeDate={date} locale={locale} />
      {isRecentScoreDate(date, today) && <AutoRefresh />}

      {/* Mac listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<BultenSkeleton />}>
          <MatchList date={date} locale={locale} shadow={shadow} />
        </Suspense>
      </div>
    </div>
  );
}
