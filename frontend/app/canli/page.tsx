"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { getLiveHTMatches, getLiveHTStats, analyzeMatch } from "@/lib/api";
import type { LiveHTMatch, LiveHTStats } from "@/lib/api";
import type { AnalyzeResponse, PatternResult } from "@/lib/types";
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
          width: 32,
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
            opacity: highlight ? 1 : 0.6,
            transition: "width 0.3s ease",
          }}
        />
      </div>
      <span
        className="flex-shrink-0 font-bold"
        style={{
          width: 48,
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

function patternMatchCount(p: PatternResult | null | undefined): number {
  if (!p) return 0;
  return p.match_count ?? 0;
}

function PatternBadge({
  label,
  count,
  color,
  bgColor,
}: {
  label: string;
  count: number;
  color: string;
  bgColor: string;
}) {
  if (count === 0) return null;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold"
      style={{
        fontSize: 10,
        borderRadius: "var(--nv-radius-full)",
        backgroundColor: bgColor,
        color,
      }}
    >
      {label}
      <span style={{ fontFamily: "var(--nv-font-mono)", fontWeight: 700 }}>{count}</span>
    </span>
  );
}

function StatsPanel({
  stats,
  analysis,
}: {
  stats: LiveHTStats;
  analysis: AnalyzeResponse | null;
}) {
  const ftB = analysis?.ft_b;
  const ftC = analysis?.ft_c;
  const ftD = analysis?.ft_d;
  const bCount = patternMatchCount(ftB);
  const cCount = patternMatchCount(ftC);
  const dCount = patternMatchCount(ftD);

  const ft1 = stats.ft_result_1_pct;
  const ftX = stats.ft_result_x_pct;
  const ft2 = stats.ft_result_2_pct;
  const ftMax = Math.max(ft1, ftX, ft2);

  const h21 = stats.h2_result_1_pct;
  const h2X = stats.h2_result_x_pct;
  const h22 = stats.h2_result_2_pct;
  const h2Max = Math.max(h21, h2X, h22);

  return (
    <div
      className="nv-fade-in mt-3 space-y-4"
      style={{ borderTop: "1px solid var(--nv-border)", paddingTop: 12 }}
    >
      {/* Arsiv bilgisi + pattern badge'leri */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 font-bold"
          style={{
            fontSize: 10,
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: "var(--nv-accent-blue-dim)",
            color: "var(--nv-accent-blue)",
            letterSpacing: "0.05em",
          }}
        >
          IY {stats.ht_score}
          <span style={{ opacity: 0.7, fontWeight: 500 }}>{stats.archive_count} maç</span>
        </span>

        {(bCount > 0 || cCount > 0 || dCount > 0) && (
          <>
            <span style={{ width: 1, height: 14, backgroundColor: "var(--nv-border)" }} />
            <PatternBadge label="A1" count={bCount} color="var(--nv-accent-blue)" bgColor="var(--nv-accent-blue-dim)" />
            <PatternBadge label="A2" count={cCount} color="var(--nv-accent-green)" bgColor="var(--nv-accent-green-dim)" />
            <PatternBadge label="A3" count={dCount} color="var(--nv-accent-amber)" bgColor="color-mix(in srgb, var(--nv-accent-amber) 15%, transparent)" />
          </>
        )}
      </div>

      {/* MS sonucu */}
      <div>
        <h4
          className="font-bold mb-2"
          style={{
            fontSize: 10,
            color: "var(--nv-text-tertiary)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Maç Sonucu Tahmini
        </h4>
        <div className="space-y-1">
          <PctBar label="1" pct={ft1} color="var(--nv-win)" highlight={ft1 === ftMax} />
          <PctBar label="X" pct={ftX} color="var(--nv-draw)" highlight={ftX === ftMax} />
          <PctBar label="2" pct={ft2} color="var(--nv-loss)" highlight={ft2 === ftMax} />
        </div>
      </div>

      {/* 2Y sonucu */}
      <div>
        <h4
          className="font-bold mb-2"
          style={{
            fontSize: 10,
            color: "var(--nv-text-tertiary)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          2. Yarı Sonucu
        </h4>
        <div className="space-y-1">
          <PctBar label="1" pct={h21} color="var(--nv-win)" highlight={h21 === h2Max} />
          <PctBar label="X" pct={h2X} color="var(--nv-draw)" highlight={h2X === h2Max} />
          <PctBar label="2" pct={h22} color="var(--nv-loss)" highlight={h22 === h2Max} />
        </div>
      </div>

      {/* Ust/Alt + KG */}
      <div className="grid grid-cols-2 gap-2">
        <div
          className="p-3"
          style={{
            borderRadius: "var(--nv-radius-md)",
            backgroundColor: "var(--nv-bg-elevated)",
          }}
        >
          <span
            className="block font-bold mb-0.5"
            style={{
              fontSize: 10,
              color: "var(--nv-text-tertiary)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Üst 2.5
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-xl)",
              color:
                stats.ft_ust_25_pct >= 60
                  ? "var(--nv-accent-green)"
                  : stats.ft_ust_25_pct <= 40
                    ? "var(--nv-accent-red)"
                    : "var(--nv-text-primary)",
            }}
          >
            %{stats.ft_ust_25_pct.toFixed(0)}
          </span>
        </div>
        <div
          className="p-3"
          style={{
            borderRadius: "var(--nv-radius-md)",
            backgroundColor: "var(--nv-bg-elevated)",
          }}
        >
          <span
            className="block font-bold mb-0.5"
            style={{
              fontSize: 10,
              color: "var(--nv-text-tertiary)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            KG Var
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-xl)",
              color:
                stats.ft_kg_var_pct >= 60
                  ? "var(--nv-accent-green)"
                  : stats.ft_kg_var_pct <= 40
                    ? "var(--nv-accent-red)"
                    : "var(--nv-text-primary)",
            }}
          >
            %{stats.ft_kg_var_pct.toFixed(0)}
          </span>
        </div>
      </div>

      {/* Pattern B/C/D ozet — sadece analiz varsa */}
      {analysis && (ftB || ftC || ftD) && (
        <div>
          <h4
            className="font-bold mb-2"
            style={{
              fontSize: 10,
              color: "var(--nv-text-tertiary)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Maç Öncesi Arşiv Tahminleri
          </h4>
          <div className="space-y-1.5">
            {ftB && bCount >= 5 && (
              <PatternRow label="A1" pattern={ftB} color="var(--nv-accent-blue)" />
            )}
            {ftC && cCount >= 1 && (
              <PatternRow label="A2" pattern={ftC} color="var(--nv-accent-green)" />
            )}
            {ftD && dCount >= 1 && (
              <PatternRow label="A3" pattern={ftD} color="var(--nv-accent-amber)" />
            )}
          </div>
        </div>
      )}

      {/* En sik FT skorlari */}
      {stats.top_ft_scores.length > 0 && (
        <div>
          <h4
            className="font-bold mb-2"
            style={{
              fontSize: 10,
              color: "var(--nv-text-tertiary)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            En Sık MS Skorları
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {stats.top_ft_scores.slice(0, 8).map((s, i) => (
              <span
                key={s.score}
                className="inline-flex items-center gap-1 px-2 py-1 font-bold"
                style={{
                  fontSize: 12,
                  fontFamily: "var(--nv-font-mono)",
                  borderRadius: "var(--nv-radius-sm)",
                  backgroundColor:
                    i === 0 ? "var(--nv-accent-blue-dim)" : "var(--nv-bg-elevated)",
                  color:
                    i === 0 ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
                }}
              >
                {s.score}
                <span style={{ opacity: 0.6, fontSize: 10, fontWeight: 500 }}>
                  %{s.pct.toFixed(0)}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PatternRow({
  label,
  pattern,
  color,
}: {
  label: string;
  pattern: PatternResult;
  color: string;
}) {
  const r1 = pattern.result_1_pct ?? 0;
  const rX = pattern.result_x_pct ?? 0;
  const r2 = pattern.result_2_pct ?? 0;
  const max = Math.max(r1, rX, r2);
  const winner = max === r1 ? "1" : max === rX ? "X" : "2";

  return (
    <div
      className="flex items-center gap-2 px-2 py-1.5"
      style={{
        borderRadius: "var(--nv-radius-sm)",
        backgroundColor: "var(--nv-bg-elevated)",
      }}
    >
      <span
        className="font-bold flex-shrink-0"
        style={{
          fontSize: 10,
          color,
          width: 22,
        }}
      >
        {label}
      </span>
      <div className="flex items-center gap-3 flex-1" style={{ fontFamily: "var(--nv-font-mono)", fontSize: 11 }}>
        <span style={{ color: winner === "1" ? "var(--nv-win)" : "var(--nv-text-tertiary)", fontWeight: winner === "1" ? 700 : 400 }}>
          1: {r1.toFixed(0)}%
        </span>
        <span style={{ color: winner === "X" ? "var(--nv-draw)" : "var(--nv-text-tertiary)", fontWeight: winner === "X" ? 700 : 400 }}>
          X: {rX.toFixed(0)}%
        </span>
        <span style={{ color: winner === "2" ? "var(--nv-loss)" : "var(--nv-text-tertiary)", fontWeight: winner === "2" ? 700 : 400 }}>
          2: {r2.toFixed(0)}%
        </span>
      </div>
      <span
        className="flex-shrink-0 font-bold"
        style={{
          fontSize: 10,
          color: "var(--nv-text-tertiary)",
        }}
      >
        {pattern.match_count} maç
      </span>
    </div>
  );
}

function MatchCard({ match }: { match: LiveHTMatch }) {
  const [expanded, setExpanded] = useState(false);
  const [stats, setStats] = useState<LiveHTStats | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [statsError, setStatsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const fetchedRef = useRef(false);

  const toggle = useCallback(async () => {
    if (!expanded && !fetchedRef.current) {
      setLoading(true);
      setStatsError(false);
      try {
        const [statsData, analysisData] = await Promise.allSettled([
          getLiveHTStats(match.ht_home, match.ht_away),
          analyzeMatch(match.match_id),
        ]);
        if (statsData.status === "fulfilled") setStats(statsData.value);
        else setStatsError(true);
        if (analysisData.status === "fulfilled") setAnalysis(analysisData.value);
        fetchedRef.current = true;
      } catch {
        setStatsError(true);
      } finally {
        setLoading(false);
      }
    }
    setExpanded((v) => !v);
  }, [expanded, match.ht_home, match.ht_away, match.match_id]);

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
    <div
      className="nv-card nv-fade-in"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        overflow: "hidden",
      }}
    >
      {/* Ust bar: lig + dakika */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 sm:px-4"
        style={{
          backgroundColor: "var(--nv-bg-elevated)",
          borderBottom: "1px solid var(--nv-border-subtle)",
        }}
      >
        <span className="flex items-center gap-1 flex-shrink-0" title={match.league_name ?? ""}>
          <span className="text-sm leading-none" aria-hidden="true">
            {flag}
          </span>
          <span
            className="font-semibold"
            style={{
              fontSize: 11,
              color: "var(--nv-text-tertiary)",
            }}
          >
            {short}
          </span>
        </span>

        {match.kickoff_time && (
          <span
            className="flex-shrink-0"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: 11,
              color: "var(--nv-text-tertiary)",
            }}
          >
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
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "var(--nv-live)",
            }}
          />
          {minuteLabel}
        </span>
      </div>

      {/* Ana icerik: takimlar + skor + butonlar */}
      <div className="px-3 py-3 sm:px-4">
        <div className="flex items-center gap-3">
          {/* Takimlar */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1">
              <span
                className="font-bold truncate"
                style={{
                  fontSize: "var(--nv-text-sm)",
                  color: "var(--nv-text-primary)",
                  lineHeight: 1.3,
                }}
              >
                {homeName}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="font-bold truncate"
                style={{
                  fontSize: "var(--nv-text-sm)",
                  color: "var(--nv-text-primary)",
                  lineHeight: 1.3,
                }}
              >
                {awayName}
              </span>
            </div>
          </div>

          {/* IY Skor */}
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
            <span
              style={{
                fontSize: 9,
                color: "var(--nv-text-tertiary)",
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              IY Skor
            </span>
          </div>
        </div>

        {/* Alt butonlar */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={toggle}
            aria-expanded={expanded}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 font-semibold transition-colors"
            style={{
              fontSize: 12,
              backgroundColor: expanded
                ? "var(--nv-accent-green-dim)"
                : "var(--nv-bg-elevated)",
              color: expanded ? "var(--nv-accent-green)" : "var(--nv-text-secondary)",
              borderRadius: "var(--nv-radius-md)",
              border: "1px solid transparent",
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 3v18h18" />
              <path d="M7 16l4-8 4 4 6-6" />
            </svg>
            {loading ? "Yükleniyor..." : expanded ? "Gizle" : "İstatistikler"}
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
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            Detaylı Analiz
          </Link>
        </div>
      </div>

      {/* Stats panel */}
      {expanded && (
        <div className="px-3 pb-3 sm:px-4 sm:pb-4">
          {loading && (
            <div className="py-6 text-center">
              <div className="nv-skeleton h-4 w-24 mx-auto mb-3" style={{ borderRadius: "var(--nv-radius-sm)" }} />
              <div className="nv-skeleton h-4 w-32 mx-auto" style={{ borderRadius: "var(--nv-radius-sm)" }} />
            </div>
          )}
          {!loading && stats && stats.archive_count > 0 && (
            <StatsPanel stats={stats} analysis={analysis} />
          )}
          {!loading && stats && stats.archive_count === 0 && (
            <div
              className="text-center py-4"
              style={{
                borderTop: "1px solid var(--nv-border)",
                fontSize: "var(--nv-text-xs)",
                color: "var(--nv-text-tertiary)",
              }}
            >
              Bu İY skoru ({stats.ht_score}) için arşivde yeterli veri yok.
            </div>
          )}
          {!loading && statsError && !stats && (
            <div
              className="text-center py-4"
              style={{
                borderTop: "1px solid var(--nv-border)",
                fontSize: "var(--nv-text-xs)",
                color: "var(--nv-accent-red)",
              }}
            >
              İstatistik alınamadı.{" "}
              <button
                onClick={() => {
                  fetchedRef.current = false;
                  toggle();
                }}
                className="underline font-medium"
                style={{ color: "var(--nv-accent-blue)" }}
              >
                Tekrar dene
              </button>
            </div>
          )}
        </div>
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
      {/* Baslik */}
      <div
        className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1
              className="font-bold"
              style={{
                fontSize: "var(--nv-text-xl)",
                color: "var(--nv-text-primary)",
                letterSpacing: "var(--nv-tracking-tight)",
              }}
            >
              Canlı
            </h1>
            {matches.length > 0 && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold"
                style={{
                  fontSize: 11,
                  borderRadius: "var(--nv-radius-full)",
                  backgroundColor: "color-mix(in srgb, var(--nv-live) 15%, transparent)",
                  color: "var(--nv-live)",
                }}
              >
                <span
                  className="nv-live-pulse"
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    backgroundColor: "var(--nv-live)",
                  }}
                />
                {matches.length} maç
              </span>
            )}
          </div>
          {lastUpdate && (
            <span
              style={{
                fontSize: "var(--nv-text-xs)",
                color: "var(--nv-text-tertiary)",
                fontFamily: "var(--nv-font-mono)",
              }}
            >
              {lastUpdate.toLocaleTimeString("tr-TR", {
                timeZone: "Europe/Istanbul",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          )}
        </div>
        <p
          className="mt-1"
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          Devre arasındaki maçlar ve arşiv istatistikleri — her 45 saniyede güncellenir
        </p>
      </div>

      {/* Icerik */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div
            className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
            style={{ maxWidth: "var(--nv-max-content)" }}
          >
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
              <div
                className="w-12 h-12 rounded-full mx-auto flex items-center justify-center"
                style={{ backgroundColor: "var(--nv-accent-red-dim)" }}
              >
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--nv-accent-red)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <p
                className="font-medium"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}
              >
                {error}
              </p>
              <button
                onClick={() => {
                  setLoading(true);
                  fetchMatches();
                }}
                className="px-4 py-2 font-semibold transition-colors"
                style={{
                  fontSize: "var(--nv-text-sm)",
                  backgroundColor: "var(--nv-accent-blue)",
                  color: "var(--nv-text-on-accent)",
                  borderRadius: "var(--nv-radius-md)",
                }}
              >
                Tekrar Dene
              </button>
            </div>
          </div>
        )}

        {!loading && !error && matches.length === 0 && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full" style={{ borderRadius: "var(--nv-radius-lg)" }}>
              <div
                className="w-12 h-12 rounded-full mx-auto flex items-center justify-center"
                style={{ backgroundColor: "var(--nv-bg-elevated)" }}
              >
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--nv-text-tertiary)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12,6 12,12 16,14" />
                </svg>
              </div>
              <p
                className="font-medium"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}
              >
                Şu anda devre arasında maç yok.
              </p>
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
                Maçlar devre arasına girdiğinde burada İY skoru ve arşiv tahminleriyle birlikte görünecek.
              </p>
              <Link
                href="/bulten"
                className="inline-block font-medium transition-colors"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}
              >
                Bültendeki maçlara bak
              </Link>
            </div>
          </div>
        )}

        {!loading && !error && matches.length > 0 && (
          <div
            className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
            style={{ maxWidth: "var(--nv-max-content)" }}
          >
            {matches.map((m) => (
              <MatchCard key={m.match_id} match={m} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
