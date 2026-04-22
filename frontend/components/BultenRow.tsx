import Link from "next/link";
import type { FixtureMatch } from "@/lib/types";

interface Props {
  match: FixtureMatch;
  timeStr: string;
}

const LEAGUE_FLAGS: Record<string, string> = {
  "ENG PR": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  "SPA D1": "🇪🇸",
  "ITA D1": "🇮🇹",
  "GER D1": "🇩🇪",
  "FRA D1": "🇫🇷",
  "POR D1": "🇵🇹",
  "HOL D1": "🇳🇱",
  "TUR D1": "🇹🇷",
  "BEL D1": "🇧🇪",
  "SCO PR": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  "GRE D1": "🇬🇷",
  "RUS D1": "🇷🇺",
  "USA MLS": "🇺🇸",
  "BRA D1": "🇧🇷",
  "ARG D1": "🇦🇷",
};

export default function BultenRow({ match, timeStr }: Props) {
  const flag = LEAGUE_FLAGS[match.league_code] ?? "⚽";
  const leagueName = match.league_name || match.league_code;

  return (
    <Link
      href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
      className="group flex items-center gap-0 border-b transition-all"
      style={{ borderColor: "#1e293b" }}
    >
      {/* Saat */}
      <div
        className="flex-shrink-0 w-16 flex items-center justify-center py-4 self-stretch"
        style={{ backgroundColor: "#0f172a" }}
      >
        <span
          className="text-sm font-mono font-bold"
          style={{ color: timeStr === "--:--" ? "#475569" : "#60a5fa" }}
        >
          {timeStr}
        </span>
      </div>

      {/* İçerik */}
      <div
        className="flex-1 flex items-center gap-3 px-4 py-3 transition-colors group-hover:bg-white/5"
      >
        {/* Lig */}
        <div className="flex-shrink-0 flex items-center gap-1.5 w-32">
          <span className="text-lg leading-none">{flag}</span>
          <span className="text-xs font-medium leading-tight" style={{ color: "#64748b" }}>
            {leagueName}
          </span>
        </div>

        {/* Takımlar */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
              {match.home_team}
            </span>
            <span
              className="flex-shrink-0 text-[11px] font-bold px-1.5 py-0.5 rounded"
              style={{ color: "#475569", backgroundColor: "#1e293b" }}
            >
              vs
            </span>
            <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
              {match.away_team}
            </span>
          </div>
        </div>

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
