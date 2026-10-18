"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getLiveHTMatches, getLivePrediction } from "@/lib/api";
import type { LiveArchiveSource, LiveHTMatch } from "@/lib/api";
import { ArchiveMatchList, ArchiveTable, HighlightList } from "@/components/LiveArchiveView";
import { leagueDisplay } from "@/lib/leagues";
import { formatTime } from "@/lib/dates";
import { minuteOrder } from "@/lib/live-order";
import { useLiveWs } from "@/lib/use-live-ws";
import type { WsStatus } from "@/lib/use-live-ws";
import { useLocale } from "@/lib/locale-context";

const POLL_INTERVAL = 45_000;
const WS_GRACE_MS = 3_000;
function ArchiveDetails({ match }: { match: LiveHTMatch }) {
  const { t } = useLocale();
  const a = t.live.archive;
  const [sources, setSources] = useState<LiveArchiveSource[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getLivePrediction(match.match_id, true)
      .then((detail) => { if (!cancelled) setSources(detail.archive_view.sources.filter((s) => s.archive !== "genel")); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [match.match_id]);

  return (
    <div className="px-3 pb-3 sm:px-4 sm:pb-4 nv-fade-in space-y-2" style={{ borderTop: "1px solid var(--nv-border)", paddingTop: 12 }}>
      <p className="font-semibold" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
        {a.matchesTitle.replace("{home}", String(match.ht_home)).replace("{away}", String(match.ht_away))}
      </p>
      {failed && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-accent-red)" }}>{t.live.liveDataError}</p>}
      {!failed && sources === null && <div className="nv-skeleton" style={{ width: "70%", height: 12, borderRadius: 4 }} />}
      {sources?.map((src) => (
        <div key={src.archive}>
          <div className="flex items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
            <span className="font-bold" style={{ color: "var(--nv-text-secondary)" }}>{src.label}</span>
            <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-tertiary)" }}>({src.n})</span>
            {src.n === 0 && <span style={{ color: "var(--nv-text-tertiary)", fontStyle: "italic" }}>{a.noMatches}</span>}
          </div>
          {src.matches && src.matches.length > 0 && <ArchiveMatchList matches={src.matches} />}
        </div>
      ))}
    </div>
  );
}

function MatchCard({ match }: { match: LiveHTMatch }) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const { flag, short } = leagueDisplay(null, match.league_name);

  const isHT = match.live_minute === "HT" || match.phase === "ht";
  const isSecondHalf = !isHT;
  const minuteLabel = isHT ? t.live.halfTime : match.live_minute ? `${match.live_minute}'` : t.periodTabs.h2Short;
  const homeName = match.home_team || "?";
  const awayName = match.away_team || "?";
  const hasLiveScore = match.live_home != null && match.live_away != null;
  const liveChanged = hasLiveScore && (match.live_home !== match.ht_home || match.live_away !== match.ht_away);

  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", overflow: "hidden" }}>
      <div className="flex items-center gap-2 px-3 py-1.5 sm:px-4" style={{ backgroundColor: "var(--nv-bg-elevated)", borderBottom: "1px solid var(--nv-border-subtle)" }}>
        <span className="flex items-center gap-1 flex-shrink-0" title={match.league_name ?? ""}>
          <span className="text-sm leading-none" aria-hidden="true">{flag}</span>
          <span className="font-semibold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{short}</span>
        </span>
        {match.kickoff_time && (
          <span className="flex-shrink-0" style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
            {formatTime(match.kickoff_time)}
          </span>
        )}
        <div className="flex-1" />
        <span className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold" style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-live-dim)", color: "var(--nv-live)" }}>
          <span className="nv-live-pulse" style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "var(--nv-live)" }} />
          {minuteLabel}
        </span>
      </div>

      <div className="px-3 py-3 sm:px-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <span className="font-bold truncate block" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", lineHeight: 1.4 }}>{homeName}</span>
            <span className="font-bold truncate block" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", lineHeight: 1.4 }}>{awayName}</span>
          </div>
          <div className="flex-shrink-0 flex items-center gap-2">
            <ScoreBox value={`${match.ht_home} - ${match.ht_away}`} caption={t.live.ht} tone="accent" compact={isSecondHalf} />
            {isSecondHalf && hasLiveScore && (
              <ScoreBox value={`${match.live_home} - ${match.live_away}`} caption={t.live.current} tone={liveChanged ? "live" : "plain"} />
            )}
          </div>
        </div>

        {(match.frozen || match.archive_view) && (
        <div className="flex justify-end">
          <span
            className="px-2 py-0.5 font-semibold"
            style={{
              fontSize: "var(--nv-text-2xs)",
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: match.frozen ? "var(--nv-accent-green-dim)" : "var(--nv-bg-elevated)",
              color: match.frozen ? "var(--nv-accent-green)" : "var(--nv-text-tertiary)",
            }}
            title={t.live.archive.frozenTooltip}
          >
            {match.frozen ? t.live.archive.frozen : t.live.archive.notFrozen}
            {match.frozen && match.frozen_at ? ` ${formatTime(match.frozen_at)}` : ""}
          </span>
        </div>
        )}
        {match.archive_view ? (
          <>
            <HighlightList view={match.archive_view} />
            <ArchiveTable view={match.archive_view} />
          </>
        ) : (
          <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.live.archive.noAnalysis}</p>
        )}

        <div className="flex items-center gap-2">
          {match.archive_view && (
          <button
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 font-semibold transition-colors"
            style={{
              fontSize: "var(--nv-text-xs)",
              backgroundColor: expanded ? "var(--nv-accent-green-dim)" : "var(--nv-bg-elevated)",
              color: expanded ? "var(--nv-accent-green)" : "var(--nv-text-secondary)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            {expanded ? t.common.hide : t.live.htArchiveAnalysis}
          </button>
          )}
          <Link
            href={`/analyze/${match.match_id}?home=${encodeURIComponent(homeName)}&away=${encodeURIComponent(awayName)}`}
            prefetch={false}
            className="flex items-center justify-center gap-1.5 px-4 py-2 font-semibold transition-colors"
            style={{ fontSize: "var(--nv-text-xs)", backgroundColor: "var(--nv-accent-blue-dim)", color: "var(--nv-accent-blue)", borderRadius: "var(--nv-radius-md)" }}
          >
            {t.common.detailedAnalysis}
          </Link>
        </div>
      </div>

      {expanded && match.archive_view && <ArchiveDetails match={match} />}
    </div>
  );
}

