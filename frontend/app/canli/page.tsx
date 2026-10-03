"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { getLiveHTMatches, getLiveHTStats } from "@/lib/api";
import type { LiveHTMatch, LiveHTStats } from "@/lib/api";
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

function PctBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="flex-shrink-0 font-medium"
        style={{
          width: 40,
          fontSize: "var(--nv-text-xs)",
          color: "var(--nv-text-secondary)",
          textAlign: "right",
        }}
      >
        {label}
      </span>
      <div className="nv-pct-bar flex-1">
        <div
          className="nv-pct-bar-fill"
          style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }}
        />
      </div>
      <span
        className="flex-shrink-0 font-bold"
        style={{
          width: 44,
          fontFamily: "var(--nv-font-mono)",
          fontSize: "var(--nv-text-xs)",
          color: "var(--nv-text-primary)",
        }}
      >
        %{pct.toFixed(1)}
      </span>
    </div>
  );
}

function StatsPanel({ stats }: { stats: LiveHTStats }) {
  return (
    <div
      className="nv-fade-in mt-3 pt-3 space-y-4"
      style={{ borderTop: "1px solid var(--nv-border)" }}
    >
      <div className="flex items-center gap-2">
        <span
          className="nv-badge"
          style={{
            backgroundColor: "var(--nv-accent-blue-dim)",
            color: "var(--nv-accent-blue)",
          }}
        >
          {stats.archive_count} arsiv maci
        </span>
        <span
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          IY {stats.ht_score} ile devreyi kapatan maclar
        </span>
      </div>

      {/* MS 1/X/2 */}
      <div>
        <h4
          className="font-semibold mb-2"
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
        >
          Mac Sonucu
        </h4>
        <div className="space-y-1.5">
          <PctBar label="MS1" pct={stats.ft_result_1_pct} color="var(--nv-win)" />
          <PctBar label="X" pct={stats.ft_result_x_pct} color="var(--nv-draw)" />
          <PctBar label="MS2" pct={stats.ft_result_2_pct} color="var(--nv-loss)" />
        </div>
      </div>

      {/* 2Y 1/X/2 */}
      <div>
        <h4
          className="font-semibold mb-2"
          style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
        >
          2. Yari Sonucu
        </h4>
        <div className="space-y-1.5">
          <PctBar label="2Y1" pct={stats.h2_result_1_pct} color="var(--nv-win)" />
          <PctBar label="X" pct={stats.h2_result_x_pct} color="var(--nv-draw)" />
          <PctBar label="2Y2" pct={stats.h2_result_2_pct} color="var(--nv-loss)" />
        </div>
      </div>

      {/* Ust/Alt + KG */}
      <div className="grid grid-cols-2 gap-3">
        <div className="nv-card p-3" style={{ backgroundColor: "var(--nv-bg-elevated)" }}>
          <span
            className="block font-semibold mb-1"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
          >
            Ust 2.5
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-lg)",
              color: stats.ft_ust_25_pct >= 55
                ? "var(--nv-accent-green)"
                : "var(--nv-text-primary)",
            }}
          >
            %{stats.ft_ust_25_pct.toFixed(1)}
          </span>
        </div>
        <div className="nv-card p-3" style={{ backgroundColor: "var(--nv-bg-elevated)" }}>
          <span
            className="block font-semibold mb-1"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
          >
            KG Var
          </span>
          <span
            className="block font-bold"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-lg)",
              color: stats.ft_kg_var_pct >= 55
                ? "var(--nv-accent-green)"
                : "var(--nv-text-primary)",
            }}
          >
            %{stats.ft_kg_var_pct.toFixed(1)}
          </span>
        </div>
      </div>

      {/* En sik FT skorlari */}
      {stats.top_ft_scores.length > 0 && (
        <div>
          <h4
            className="font-semibold mb-2"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}
          >
            En Sik MS Skorlari
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {stats.top_ft_scores.slice(0, 8).map((s, i) => (
              <span
                key={s.score}
                className="nv-badge"
                style={{
                  backgroundColor: i === 0
                    ? "var(--nv-accent-blue-dim)"
                    : "var(--nv-bg-elevated)",
                  color: i === 0
                    ? "var(--nv-accent-blue)"
                    : "var(--nv-text-secondary)",
                  fontFamily: "var(--nv-font-mono)",
                  padding: "3px 8px",
                }}
              >
                {s.score} <span style={{ opacity: 0.7 }}>%{s.pct.toFixed(0)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MatchCard({ match }: { match: LiveHTMatch }) {
  const [expanded, setExpanded] = useState(false);
  const [stats, setStats] = useState<LiveHTStats | null>(null);
  const [loading, setLoading] = useState(false);
  const fetchedRef = useRef(false);

  const toggle = useCallback(async () => {
    if (!expanded && !fetchedRef.current) {
      setLoading(true);
      try {
        const data = await getLiveHTStats(match.ht_home, match.ht_away);
        setStats(data);
        fetchedRef.current = true;
      } catch {
        /* stats gosterilmez */
      } finally {
        setLoading(false);
      }
    }
    setExpanded((v) => !v);
  }, [expanded, match.ht_home, match.ht_away]);

  const { flag, short } = leagueDisplay(null, match.league_name);
  const minuteLabel = match.live_minute === "HT"
    ? "Devre Arasi"
    : match.live_minute
      ? `${match.live_minute}'`
      : "";

  return (
    <div className="nv-card p-3 sm:p-4 nv-fade-in">
      {/* Ust satir: Lig + Dakika + IY Skor */}
      <div className="flex items-center gap-2 sm:gap-3">
        <span
          className="flex items-center gap-1 flex-shrink-0"
          title={match.league_name ?? ""}
        >
          <span className="text-base leading-none" aria-hidden="true">
            {flag}
          </span>
          <span
            className="font-semibold truncate"
            style={{
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
              maxWidth: 56,
            }}
          >
            {short}
          </span>
        </span>

        {/* Saat */}
        {match.kickoff_time && (
          <span
            className="flex-shrink-0"
            style={{
              fontFamily: "var(--nv-font-mono)",
              fontSize: "var(--nv-text-xs)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            {formatKickoff(match.kickoff_time)}
          </span>
        )}

        {/* Canli badge */}
        <span
          className="nv-badge nv-badge-red nv-live-pulse flex items-center gap-1 flex-shrink-0"
          style={{ padding: "2px 8px" }}
        >
          <span
            className="nv-live-pulse"
            style={{
              width: 6,
              height: 6,
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: "var(--nv-live)",
              boxShadow: "0 0 6px var(--nv-live-glow)",
            }}
          />
          {minuteLabel}
        </span>

        <div className="flex-1" />

        {/* IY Skor */}
        <div
          className="flex-shrink-0 font-bold px-3 py-1"
          style={{
            fontFamily: "var(--nv-font-mono)",
            fontSize: "var(--nv-text-xl)",
            color: "var(--nv-text-on-accent)",
            backgroundColor: "var(--nv-accent-blue)",
            borderRadius: "var(--nv-radius-md)",
            letterSpacing: "0.05em",
            lineHeight: 1.2,
          }}
        >
          {match.ht_home} - {match.ht_away}
        </div>
      </div>

      {/* Takimlar + butonlar */}
      <div className="flex items-center gap-2 mt-2.5">
        <div className="flex-1 min-w-0 flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-2">
          <span
            className="truncate font-medium"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}
          >
            {match.home_team ?? "Ev Sahibi"}
          </span>
          <span
            className="hidden sm:inline flex-shrink-0"
            style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
          >
            vs
          </span>
          <span
            className="truncate font-medium"
            style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}
          >
            {match.away_team ?? "Deplasman"}
          </span>
        </div>

        {/* Istatistikler toggle */}
        <button
          onClick={toggle}
          className="flex-shrink-0 flex items-center justify-center min-h-[36px] px-3 py-1.5 font-medium transition-colors"
          style={{
            fontSize: "var(--nv-text-xs)",
            backgroundColor: expanded
              ? "var(--nv-accent-green-dim)"
              : "var(--nv-bg-elevated)",
            color: expanded
              ? "var(--nv-accent-green)"
              : "var(--nv-text-secondary)",
            borderRadius: "var(--nv-radius-md)",
          }}
        >
          {loading ? "..." : expanded ? "Gizle" : "Istatistik"}
        </button>

        {/* Analiz linki */}
        <Link
          href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team ?? "")}&away=${encodeURIComponent(match.away_team ?? "")}`}
          prefetch={false}
          className="flex-shrink-0 flex items-center justify-center min-h-[36px] px-3 py-1.5 font-medium transition-colors"
          style={{
            fontSize: "var(--nv-text-xs)",
            backgroundColor: "var(--nv-accent-blue-dim)",
            color: "var(--nv-accent-blue)",
            borderRadius: "var(--nv-radius-md)",
          }}
        >
          Analiz
        </Link>
      </div>

      {/* Inline stats panel */}
      {expanded && stats && stats.archive_count > 0 && <StatsPanel stats={stats} />}
      {expanded && stats && stats.archive_count === 0 && (
        <div
          className="mt-3 pt-3 text-center"
          style={{
            borderTop: "1px solid var(--nv-border)",
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          Bu IY skoru icin arsivde yeterli veri yok.
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
      setError("Canli veri alinamadi.");
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
              Canli
            </h1>
            {matches.length > 0 && (
              <span
                className="nv-badge nv-badge-red nv-live-pulse flex items-center gap-1"
                style={{ padding: "2px 8px" }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "var(--nv-radius-full)",
                    backgroundColor: "var(--nv-live)",
                    boxShadow: "0 0 6px var(--nv-live-glow)",
                  }}
                />
                {matches.length} mac
              </span>
            )}
          </div>
          {lastUpdate && (
            <span
              style={{
                fontSize: "var(--nv-text-xs)",
                color: "var(--nv-text-tertiary)",
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
          Devre arasindaki maclar ve arsiv IY istatistikleri
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
              <div key={i} className="nv-card p-4">
                <div className="flex items-center gap-3">
                  <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
                  <div className="flex-1" />
                  <div className="nv-skeleton" style={{ width: 64, height: 36 }} />
                </div>
                <div className="flex items-center gap-3 mt-3">
                  <div className="nv-skeleton flex-1" style={{ height: 14 }} />
                  <div className="nv-skeleton flex-1" style={{ height: 14 }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center justify-center py-24 px-[var(--nv-page-gutter)]">
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--nv-accent-red)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className="mx-auto"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <p
                className="font-medium"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}
              >
                {error}
              </p>
              <button
                onClick={() => { setLoading(true); fetchMatches(); }}
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
            <div className="nv-card p-8 text-center space-y-4 max-w-sm w-full">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--nv-text-tertiary)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className="mx-auto"
              >
                <circle cx="12" cy="12" r="3" />
                <circle cx="12" cy="12" r="7" />
                <circle cx="12" cy="12" r="11" />
              </svg>
              <p
                className="font-medium"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}
              >
                Su anda devre arasinda mac yok.
              </p>
              <p
                style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}
              >
                Maclar devre arasina girdiginde burada gorunecek. Sayfa her 45 saniyede otomatik guncellenir.
              </p>
              <Link
                href="/bulten"
                className="inline-block font-medium transition-colors"
                style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-blue)" }}
              >
                Bultendeki maclara bak
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
