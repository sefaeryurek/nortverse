import { getFixture } from "@/lib/api";
import Link from "next/link";
import DayTabs from "@/components/DayTabs";

interface Props {
  searchParams: Promise<{ date?: string }>;
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
    return new Date(iso).toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "--:--";
  }
}

export default async function Tahmin2Page({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toISOString().split("T")[0];
  const date = params.date ?? today;

  let matches = [];
  let error = "";
  try {
    matches = await getFixture(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b" style={{ borderColor: "#2d3748" }}>
        <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
          Tahmin — Arşiv 2
        </h1>
        <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>
          Katman C · 35 skor oran benzerliği (±0.5) · Gerçek sonuçtan tahmin
        </p>
      </div>

      <DayTabs activeDate={date} />

      <div className="flex-1 overflow-y-auto">
        {error ? (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm" style={{ color: "#ef4444" }}>{error}</p>
          </div>
        ) : matches.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm" style={{ color: "#64748b" }}>Bu tarihte maç bulunamadı.</p>
          </div>
        ) : (
          <div>
            {matches.map((m) => {
              const flag = LEAGUE_FLAGS[m.league_code] ?? "⚽";
              return (
                <Link
                  key={m.match_id}
                  href={`/analyze/${m.match_id}`}
                  className="flex items-center gap-3 px-4 py-3 border-b transition-colors hover:bg-white/5"
                  style={{ borderColor: "#2d3748" }}
                >
                  <span className="text-base flex-shrink-0">{flag}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold truncate" style={{ color: "#e2e8f0" }}>
                        {m.home_team}
                      </span>
                      <span className="text-xs font-bold flex-shrink-0" style={{ color: "#475569" }}>vs</span>
                      <span className="text-sm font-semibold truncate" style={{ color: "#e2e8f0" }}>
                        {m.away_team}
                      </span>
                    </div>
                    <p className="text-xs mt-0.5 truncate" style={{ color: "#475569" }}>
                      {m.league_code}{m.league_name ? ` · ${m.league_name}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-sm font-mono font-semibold" style={{ color: "#93c5fd" }}>
                      {formatTime(m.kickoff_time)}
                    </span>
                    <span
                      className="text-xs px-2.5 py-1 rounded-lg font-semibold"
                      style={{ backgroundColor: "#1c1035", color: "#c084fc", border: "1px solid #7e22ce" }}
                    >
                      Tahmin →
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
