import Link from "next/link";
import type { FixtureMatch } from "@/lib/types";
import { leagueDisplay } from "@/lib/leagues";

interface Props {
  match: FixtureMatch;
  timeStr: string;
}

export default function BultenRow({ match, timeStr }: Props) {
  const { flag } = leagueDisplay(match.league_code, match.league_name);
  const leagueName = match.league_name || match.league_code;
  const liveLabel = match.live_minute === "HT" ? "İY" : match.live_minute ? `${match.live_minute}′` : "CANLI";

  return (
    <Link
      href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
      prefetch={false}
      className="group flex items-center gap-0 border-b transition-all"
      style={{ borderColor: "#1e293b" }}
    >
      {/* Saat */}
      <div
        className="flex-shrink-0 w-16 flex items-center justify-center py-4 self-stretch"
        style={{ backgroundColor: match.status === "live" ? "#052e20" : "#0f172a" }}
      >
        <span
          className="text-sm font-mono font-bold"
          style={{ color: match.status === "live" ? "#4ade80" : timeStr === "--:--" ? "#475569" : "#60a5fa" }}
        >
          {match.status === "live" ? liveLabel : timeStr}
        </span>
      </div>

      {/* İçerik */}
      <div
        className="min-w-0 flex-1 flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 transition-colors group-hover:bg-white/5"
      >
        {/* Lig */}
        <div className="flex-shrink-0 flex items-center gap-1.5 w-full sm:w-32">
          <span className="text-lg leading-none">{flag}</span>
          <span className="text-xs font-medium leading-tight" style={{ color: "#64748b" }}>
            {leagueName}
          </span>
        </div>

        {/* Takımlar */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-2">
            <span className="max-w-full break-words text-sm font-semibold sm:truncate" style={{ color: "#e2e8f0" }}>
              {match.home_team}
            </span>
            <span
              className="hidden sm:inline flex-shrink-0 text-[11px] font-bold px-1.5 py-0.5 rounded"
              style={{ color: "#475569", backgroundColor: "#1e293b" }}
            >
              vs
            </span>
            <span className="max-w-full break-words text-sm font-semibold sm:truncate" style={{ color: "#e2e8f0" }}>
              {match.away_team}
            </span>
          </div>
        </div>

        {match.status === "live" && match.live_home !== null && match.live_away !== null && (
          <span className="flex-shrink-0 rounded bg-green-950 px-2 py-1 text-sm font-bold font-mono text-green-300">
            {match.live_home} - {match.live_away}
          </span>
        )}
        {match.status === "pending" && (
          <span className="flex-shrink-0 rounded bg-amber-950 px-2 py-1 text-xs text-amber-300">
            Durum doğrulanıyor
          </span>
        )}

        {/* Ok */}
        <div
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-colors group-hover:bg-blue-600"
          style={{ backgroundColor: "#1e293b" }}
        >
          <svg
            className="w-3.5 h-3.5 transition-colors group-hover:text-white"
            style={{ color: "#475569" }}
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </Link>
  );
}
