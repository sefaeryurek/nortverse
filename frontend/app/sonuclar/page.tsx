import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import { getResults } from "@/lib/api";
import { leagueDisplay } from "@/lib/leagues";
import type { ResultMatch } from "@/lib/types";
import Link from "next/link";

function ResultSkeleton() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-4 py-3 border-b animate-pulse"
          style={{ borderColor: "#1e293b" }}
        >
          <div className="w-12 h-3 rounded" style={{ backgroundColor: "#1e293b" }} />
          <div className="w-20 h-3 rounded" style={{ backgroundColor: "#1e293b" }} />
          <div className="flex-1 flex items-center gap-2">
            <div className="h-3.5 flex-1 rounded" style={{ backgroundColor: "#1e293b" }} />
            <div className="h-3 w-6 rounded" style={{ backgroundColor: "#1e293b" }} />
            <div className="h-3.5 flex-1 rounded" style={{ backgroundColor: "#1e293b" }} />
          </div>
          <div className="w-16 h-6 rounded" style={{ backgroundColor: "#1e293b" }} />
          <div className="w-12 h-6 rounded" style={{ backgroundColor: "#1e293b" }} />
        </div>
      ))}
    </>
  );
}

interface Props {
  searchParams: Promise<{ date?: string }>;
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

function ResultRow({ match }: { match: ResultMatch }) {
  const timeStr = formatTime(match.kickoff_time);
  const htStr =
    match.actual_ht_home != null && match.actual_ht_away != null
      ? `IY ${match.actual_ht_home}-${match.actual_ht_away}`
      : null;
  const scoreStr =
    match.actual_ft_home != null && match.actual_ft_away != null
      ? `${match.actual_ft_home} - ${match.actual_ft_away}`
      : null;

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b hover:bg-slate-900/40 transition-colors"
      style={{ borderColor: "#1e293b" }}
    >
      {/* Saat */}
      <span
        className="w-12 text-xs font-mono flex-shrink-0 text-right"
        style={{ color: "#64748b" }}
      >
        {timeStr}
      </span>

      {/* Lig */}
      {(() => {
        const { flag, short } = leagueDisplay(match.league_code, match.league_name);
        return (
          <span
            className="w-24 text-xs font-semibold truncate flex-shrink-0 flex items-center gap-1"
            style={{ color: "#475569" }}
            title={match.league_name ?? match.league_code ?? ""}
          >
            <span className="text-base leading-none" aria-hidden>{flag}</span>
            <span>{short}</span>
          </span>
        );
      })()}

      {/* Takımlar */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate" style={{ color: "#e2e8f0" }}>
            {match.home_team}
          </span>
          <span className="text-xs flex-shrink-0" style={{ color: "#475569" }}>vs</span>
          <span className="text-sm font-medium truncate" style={{ color: "#e2e8f0" }}>
            {match.away_team}
          </span>
        </div>
        {htStr && (
          <span className="text-[10px] font-mono" style={{ color: "#475569" }}>
            {htStr}
          </span>
        )}
      </div>

      {/* Status'e göre: Canlı veya Skor */}
      <div className="flex-shrink-0 flex flex-col items-end gap-0.5">
        {match.status === "live" ? (
          <span
            className="px-2 py-0.5 rounded text-xs font-bold animate-pulse"
            style={{ backgroundColor: "#14532d", color: "#4ade80" }}
          >
            {scoreStr ? `Canlı ${scoreStr}` : "Canlı"}
          </span>
        ) : (
          <span
            className="text-sm font-bold font-mono px-2 py-0.5 rounded"
            style={{ backgroundColor: "#0f172a", color: "#f1f5f9" }}
          >
            {scoreStr}
          </span>
        )}
      </div>

      {/* Analiz linki */}
      <Link
        href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
        className="flex-shrink-0 text-xs px-3 py-2 rounded transition-colors min-h-[40px] flex items-center justify-center"
        style={{ backgroundColor: "#1e293b", color: "#64748b" }}
      >
        Analiz
      </Link>
    </div>
  );
}

async function ResultList({ date }: { date: string }) {
  let matches: ResultMatch[] = [];
  let error = "";
  try {
    matches = await getResults(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center space-y-3">
          <div className="text-5xl">⚠️</div>
          <p className="text-sm font-medium" style={{ color: "#ef4444" }}>{error}</p>
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
    const isToday = date === today;
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center space-y-3 max-w-md px-6">
          <div className="text-5xl">📭</div>
          <p className="text-sm font-medium" style={{ color: "#64748b" }}>
            {isToday
              ? "Henüz oynanan veya canlı maç yok."
              : "Bu tarihe ait maç bulunamadı."}
          </p>
          {isToday && (
            <p className="text-xs" style={{ color: "#475569" }}>
              Maçlar başladıkça canlı, bittikçe skor olarak burada görünür.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Özet */}
      <div
        className="flex items-center gap-4 px-4 py-2 text-xs border-b"
        style={{ borderColor: "#1e293b", color: "#475569" }}
      >
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "#22c55e" }} />
          {matches.length} maç
        </span>
        <span style={{ color: "#4ade80" }}>
          Canlı: {matches.filter((m) => m.status === "live").length}
        </span>
        <span>Bitti: {matches.filter((m) => m.status === "finished").length}</span>
        <span>KG: {matches.filter((m) => m.kg_var === true).length}</span>
        <span>2.5 Üst: {matches.filter((m) => m.over_25 === true).length}</span>
      </div>

      {matches.map((m) => (
        <ResultRow key={m.match_id} match={m} />
      ))}
    </>
  );
}

export default async function SonuclarPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", {
    timeZone: "Europe/Istanbul",
  });
  const date = params.date ?? today;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b" style={{ borderColor: "#2d3748" }}>
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
            Sonuçlar
          </h1>
          <span
            className="text-xs font-mono px-2.5 py-1 rounded-full"
            style={{ backgroundColor: "#1e293b", color: "#64748b" }}
          >
            {date}
          </span>
        </div>
      </div>

      {/* Gün sekmeleri */}
      <DayTabs activeDate={date} basePath="/sonuclar" />

      {/* Sonuç listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<ResultSkeleton />}>
          <ResultList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
