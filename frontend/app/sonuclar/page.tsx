import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import { getResults } from "@/lib/api";
import type { ResultMatch } from "@/lib/types";
import Link from "next/link";

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

function ResultBadge({
  hit,
  label,
}: {
  hit: boolean;
  label: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold"
      style={{
        backgroundColor: hit ? "#14532d" : "#2d1010",
        color: hit ? "#4ade80" : "#f87171",
        border: `1px solid ${hit ? "#166534" : "#7f1d1d"}`,
      }}
    >
      {hit ? "✓" : "✗"} {label}
    </span>
  );
}

function ResultRow({ match }: { match: ResultMatch }) {
  const timeStr = formatTime(match.kickoff_time);
  const scoreStr = `${match.actual_ft_home} - ${match.actual_ft_away}`;
  const htStr =
    match.actual_ht_home != null && match.actual_ht_away != null
      ? `${match.actual_ht_home}-${match.actual_ht_away}`
      : null;

  const resultLabel =
    match.result === "1" ? "Ev" : match.result === "2" ? "Dep" : "X";
  const resultColor =
    match.result === "1"
      ? "#3b82f6"
      : match.result === "2"
        ? "#f97316"
        : "#94a3b8";

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b hover:bg-opacity-50 transition-colors"
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
      <span
        className="w-20 text-xs font-semibold truncate flex-shrink-0"
        style={{ color: "#475569" }}
        title={match.league_name ?? match.league_code ?? ""}
      >
        {match.league_code ?? "—"}
      </span>

      {/* Maç */}
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <span
          className="text-sm font-medium truncate"
          style={{ color: "#e2e8f0" }}
        >
          {match.home_team}
        </span>

        {/* Skor kutusu */}
        <div className="flex-shrink-0 flex flex-col items-center">
          <span
            className="text-base font-bold font-mono px-3 py-1 rounded"
            style={{ backgroundColor: "#0f172a", color: "#f1f5f9" }}
          >
            {scoreStr}
          </span>
          {htStr && (
            <span className="text-[10px] font-mono mt-0.5" style={{ color: "#475569" }}>
              IY: {htStr}
            </span>
          )}
        </div>

        <span
          className="text-sm font-medium truncate"
          style={{ color: "#e2e8f0" }}
        >
          {match.away_team}
        </span>
      </div>

      {/* Sonuç rozetleri */}
      <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap justify-end">
        <span
          className="px-2 py-0.5 rounded text-xs font-bold"
          style={{ backgroundColor: "#1e293b", color: resultColor }}
        >
          {resultLabel}
        </span>
        <ResultBadge hit={match.kg_var} label="KG" />
        <ResultBadge hit={match.over_25} label="2.5 Üst" />
        <ResultBadge hit={match.katman_a_covered} label="A✓" />
      </div>

      {/* Analiz linki */}
      <Link
        href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
        className="flex-shrink-0 text-xs px-2 py-1 rounded transition-colors"
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
          <p className="text-sm font-medium" style={{ color: "#ef4444" }}>
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center space-y-3">
          <div className="text-5xl">📭</div>
          <p className="text-sm font-medium" style={{ color: "#64748b" }}>
            Bu tarihe ait tamamlanmış maç bulunamadı.
          </p>
        </div>
      </div>
    );
  }

  const covered = matches.filter((m) => m.katman_a_covered).length;
  const covPct =
    matches.length > 0 ? Math.round((covered / matches.length) * 100) : 0;

  return (
    <>
      {/* Özet satırı */}
      <div
        className="flex items-center gap-4 px-4 py-2 text-xs border-b"
        style={{ borderColor: "#1e293b", color: "#475569" }}
      >
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "#22c55e" }} />
          {matches.length} maç tamamlandı
        </span>
        <span>KG: {matches.filter((m) => m.kg_var).length}</span>
        <span>2.5 Üst: {matches.filter((m) => m.over_25).length}</span>
        <span style={{ color: covPct >= 60 ? "#22c55e" : covPct >= 40 ? "#f97316" : "#ef4444" }}>
          Katman A isabeti: %{covPct}
        </span>
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
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-24">
              <p className="text-sm animate-pulse" style={{ color: "#64748b" }}>
                Yükleniyor...
              </p>
            </div>
          }
        >
          <ResultList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
