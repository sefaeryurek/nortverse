import { redirect } from "next/navigation";
import { isRecentScoreDate, resolvePageDate } from "@/lib/dates";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import RetryButton from "@/components/RetryButton";
import BultenRow from "@/components/BultenRow";
import AutoRefresh from "@/components/AutoRefresh";
import { getFixture } from "@/lib/api";
import { showBulletinMatch } from "@/lib/match-visibility";
import type { FixtureMatch } from "@/lib/types";
import Link from "next/link";

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

async function MatchList({ date }: { date: string }) {
  let matches: FixtureMatch[] = [];
  let error = "";
  try {
    const now = new Date();
    const today = now.toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
    matches = (await getFixture(date)).filter((match) => showBulletinMatch(match, now.getTime(), today, date));
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
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
              fontSize: "20px",
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
            Veriler şu anda yüklenemiyor. Biraz sonra tekrar deneyebilirsiniz.
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
              fontSize: "20px",
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
            Bu tarihte bültende bekleyen maç yok.
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
            Kesin sonuçlara bak
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
        <span className="nv-badge nv-badge-blue">{matches.length} maç</span>
        {liveCount > 0 && (
          <span className="nv-badge nv-badge-red nv-live-pulse">
            Canlı: {liveCount}
          </span>
        )}
        {scheduledCount > 0 && (
          <span className="nv-badge nv-badge-green">
            Başlayacak: {scheduledCount}
          </span>
        )}
      </div>

      {/* Mac listesi */}
      <div style={{ padding: "var(--nv-space-sm) var(--nv-page-gutter)" }}>
        {sorted.map(({ match, timeStr }) => (
          <BultenRow key={match.match_id} match={match} timeStr={timeStr} />
        ))}
      </div>
    </>
  );
}

export default async function BultenPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const date = resolvePageDate(params.date, today, true);
  if (date === null) redirect("/bulten");

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
            Günlük Bülten
          </h1>
          <span className="nv-badge nv-badge-blue">
            {date}
          </span>
        </div>
      </div>

      {/* Gun sekmeleri */}
      <DayTabs referenceDate={today} activeDate={date} />
      {isRecentScoreDate(date, today) && <AutoRefresh />}

      {/* Mac listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<BultenSkeleton />}>
          <MatchList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