function ScoreBox({ value, caption, tone, compact }: { value: string; caption: string; tone: "accent" | "live" | "plain"; compact?: boolean }) {
  const colors = {
    accent: { fg: "var(--nv-text-on-accent)", bg: "var(--nv-accent-blue)" },
    live: { fg: "var(--nv-text-on-accent)", bg: "var(--nv-live)" },
    plain: { fg: "var(--nv-text-primary)", bg: "var(--nv-bg-elevated)" },
  }[tone];
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className="font-bold text-center"
        style={{
          fontFamily: "var(--nv-font-mono)",
          fontSize: compact ? "var(--nv-text-lg)" : "var(--nv-text-2xl)",
          lineHeight: 1,
          color: colors.fg,
          backgroundColor: colors.bg,
          borderRadius: "var(--nv-radius-md)",
          padding: compact ? "4px 10px" : "6px 14px",
          minWidth: compact ? 52 : 72,
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        {caption}
      </span>
    </div>
  );
}

function ConnectionBadge({ status }: { status: WsStatus }) {
  const { t } = useLocale();
  if (status === "connected") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5" style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-accent-green-dim)", color: "var(--nv-accent-green)" }} title={t.live.wsTooltip}>
        <span style={{ width: 5, height: 5, borderRadius: "50%", backgroundColor: "currentColor" }} />
        WS
      </span>
    );
  }
  if (status === "fallback") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5" style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }} title={t.live.restTooltip}>
        REST
      </span>
    );
  }
  return null;
}

interface Snapshot {
  matches: LiveHTMatch[];
  at: Date;
}

export default function CanliPage() {
  const { t, locale } = useLocale();
  const ws = useLiveWs();
  const usingWs = ws.status === "connected" && ws.lastUpdate !== null;
  const [rest, setRest] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");

  const fetchMatches = useCallback(async () => {
    try {
      const data = await getLiveHTMatches();
      setRest({ matches: data, at: new Date() });
      setError("");
    } catch {
      setError(t.live.liveDataError);
    }
  }, [t]);

  // WS bağlı değilken REST ile yükle: bağlantı kurulurken kısa bekleme, fallback'te hemen.
  useEffect(() => {
    if (usingWs) return;
    const start = window.setTimeout(fetchMatches, ws.status === "fallback" ? 0 : WS_GRACE_MS);
    const timer = window.setInterval(fetchMatches, POLL_INTERVAL);
    return () => {
      window.clearTimeout(start);
      window.clearInterval(timer);
    };
  }, [usingWs, ws.status, fetchMatches]);

  const source: Snapshot | null = usingWs && ws.lastUpdate ? { matches: ws.matches, at: ws.lastUpdate } : rest;
  const matches = useMemo(
    () => [...(source?.matches ?? [])].sort((a, b) => minuteOrder(a) - minuteOrder(b)),
    [source?.matches],
  );
  const loading = source === null && !error;
  const showError = source === null && !!error;
  const timeLocale = locale === "en" ? "en-GB" : "tr-TR";

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-tight)" }}>
              {t.live.title}
            </h1>
            {matches.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold" style={{ fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-live-dim)", color: "var(--nv-live)" }}>
                <span className="nv-live-pulse" style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "var(--nv-live)" }} />
                {matches.length} {t.common.match}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ConnectionBadge status={ws.status} />
            {source && (
              <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", fontFamily: "var(--nv-font-mono)" }}>
                {source.at.toLocaleTimeString(timeLocale, { timeZone: "Europe/Istanbul", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
          </div>
        </div>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
          {t.live.htDescription}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }} aria-busy="true">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="nv-card p-3" style={{ borderRadius: "var(--nv-radius-lg)" }}>
                <div className="nv-skeleton" style={{ width: "60%", height: 14, borderRadius: 4 }} />
                <div className="nv-skeleton mt-2" style={{ width: "40%", height: 14, borderRadius: 4 }} />
              </div>
            ))}
          </div>
        )}

        {showError && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full" style={{ borderRadius: "var(--nv-radius-lg)" }}>
              <p className="font-medium" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{error}</p>
              <button
                onClick={() => { setError(""); fetchMatches(); }}
                className="px-4 py-2 font-semibold transition-colors"
                style={{ fontSize: "var(--nv-text-sm)", backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}
              >
                {t.common.retry}
              </button>
            </div>
          </div>
        )}

        {source && matches.length === 0 && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full" style={{ borderRadius: "var(--nv-radius-lg)" }}>
              <p className="font-medium" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}>{t.live.noLiveMatches}</p>
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.live.noLiveNote}</p>
              <Link href="/bulten" className="inline-block font-medium transition-colors" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}>
                {t.live.viewBulletin}
              </Link>
            </div>
          </div>
        )}

        {matches.length > 0 && (
          <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
            {matches.map((match) => <MatchCard key={match.match_id} match={match} />)}
          </div>
        )}
      </div>
    </div>
  );
}
