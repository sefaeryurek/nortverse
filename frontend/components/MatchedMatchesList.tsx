"use client";

import { useEffect, useState } from "react";
import { getMatchedMatches } from "@/lib/api";
import type { MatchedMatchesResponse, MatchedMatch } from "@/lib/api";

interface Props {
  matchId: string;
  hasPatternB: boolean;
  hasPatternC: boolean;
}

function ScoreBadge({ label, score }: { label: string; score: string | null }) {
  if (!score) return null;
  return (
    <span
      style={{
        fontSize: "var(--nv-text-xs)",
        fontFamily: "var(--nv-font-mono)",
        fontWeight: 700,
        padding: "1px 5px",
        borderRadius: "var(--nv-radius-sm)",
        backgroundColor: "var(--nv-bg-elevated)",
        color: "var(--nv-text-secondary)",
      }}
    >
      <span style={{ color: "var(--nv-text-tertiary)", fontWeight: 500, marginRight: 2 }}>{label}</span>
      {score}
    </span>
  );
}

function MatchRow({ match }: { match: MatchedMatch }) {
  return (
    <div
      className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 py-2 px-2"
      style={{ borderBottom: "1px solid var(--nv-border-subtle)" }}
    >
      <div className="flex-1 min-w-0">
        <span
          className="text-xs truncate"
          style={{ color: "var(--nv-text-primary)", fontWeight: 600 }}
        >
          {match.home_team} - {match.away_team}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <ScoreBadge label="IY" score={match.ht} />
        <ScoreBadge label="2Y" score={match.h2} />
        <ScoreBadge label="MS" score={match.ft} />
      </div>
    </div>
  );
}

export default function MatchedMatchesList({ matchId, hasPatternB, hasPatternC }: Props) {
  const [data, setData] = useState<MatchedMatchesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open || data) return;
    let cancelled = false;
    setLoading(true);
    getMatchedMatches(matchId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, matchId, data]);

  if (!hasPatternB && !hasPatternC) return null;

  return (
    <div
      className="nv-card nv-fade-in"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        padding: "var(--nv-space-lg)",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left"
        style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
      >
        <span style={{ color: "var(--nv-text-tertiary)" }}>
          {open ? "▾" : "▸"}
        </span>
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-primary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          Eşleşen Arşiv Maçları
        </h3>
        <div className="flex gap-1">
          {hasPatternB && (
            <span className="nv-badge" style={{ backgroundColor: "var(--nv-accent-blue-dim)", color: "var(--nv-accent-blue)" }}>
              A1
            </span>
          )}
          {hasPatternC && (
            <span className="nv-badge" style={{ backgroundColor: "var(--nv-accent-green-dim)", color: "var(--nv-accent-green)" }}>
              A2
            </span>
          )}
        </div>
      </button>

      {open && (
        <div style={{ marginTop: "var(--nv-space-md)" }}>
          {loading && (
            <div className="text-xs" style={{ color: "var(--nv-text-tertiary)", padding: "var(--nv-space-md) 0" }}>
              Yükleniyor...
            </div>
          )}

          {data && (
            <>
              {data.archive_b.length > 0 && (
                <div style={{ marginBottom: "var(--nv-space-lg)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-bold uppercase"
                      style={{ color: "var(--nv-accent-blue)", letterSpacing: "var(--nv-tracking-wide)" }}
                    >
                      Arşiv 1 (Skor Seti Eşleşmesi)
                    </span>
                    <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
                      {data.archive_b.length} maç
                    </span>
                  </div>
                  {data.archive_b.map((m) => (
                    <MatchRow key={`b-${m.match_id}`} match={m} />
                  ))}
                </div>
              )}

              {data.archive_c.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-bold uppercase"
                      style={{ color: "var(--nv-accent-green)", letterSpacing: "var(--nv-tracking-wide)" }}
                    >
                      Arşiv 2 (Oran Eşleşmesi)
                    </span>
                    <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
                      {data.archive_c.length} maç
                    </span>
                  </div>
                  {data.archive_c.map((m) => (
                    <MatchRow key={`c-${m.match_id}`} match={m} />
                  ))}
                </div>
              )}

              {data.archive_b.length === 0 && data.archive_c.length === 0 && (
                <div className="text-xs" style={{ color: "var(--nv-text-tertiary)", padding: "var(--nv-space-md) 0" }}>
                  Eşleşen maç bulunamadı
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
