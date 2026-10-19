"use client";

import { useEffect, useState } from "react";
import { getMatchedMatches } from "@/lib/api";
import type { MatchedMatchesResponse, MatchedMatch } from "@/lib/api";
import { useLocale } from "@/lib/locale-context";
import type { Period } from "@/lib/labels";

const LIST_LIMIT = 50;
/** A3 = takım gücüne en yakın 200 maç; önce en yakın 20 gösterilir (Sprint 91). */
const LIST_LIMIT_D = 20;
const limitOf = (id: string) => (id === "d" ? LIST_LIMIT_D : LIST_LIMIT);

interface Props {
  matchId: string;
  period?: Period;
  hasPatternB: boolean;
  hasPatternC: boolean;
  hasPatternD?: boolean;
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

function MatchRow({ match, showSimilarity, htLabel, h2Label, ftLabel }: { match: MatchedMatch; showSimilarity?: boolean; htLabel: string; h2Label: string; ftLabel: string }) {
  return (
    <div
      className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 py-2 px-2"
      style={{ borderBottom: "1px solid var(--nv-border-subtle)" }}
    >
      <div className="flex-1 min-w-0">
        <span
          className="block text-xs truncate"
          style={{ color: "var(--nv-text-primary)", fontWeight: 600 }}
          title={`${match.home_team} - ${match.away_team}`}
        >
          {match.home_team} - {match.away_team}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {showSimilarity && match.similarity != null && (
          <span
            style={{
              fontSize: "var(--nv-text-xs)",
              fontFamily: "var(--nv-font-mono)",
              fontWeight: 600,
              padding: "1px 5px",
              borderRadius: "var(--nv-radius-sm)",
              backgroundColor: "var(--nv-accent-amber-glow)",
              color: "var(--nv-accent-amber)",
            }}
          >
            {(match.similarity * 100).toFixed(1)}%
          </span>
        )}
        <ScoreBadge label={htLabel} score={match.ht} />
        <ScoreBadge label={h2Label} score={match.h2} />
        <ScoreBadge label={ftLabel} score={match.ft} />
      </div>
    </div>
  );
}

export default function MatchedMatchesList({ matchId, period = "ft", hasPatternB, hasPatternC, hasPatternD }: Props) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [reload, setReload] = useState(0);
  const [showAll, setShowAll] = useState<Record<string, boolean>>({});
  // Sonuç maç+periyot anahtarıyla saklanır; yükleniyor durumu türetilir (effect içinde senkron setState yok).
  const key = `${matchId}:${period}`;
  const [result, setResult] = useState<{ key: string; data: MatchedMatchesResponse | null; error: boolean } | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getMatchedMatches(matchId, period)
      .then((d) => { if (!cancelled) setResult({ key, data: d, error: false }); })
      .catch((err) => {
        console.error("Matched matches fetch failed:", err);
        if (!cancelled) setResult({ key, data: null, error: true });
      });
    return () => { cancelled = true; };
  }, [open, key, matchId, period, reload]);

  const current = result?.key === key ? result : null;
  const loading = open && current === null;
  const error = current?.error ?? false;
  const data = current?.data ?? null;
  const visible = (list: MatchedMatch[], id: string) => (showAll[`${key}:${id}`] ? list : list.slice(0, limitOf(id)));
  const moreButton = (list: MatchedMatch[], id: string) => list.length > limitOf(id) && !showAll[`${key}:${id}`] && (
    <button
      onClick={() => setShowAll((prev) => ({ ...prev, [`${key}:${id}`]: true }))}
      className="text-xs font-semibold mt-1"
      style={{ color: "var(--nv-accent-blue)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
    >
      {t.analyze.showMore.replace("{count}", String(list.length - limitOf(id)))}
    </button>
  );

  if (!hasPatternB && !hasPatternC && !hasPatternD) return null;

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
        aria-expanded={open}
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
          {t.analyze.matchedMatches}
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
          {hasPatternD && (
            <span className="nv-badge" style={{ backgroundColor: "var(--nv-accent-amber-glow)", color: "var(--nv-accent-amber)" }}>
              A3
            </span>
          )}
        </div>
      </button>

      {open && (
        <div style={{ marginTop: "var(--nv-space-md)" }}>
          {loading && (
            <div className="text-xs" style={{ color: "var(--nv-text-tertiary)", padding: "var(--nv-space-md) 0" }}>
              {t.analyze.loading}
            </div>
          )}

          {error && !loading && (
            <div className="flex items-center gap-2" style={{ padding: "var(--nv-space-md) 0" }}>
              <span className="text-xs" style={{ color: "var(--nv-text-tertiary)" }}>{t.analyze.loadError}</span>
              <button
                onClick={() => { setResult(null); setReload((r) => r + 1); }}
                className="text-xs font-semibold"
                style={{ color: "var(--nv-accent-blue)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                {t.common.retry}
              </button>
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
                      {t.analyze.archive1ScoreSet}
                    </span>
                    <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
                      {data.archive_b.length} {t.common.match}
                    </span>
                  </div>
                  {visible(data.archive_b, "b").map((m) => (
                    <MatchRow key={`b-${m.match_id}`} match={m} htLabel={t.periodTabs.htShort} h2Label={t.periodTabs.h2Short} ftLabel={t.periodTabs.ftShort} />
                  ))}
                  {moreButton(data.archive_b, "b")}
                </div>
              )}

              {data.archive_c.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-bold uppercase"
                      style={{ color: "var(--nv-accent-green)", letterSpacing: "var(--nv-tracking-wide)" }}
                    >
                      {t.analyze.archive2RatioMatch}
                    </span>
                    <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
                      {data.archive_c.length} {t.common.match}
                    </span>
                  </div>
                  {visible(data.archive_c, "c").map((m) => (
                    <MatchRow key={`c-${m.match_id}`} match={m} htLabel={t.periodTabs.htShort} h2Label={t.periodTabs.h2Short} ftLabel={t.periodTabs.ftShort} />
                  ))}
                  {moreButton(data.archive_c, "c")}
                </div>
              )}

              {data.archive_d && data.archive_d.length > 0 && (
                <div style={{ marginTop: data.archive_b.length > 0 || data.archive_c.length > 0 ? "var(--nv-space-lg)" : 0 }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-bold uppercase"
                      style={{ color: "var(--nv-accent-amber)", letterSpacing: "var(--nv-tracking-wide)" }}
                    >
                      {t.analyze.archive3Cosine}
                    </span>
                    <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
                      {data.archive_d.length} {t.common.match}
                    </span>
                  </div>
                  {visible(data.archive_d, "d").map((m) => (
                    <MatchRow key={`d-${m.match_id}`} match={m} showSimilarity htLabel={t.periodTabs.htShort} h2Label={t.periodTabs.h2Short} ftLabel={t.periodTabs.ftShort} />
                  ))}
                  {moreButton(data.archive_d, "d")}
                </div>
              )}

              {data.archive_b.length === 0 && data.archive_c.length === 0 && (!data.archive_d || data.archive_d.length === 0) && (
                <div className="text-xs" style={{ color: "var(--nv-text-tertiary)", padding: "var(--nv-space-md) 0" }}>
                  {data.list_available && Object.values(data.list_available).some((ok) => !ok)
                    ? t.analyze.listNotStored
                    : t.analyze.noMatchesFound}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
