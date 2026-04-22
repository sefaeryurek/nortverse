"use client";

import { useRouter } from "next/navigation";
import type { FixtureMatch } from "@/lib/types";

interface Props {
  match: FixtureMatch;
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
};

function formatTime(iso: string | null): string {
  if (!iso) return "--:--";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--:--";
  }
}

export default function BultenRow({ match }: Props) {
  const router = useRouter();
  const flag = LEAGUE_FLAGS[match.league_code] ?? "⚽";

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b transition-colors hover:bg-white/5 cursor-default"
      style={{ borderColor: "#2d3748" }}
    >
      {/* Lig */}
      <div className="w-24 flex-shrink-0 flex items-center gap-1.5">
        <span className="text-base">{flag}</span>
        <span className="text-xs truncate" style={{ color: "#64748b" }}>
          {match.league_code}
        </span>
      </div>

      {/* Takımlar */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold truncate" style={{ color: "#e2e8f0" }}>
            {match.home_team}
          </span>
          <span className="text-xs font-bold" style={{ color: "#475569" }}>
            vs
          </span>
          <span className="text-sm font-semibold truncate" style={{ color: "#e2e8f0" }}>
            {match.away_team}
          </span>
        </div>
        {match.league_name && (
          <p className="text-xs mt-0.5 truncate" style={{ color: "#475569" }}>
            {match.league_name}
          </p>
        )}
      </div>

      {/* Saat */}
      <div
        className="text-sm font-mono font-semibold w-14 text-center flex-shrink-0"
        style={{ color: "#93c5fd" }}
      >
        {formatTime(match.kickoff_time)}
      </div>

      {/* Buton */}
      <button
        onClick={() => router.push(`/analyze/${match.match_id}`)}
        className="flex-shrink-0 px-3 py-1.5 rounded text-xs font-semibold transition-colors"
        style={{ backgroundColor: "#1e3a5f", color: "#93c5fd" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "#1d4ed8";
          e.currentTarget.style.color = "#fff";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "#1e3a5f";
          e.currentTarget.style.color = "#93c5fd";
        }}
      >
        Tahmin Et
      </button>
    </div>
  );
}
