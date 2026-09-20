import { redirect } from "next/navigation";
import { resolvePageDate } from "@/lib/dates";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import AutoRefresh from "@/components/AutoRefresh";
import RetryButton from "@/components/RetryButton";
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
  searchParams: Promise<{ date?: string | string[]; q?: string | string[] }>;
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
      className="flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 border-b hover:bg-slate-900/40 transition-colors"
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
      <div className="w-full min-w-0 sm:w-auto sm:flex-1">
        <div className="flex flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-2">
          <span className="max-w-full break-words text-sm font-medium sm:truncate" style={{ color: "#e2e8f0" }}>
            {match.home_team}
          </span>
          <span className="hidden sm:inline text-xs flex-shrink-0" style={{ color: "#475569" }}>vs</span>
          <span className="max-w-full break-words text-sm font-medium sm:truncate" style={{ color: "#e2e8f0" }}>
            {match.away_team}
          </span>
        </div>
        {htStr && (
          <span className="text-[10px] font-mono" style={{ color: "#475569" }}>
            {htStr}
          </span>
        )}
      </div>

      {/* Kesin maç sonu skoru */}
      <div className="flex-shrink-0 flex flex-col items-end gap-0.5">
        <span
          className="text-sm font-bold font-mono px-2 py-0.5 rounded"
          style={{ backgroundColor: "#0f172a", color: "#f1f5f9" }}
        >
          {scoreStr}
        </span>
      </div>

      {/* Analiz linki */}
      <Link
        href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
        prefetch={false}
        className="flex-shrink-0 text-xs px-3 py-2 rounded transition-colors min-h-[40px] flex items-center justify-center"
        style={{ backgroundColor: "#1e293b", color: "#64748b" }}
      >
        Analiz
      </Link>
    </div>
  );
}

async function ResultList({ date, q }: { date: string; q: string }) {
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
          <RetryButton />
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
              ? "Bugün henüz kesinleşmiş maç sonucu yok."
              : "Bu tarihte kesinleşmiş maç sonucu bulunamadı."}
          </p>
          {isToday && (
            <p className="text-xs" style={{ color: "#475569" }}>
              Başlayacak ve süren maçlar Bülten sayfasında görünür.
            </p>
          )}
          <Link href={`/bulten?date=${date}`} className="mt-3 inline-block text-sm text-blue-400 hover:text-blue-300">
            Bültendeki maçlara bak
          </Link>
        </div>
      </div>
    );
  }

  const normalized = q.toLocaleLowerCase("tr-TR");
  const visible = matches.filter((match) =>
    !normalized || [match.home_team, match.away_team, match.league_name ?? match.league_code ?? ""]
      .some((value) => value.toLocaleLowerCase("tr-TR").includes(normalized)))
  const lastChecked = matches.reduce<string | null>((latest, match) =>
    match.score_checked_at && (!latest || match.score_checked_at > latest)
      ? match.score_checked_at : latest, null);

  return (
    <>
      {/* Özet */}
      <div
        className="flex flex-wrap items-center gap-3 px-4 py-2 text-xs border-b"
        style={{ borderColor: "#1e293b", color: "#475569" }}
      >
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: "#22c55e" }} />
          {matches.length} biten maç
        </span>
      </div>
      <p className="border-b border-slate-800 px-4 py-2 text-xs text-slate-400">
        {lastChecked
          ? `Son skor kontrolü: ${new Date(lastChecked).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", dateStyle: "short", timeStyle: "short" })}`
          : "Yalnızca kesin maç sonu skorları gösterilir."}
      </p>

      <div className="space-y-3 border-b border-slate-800 px-4 py-3">
        <form action="/sonuclar" className="flex max-w-xl gap-2">
          <input type="hidden" name="date" value={date} />
          <input
            name="q"
            defaultValue={q}
            maxLength={80}
            aria-label="Takım veya lig ara"
            placeholder="Takım veya lig ara"
            className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
          />
          <button type="submit" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600">
            Ara
          </button>
        </form>
        {q && <p className="text-xs text-slate-400">{visible.length} eşleşen maç</p>}
      </div>

      {visible.length === 0 && (
        <p className="px-4 py-12 text-center text-sm text-slate-400">Bu filtreyle eşleşen maç bulunamadı.</p>
      )}
      {visible.map((m) => (
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
  const date = resolvePageDate(params.date, today);
  if (date === null) redirect("/sonuclar");
  const q = typeof params.q === "string" ? params.q.trim().slice(0, 80) : "";

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
      <DayTabs referenceDate={today} activeDate={date} basePath="/sonuclar" range="past" />
      {date === today && <AutoRefresh />}

      {/* Sonuç listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<ResultSkeleton />}>
          <ResultList date={date} q={q} />
        </Suspense>
      </div>
    </div>
  );
}
