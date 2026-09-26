import { memo } from "react";
import Link from "next/link";
import type { FixtureMatch } from "@/lib/types";
import { leagueDisplay } from "@/lib/leagues";
import { isLiveScoreStale } from "@/lib/score-freshness";
import LiveMatchBadge from "./LiveMatchBadge";

interface Props {
  match: FixtureMatch;
  timeStr: string;
  patternStatus?: { has_b: boolean; has_c: boolean };
}

export default memo(function BultenRow({ match, timeStr, patternStatus }: Props) {
  const { flag } = leagueDisplay(match.league_code, match.league_name);
  const leagueName = match.league_name || match.league_code;
  const checkedLabel = match.score_checked_at
    ? new Date(match.score_checked_at).toLocaleString("tr-TR", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul",
    }) : null;

  const isLive = match.status === "live" && match.live_home !== null && match.live_away !== null;

  return (
    <Link
      href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
      prefetch={false}
      aria-label={`${match.home_team} - ${match.away_team}, ${timeStr}`}
      className="nv-card-interactive group block"
      style={{
        padding: 0,
        marginBottom: "var(--nv-space-sm)",
        minHeight: 44,
      }}
    >
      <div className="flex items-center gap-3 px-3 py-3 sm:px-4">
        {/* Saat */}
        <div
          className="flex-shrink-0 flex items-center justify-center"
          style={{
            width: 52,
            height: 36,
            borderRadius: "var(--nv-radius-sm)",
            backgroundColor: "var(--nv-bg-elevated)",
          }}
        >
          <span
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-sm)",
              fontWeight: 700,
              color: timeStr === "--:--"
                ? "var(--nv-text-tertiary)"
                : "var(--nv-accent-blue)",
            }}
          >
            {timeStr}
          </span>
        </div>

        {/* Lig + Takimlar */}
        <div className="min-w-0 flex-1 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
          {/* Lig */}
          <div
            className="flex items-center gap-1.5 flex-shrink-0"
            style={{ minWidth: 0 }}
          >
            <span className="text-lg leading-none flex-shrink-0">{flag}</span>
            <span
              className="truncate"
              style={{
                fontSize: "var(--nv-text-xs)",
                fontWeight: 500,
                color: "var(--nv-text-tertiary)",
                maxWidth: 120,
              }}
            >
              {leagueName}
            </span>
          </div>

          {/* Takimlar */}
          <div className="min-w-0 flex-1">
            <div className="flex flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:gap-2">
              <span
                className="max-w-full break-words sm:truncate"
                style={{
                  fontSize: "var(--nv-text-sm)",
                  fontWeight: 600,
                  color: "var(--nv-text-primary)",
                }}
              >
                {match.home_team}
              </span>
              <span
                className="hidden sm:inline flex-shrink-0"
                style={{
                  fontSize: "var(--nv-text-xs)",
                  fontWeight: 700,
                  color: "var(--nv-text-tertiary)",
                  padding: "1px 6px",
                  borderRadius: "var(--nv-radius-sm)",
                  backgroundColor: "var(--nv-bg-elevated)",
                }}
              >
                vs
              </span>
              <span
                className="max-w-full break-words sm:truncate"
                style={{
                  fontSize: "var(--nv-text-sm)",
                  fontWeight: 600,
                  color: "var(--nv-text-primary)",
                }}
              >
                {match.away_team}
              </span>
            </div>
          </div>
        </div>

        {/* Canli skor */}
        {isLive && (
          <LiveMatchBadge
            home={match.live_home!}
            away={match.live_away!}
            minute={match.live_minute}
            checkedAt={match.score_checked_at}
            checkedLabel={checkedLabel}
            initialStale={isLiveScoreStale(match.score_checked_at)}
          />
        )}

        {/* Arsiv eslesmesi gostergesi */}
        {patternStatus && (
          <div className="flex items-center gap-1 flex-shrink-0">
            {patternStatus.has_b && (
              <span
                title="Arşiv 1 eşleşmesi var"
                style={{
                  fontSize: "var(--nv-text-xs)",
                  fontWeight: 700,
                  lineHeight: 1,
                  padding: "2px 6px",
                  borderRadius: "var(--nv-radius-sm)",
                  backgroundColor: "var(--nv-accent-blue-dim)",
                  color: "var(--nv-accent-blue)",
                }}
              >
                A1
              </span>
            )}
            {patternStatus.has_c && (
              <span
                title="Arşiv 2 eşleşmesi var"
                style={{
                  fontSize: "var(--nv-text-xs)",
                  fontWeight: 700,
                  lineHeight: 1,
                  padding: "2px 6px",
                  borderRadius: "var(--nv-radius-sm)",
                  backgroundColor: "var(--nv-accent-green-dim)",
                  color: "var(--nv-accent-green)",
                }}
              >
                A2
              </span>
            )}
          </div>
        )}

        {/* Chevron ok */}
        <div
          className="flex-shrink-0 flex items-center justify-center"
          style={{
            width: 28,
            height: 28,
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: "var(--nv-bg-elevated)",
            transition: `background-color var(--nv-duration-normal) var(--nv-ease)`,
          }}
        >
          <svg
            width={14}
            height={14}
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
            viewBox="0 0 24 24"
            aria-hidden="true"
            style={{
              color: "var(--nv-text-tertiary)",
              transition: `color var(--nv-duration-normal) var(--nv-ease)`,
            }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </Link>
  );
});
