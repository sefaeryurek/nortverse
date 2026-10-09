"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { ApiError, getLiveHTMatches, getMatchedMatches } from "@/lib/api";
import type { LiveHTMatch, MatchedMatch, MatchedMatchesResponse } from "@/lib/api";
import { leagueDisplay } from "@/lib/leagues";

const POLL_INTERVAL = 45_000;

function formatKickoff(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("tr-TR", {
      timeZone: "Europe/Istanbul",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

interface HTFilteredStats {
  archive: string;
  color: string;
  bgColor: string;
  matches: MatchedMatch[];
  ftScoreCounts: { score: string; count: number; pct: number }[];
  result1Pct: number;
  resultXPct: number;
  result2Pct: number;
  ust25Pct: number;
  kgVarPct: number;
}

function filterByHT(
  matches: MatchedMatch[],
  htHome: number,
  htAway: number,
): MatchedMatch[] {
  const htStr = `${htHome}-${htAway}`;
  return matches.filter((m) => m.ht === htStr);
}

function computeStats(
  matches: MatchedMatch[],
  archive: string,
  color: string,
  bgColor: string,
): HTFilteredStats | null {
  if (matches.length === 0) return null;

  let r1 = 0, rX = 0, r2 = 0, ust25 = 0, kgVar = 0;
  const scoreCounts: Record<string, number> = {};

  for (const m of matches) {
    if (!m.ft) continue;
    const parts = m.ft.split("-");
    if (parts.length !== 2) continue;
    const fh = parseInt(parts[0], 10);
    const fa = parseInt(parts[1], 10);
    if (isNaN(fh) || isNaN(fa)) continue;

    if (fh > fa) r1++;
    else if (fh === fa) rX++;
    else r2++;

    if (fh + fa > 2) ust25++;
    if (fh > 0 && fa > 0) kgVar++;

    scoreCounts[m.ft] = (scoreCounts[m.ft] || 0) + 1;
  }

  const total = r1 + rX + r2;
  if (total === 0) return null;

  const ftScoreCounts = Object.entries(scoreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([score, count]) => ({
      score,
      count,
      pct: Math.round((count / total) * 1000) / 10,
    }));

  return {
    archive,
    color,
    bgColor,
    matches,
    ftScoreCounts,
    result1Pct: Math.round((r1 / total) * 1000) / 10,
    resultXPct: Math.round((rX / total) * 1000) / 10,
    result2Pct: Math.round((r2 / total) * 1000) / 10,
    ust25Pct: Math.round((ust25 / total) * 1000) / 10,
    kgVarPct: Math.round((kgVar / total) * 1000) / 10,
  };
}

function PctBar({
  label,
  pct,
  color,
  highlight,
}: {
  label: string;
  pct: number;
  color: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="flex-shrink-0 font-semibold"
        style={{
          width: 28,
          fontSize: 11,
          color: highlight ? color : "var(--nv-text-secondary)",
          textAlign: "right",
        }}
      >
        {label}
      </span>
      <div
        className="flex-1"
        style={{
          height: 8,
          borderRadius: 4,
          backgroundColor: "var(--nv-bg-elevated)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            borderRadius: 4,
            backgroundColor: color,
            opacity: highlight ? 1 : 0.5,
            transition: "width 0.3s ease",
          }}
        />
      </div>
      <span
        className="flex-shrink-0 font-bold"
        style={{
          width: 46,
          fontFamily: "var(--nv-font-mono)",
          fontSize: 12,
          color: highlight ? color : "var(--nv-text-primary)",
          textAlign: "right",
        }}
      >
        %{pct.toFixed(1)}
      </span>
    </div>
  );
}

function ArchiveSection({ stats }: { stats: HTFilteredStats }) {
  const { result1Pct, resultXPct, result2Pct } = stats;
  const max = Math.max(result1Pct, resultXPct, result2Pct);

  return (
    <div
      className="p-3 space-y-3"
      style={{
        borderRadius: "var(--nv-radius-md)",
        border: `1px solid color-mix(in srgb, ${stats.color} 25%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${stats.color} 4%, transparent)`,
      }}
    >
      {/* Baslik */}
      <div className="flex items-center justify-between">
        <span
          className="inline-flex items-center gap-1.5 font-bold"
          style={{ fontSize: 12, color: stats.color }}
        >
          <span
            className="inline-flex items-center justify-center"
            style={{
              width: 20,
              height: 20,
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: stats.bgColor,
              fontSize: 9,
              fontWeight: 800,
            }}
          >
            {stats.archive}
          </span>
          Arşiv {stats.archive.replace("A", "")} — İY Eşleşen
        </span>
        <span
          className="font-semibold"
          style={{
            fontSize: 10,
            color: "var(--nv-text-tertiary)",
            fontFamily: "var(--nv-font-mono)",
          }}
        >
          {stats.matches.length} maç
        </span>
      </div>

      {/* MS Sonucu */}
      <div className="space-y-1">
        <PctBar label="1" pct={result1Pct} color="var(--nv-win)" highlight={result1Pct === max} />
        <PctBar label="X" pct={resultXPct} color="var(--nv-draw)" highlight={resultXPct === max} />
        <PctBar label="2" pct={result2Pct} color="var(--nv-loss)" highlight={result2Pct === max} />
      </div>

      {/* Ust/Alt + KG */}
      <div className="grid grid-cols-2 gap-2">
        <div
          className="py-1.5 px-2 text-center"
          style={{ borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-bg-elevated)" }}
        >
          <span className="block" style={{ fontSize: 9, color: "var(--nv-text-tertiary)", fontWeight: 600 }}>
            ÜST 2.5
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: 14,
              color:
                stats.ust25Pct >= 60 ? "var(--nv-accent-green)"
                  : stats.ust25Pct <= 40 ? "var(--nv-accent-red)"
                    : "var(--nv-text-primary)",
            }}
          >
            %{stats.ust25Pct.toFixed(0)}
          </span>
        </div>
        <div
          className="py-1.5 px-2 text-center"
          style={{ borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-bg-elevated)" }}
        >
          <span className="block" style={{ fontSize: 9, color: "var(--nv-text-tertiary)", fontWeight: 600 }}>
            KG VAR
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: 14,
              color:
                stats.kgVarPct >= 60 ? "var(--nv-accent-green)"
                  : stats.kgVarPct <= 40 ? "var(--nv-accent-red)"
                    : "var(--nv-text-primary)",
            }}
          >
            %{stats.kgVarPct.toFixed(0)}
          </span>
        </div>
      </div>

      {/* En sik skorlar */}
      {stats.ftScoreCounts.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {stats.ftScoreCounts.map((s, i) => (
            <span
              key={s.score}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 font-bold"
              style={{
                fontSize: 11,
                fontFamily: "var(--nv-font-mono)",
                borderRadius: "var(--nv-radius-sm)",
                backgroundColor: i === 0 ? stats.bgColor : "var(--nv-bg-elevated)",
                color: i === 0 ? stats.color : "var(--nv-text-secondary)",
              }}
            >
              {s.score}
              <span style={{ opacity: 0.6, fontSize: 9, fontWeight: 500 }}>
                %{s.pct.toFixed(0)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Eslesme detaylari (ilk 5) */}
      {stats.matches.length > 0 && (
        <div className="space-y-0.5 pt-1" style={{ borderTop: "1px solid var(--nv-border-subtle)" }}>
          {stats.matches.slice(0, 5).map((m) => (
            <div
              key={m.match_id}
              className="flex items-center gap-2 py-0.5"
              style={{ fontSize: 10, color: "var(--nv-text-tertiary)" }}
            >
              <span className="truncate flex-1 min-w-0">
                {m.home_team} - {m.away_team}
              </span>
              <span className="flex-shrink-0" style={{ color: "var(--nv-text-secondary)" }}>
                İY {m.ht}
              </span>
              <span
                className="flex-shrink-0 font-bold"
                style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}
              >
                MS {m.ft}
              </span>
            </div>
          ))}
          {stats.matches.length > 5 && (
            <span style={{ fontSize: 9, color: "var(--nv-text-tertiary)" }}>
              +{stats.matches.length - 5} maç daha
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function StatsPanel({
  matchId,
  htHome,
  htAway,
}: {
  matchId: string;
  htHome: number;
  htAway: number;
}) {
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [archiveStats, setArchiveStats] = useState<HTFilteredStats[]>([]);
  const [noData, setNoData] = useState(false);
  const fetchedRef = useRef(false);

  const doFetch = useCallback(async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const data: MatchedMatchesResponse = await getMatchedMatches(matchId);

      const results: HTFilteredStats[] = [];

      const bFiltered = filterByHT(data.archive_b || [], htHome, htAway);
      const bStats = computeStats(bFiltered, "A1", "var(--nv-accent-blue)", "var(--nv-accent-blue-dim)");
      if (bStats) results.push(bStats);

      const cFiltered = filterByHT(data.archive_c || [], htHome, htAway);
      const cStats = computeStats(cFiltered, "A2", "var(--nv-accent-green)", "var(--nv-accent-green-dim)");
      if (cStats) results.push(cStats);

      const dFiltered = filterByHT(data.archive_d || [], htHome, htAway);
      const dStats = computeStats(dFiltered, "A3", "var(--nv-accent-amber)", "color-mix(in srgb, var(--nv-accent-amber) 15%, transparent)");
      if (dStats) results.push(dStats);

      setArchiveStats(results);
      setNoData(results.length === 0);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setErrorMsg("Bu maç için analiz verisi bulunamadı. Yeterli istatistik olmayabilir.");
      } else {
        setErrorMsg("Arşiv verileri alınamadı.");
      }
    } finally {
      setLoading(false);
    }
  }, [matchId, htHome, htAway]);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    doFetch();
  }, [doFetch]);

  if (loading) {
    return (
      <div className="px-3 pb-3 sm:px-4 sm:pb-4" style={{ borderTop: "1px solid var(--nv-border)" }}>
        <div className="py-6 text-center space-y-2">
          <div className="nv-skeleton h-4 w-32 mx-auto" style={{ borderRadius: 4 }} />
          <div className="nv-skeleton h-4 w-24 mx-auto" style={{ borderRadius: 4 }} />
        </div>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="px-3 pb-3 sm:px-4 sm:pb-4 text-center py-4" style={{ borderTop: "1px solid var(--nv-border)" }}>
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
          {errorMsg}
        </p>
        <button
          onClick={() => { fetchedRef.current = false; doFetch(); }}
          className="mt-2 underline font-medium"
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-accent-blue)" }}
        >
          Tekrar dene
        </button>
      </div>
    );
  }

  if (noData) {
    return (
      <div className="px-3 pb-3 sm:px-4 sm:pb-4 text-center py-4" style={{ borderTop: "1px solid var(--nv-border)" }}>
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
          A1/A2/A3 eşleşen maçlarda İY {htHome}-{htAway} skoru bulunamadı.
        </p>
      </div>
    );
  }

  return (
    <div
      className="px-3 pb-3 sm:px-4 sm:pb-4 space-y-2 nv-fade-in"
      style={{ borderTop: "1px solid var(--nv-border)", paddingTop: 12 }}
    >
      <p className="font-semibold mb-2" style={{ fontSize: 10, color: "var(--nv-text-tertiary)", letterSpacing: "0.05em" }}>
        İY {htHome}-{htAway} ile biten eşleşen arşiv maçlarının MS sonuçları:
      </p>
      {archiveStats.map((s) => (
        <ArchiveSection key={s.archive} stats={s} />
      ))}
    </div>
  );
}

function MatchCard({ match }: { match: LiveHTMatch }) {
  const [expanded, setExpanded] = useState(false);

  const { flag, short } = leagueDisplay(null, match.league_name);
  const minuteLabel =
    match.live_minute === "HT"
      ? "Devre Arası"
      : match.live_minute
        ? `${match.live_minute}'`
        : "";

  const homeName = match.home_team || "Bilinmiyor";
  const awayName = match.away_team || "Bilinmiyor";

  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", overflow: "hidden" }}>
      {/* Ust bar: lig + dakika */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 sm:px-4"
        style={{ backgroundColor: "var(--nv-bg-elevated)", borderBottom: "1px solid var(--nv-border-subtle)" }}
      >
        <span className="flex items-center gap-1 flex-shrink-0" title={match.league_name ?? ""}>
          <span className="text-sm leading-none" aria-hidden="true">{flag}</span>
          <span className="font-semibold" style={{ fontSize: 11, color: "var(--nv-text-tertiary)" }}>{short}</span>
        </span>

        {match.kickoff_time && (
          <span className="flex-shrink-0" style={{ fontFamily: "var(--nv-font-mono)", fontSize: 11, color: "var(--nv-text-tertiary)" }}>
            {formatKickoff(match.kickoff_time)}
          </span>
        )}

        <div className="flex-1" />

        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold"
          style={{
            fontSize: 10,
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: "color-mix(in srgb, var(--nv-live) 15%, transparent)",
            color: "var(--nv-live)",
          }}
        >
          <span
            className="nv-live-pulse"
            style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "var(--nv-live)" }}
          />
          {minuteLabel}
        </span>
      </div>

      {/* Ana icerik: takimlar + skor */}
      <div className="px-3 py-3 sm:px-4">
        <div className="flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <div className="mb-1">
              <span className="font-bold truncate block" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", lineHeight: 1.3 }}>
                {homeName}
              </span>
            </div>
            <div>
              <span className="font-bold truncate block" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", lineHeight: 1.3 }}>
                {awayName}
              </span>
            </div>
          </div>

          <div className="flex-shrink-0 flex flex-col items-center gap-0.5">
            <span
              className="font-bold"
              style={{
                fontFamily: "var(--nv-font-mono)",
                fontSize: 28,
                lineHeight: 1,
                color: "var(--nv-text-on-accent)",
                backgroundColor: "var(--nv-accent-blue)",
                borderRadius: "var(--nv-radius-md)",
                padding: "6px 14px",
                letterSpacing: "0.05em",
                minWidth: 72,
                textAlign: "center",
              }}
            >
              {match.ht_home} - {match.ht_away}
            </span>
            <span style={{ fontSize: 9, color: "var(--nv-text-tertiary)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" as const }}>
              İY Skor
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 font-semibold transition-colors"
            style={{
              fontSize: 12,
              backgroundColor: expanded ? "var(--nv-accent-green-dim)" : "var(--nv-bg-elevated)",
              color: expanded ? "var(--nv-accent-green)" : "var(--nv-text-secondary)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 3v18h18" />
              <path d="M7 16l4-8 4 4 6-6" />
            </svg>
            {expanded ? "Gizle" : "İY Arşiv Analizi"}
          </button>
          <Link
            href={`/analyze/${match.match_id}?home=${encodeURIComponent(homeName)}&away=${encodeURIComponent(awayName)}`}
            prefetch={false}
            className="flex items-center justify-center gap-1.5 px-4 py-2 font-semibold transition-colors"
            style={{
              fontSize: 12,
              backgroundColor: "var(--nv-accent-blue-dim)",
              color: "var(--nv-accent-blue)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            Detaylı Analiz
          </Link>
        </div>
      </div>

      {expanded && (
        <StatsPanel matchId={match.match_id} htHome={match.ht_home} htAway={match.ht_away} />
      )}
    </div>
  );
}

export default function CanliPage() {
  const [matches, setMatches] = useState<LiveHTMatch[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchMatches = useCallback(async () => {
    try {
      const data = await getLiveHTMatches();
      setMatches(data);
      setError("");
      setLastUpdate(new Date());
    } catch {
      setMatches((prev) => {
        if (prev.length === 0) setError("Canlı veri alınamadı.");
        return prev;
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMatches();
    const timer = window.setInterval(fetchMatches, POLL_INTERVAL);
    return () => window.clearInterval(timer);
  }, [fetchMatches]);

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-tight)" }}>
              Canlı
            </h1>
            {matches.length > 0 && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold"
                style={{ fontSize: 11, borderRadius: "var(--nv-radius-full)", backgroundColor: "color-mix(in srgb, var(--nv-live) 15%, transparent)", color: "var(--nv-live)" }}
              >
                <span className="nv-live-pulse" style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "var(--nv-live)" }} />
                {matches.length} maç
              </span>
            )}
          </div>
          {lastUpdate && (
            <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", fontFamily: "var(--nv-font-mono)" }}>
              {lastUpdate.toLocaleTimeString("tr-TR", { timeZone: "Europe/Istanbul", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          )}
        </div>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
          Devre arasındaki maçların A1/A2/A3 arşiv eşleşmelerine göre İY filtreli MS tahminleri
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="nv-card" style={{ borderRadius: "var(--nv-radius-lg)", overflow: "hidden" }}>
                <div className="px-3 py-1.5" style={{ backgroundColor: "var(--nv-bg-elevated)" }}>
                  <div className="nv-skeleton" style={{ width: 80, height: 12, borderRadius: 4 }} />
                </div>
                <div className="p-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 space-y-2">
                      <div className="nv-skeleton" style={{ width: "60%", height: 14, borderRadius: 4 }} />
                      <div className="nv-skeleton" style={{ width: "50%", height: 14, borderRadius: 4 }} />
                    </div>
                    <div className="nv-skeleton" style={{ width: 72, height: 44, borderRadius: 8 }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full" style={{ borderRadius: "var(--nv-radius-lg)" }}>
              <div className="w-12 h-12 rounded-full mx-auto flex items-center justify-center" style={{ backgroundColor: "var(--nv-accent-red-dim)" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--nv-accent-red)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <p className="font-medium" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{error}</p>
              <button
                onClick={() => { setLoading(true); fetchMatches(); }}
                className="px-4 py-2 font-semibold transition-colors"
                style={{ fontSize: "var(--nv-text-sm)", backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}
              >
                Tekrar Dene
              </button>
            </div>
          </div>
        )}

        {!loading && !error && matches.length === 0 && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full" style={{ borderRadius: "var(--nv-radius-lg)" }}>
              <div className="w-12 h-12 rounded-full mx-auto flex items-center justify-center" style={{ backgroundColor: "var(--nv-bg-elevated)" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--nv-text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12,6 12,12 16,14" />
                </svg>
              </div>
              <p className="font-medium" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}>
                Şu anda devre arasında maç yok.
              </p>
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
                Maçlar devre arasına girdiğinde burada A1/A2/A3 arşiv eşleşmelerine göre İY filtreli MS tahminleri görünecek.
              </p>
              <Link href="/bulten" className="inline-block font-medium transition-colors" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}>
                Bültendeki maçlara bak
              </Link>
            </div>
          </div>
        )}

        {!loading && !error && matches.length > 0 && (
          <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
            {matches.map((m) => (
              <MatchCard key={m.match_id} match={m} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
