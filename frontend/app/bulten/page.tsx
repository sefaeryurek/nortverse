import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import BultenRow from "@/components/BultenRow";
import { getFixture } from "@/lib/api";
import type { FixtureMatch } from "@/lib/types";

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
    matches = await getFixture(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center space-y-3">
          <div className="text-5xl">⚠️</div>
          <p className="text-sm font-medium" style={{ color: "#ef4444" }}>{error}</p>
          <p className="text-xs" style={{ color: "#475569" }}>
            Backend sunucusunun çalıştığından emin olun
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
            Bu tarihte maç bulunamadı.
          </p>
        </div>
      </div>
    );
  }

  const sorted = sortMatches(matches);

  return (
    <>
      <div
        className="flex items-center gap-2 px-4 py-2 text-xs border-b"
        style={{ borderColor: "#1e293b", color: "#475569" }}
      >
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: "#22c55e" }}
        />
        {matches.length} maç
      </div>
      {sorted.map(({ match, timeStr }) => (
        <BultenRow key={match.match_id} match={match} timeStr={timeStr} />
      ))}
    </>
  );
}

export default async function BultenPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const date = params.date ?? today;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-6 py-4 border-b"
        style={{ borderColor: "#2d3748" }}
      >
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
            Günlük Bülten
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
      <DayTabs activeDate={date} />

      {/* Maç listesi */}
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
          <MatchList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
