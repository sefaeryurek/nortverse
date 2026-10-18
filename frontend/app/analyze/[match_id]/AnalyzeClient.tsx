"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import type { AnalyzeResponse } from "@/lib/types";
import { analyzeMatch } from "@/lib/api";
import ScoreList from "@/components/ScoreList";
import PowerScoreGauge, { computePowerScore } from "@/components/PowerScoreGauge";
import MatchedMatchesList from "@/components/MatchedMatchesList";
import { MatchProvider } from "@/lib/match-context";
import { useLocale } from "@/lib/locale-context";

const IddaaCoupon = dynamic(() => import("@/components/IddaaCoupon"));
const TrendsPanel = dynamic(() => import("@/components/TrendsPanel"));

type Period = "ht" | "h2" | "ft";

const PERIOD_KEYS: Period[] = ["ht", "h2", "ft"];

function patternFor(data: AnalyzeResponse, period: Period) {
  return {
    b: period === "ht" ? data.ht_b : period === "h2" ? data.h2_b : data.ft_b,
    c: period === "ht" ? data.ht_c : period === "h2" ? data.h2_c : data.ft_c,
    d: period === "ht" ? data.ht_d : period === "h2" ? data.h2_d : data.ft_d,
  };
}

function scoresFor(data: AnalyzeResponse, period: Period) {
  const p = period === "ht" ? data.ht : period === "h2" ? data.half2 : data.ft;
  return { scores_1: p.scores_1, scores_x: p.scores_x, scores_2: p.scores_2 };
}

interface Props {
  match_id: string;
  initialData: AnalyzeResponse | null;
  initialError: string;
  urlHome: string;
  urlAway: string;
}

export default function AnalyzeClient({ match_id, initialData, initialError, urlHome, urlAway }: Props) {
  const { t } = useLocale();
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [data, setData] = useState<AnalyzeResponse | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(initialError);
  const [activePeriod, setActivePeriod] = useState<Period>("ft");
  const [isPending, startTransition] = useTransition();

  const changePeriod = (key: Period) => {
    if (key === activePeriod) return;
    startTransition(() => setActivePeriod(key));
  };

  useEffect(() => {
    if (attempt === 0) return;
    let cancelled = false;
    const controller = new AbortController();
    analyzeMatch(match_id, controller.signal)
      .then((d) => { if (!cancelled) { setData(d); setError(""); } })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [attempt, match_id]);



  const retry = () => {
    setError("");
    setLoading(true);
    setAttempt((n) => n + 1);
  };

  const { b: patternB, c: patternC, d: patternD } = data
    ? patternFor(data, activePeriod)
    : { b: null, c: null, d: null };
  const scores = data ? scoresFor(data, activePeriod) : null;

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      {/* Hero header */}
      <div
        className="px-5 py-5 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <div className="flex items-start gap-3">
          {/* Back button */}
          <button
            onClick={() => (window.history.length > 1 ? router.back() : router.push("/bulten"))}
            aria-label={t.analyze.backLabel}
            className="flex items-center justify-center w-9 h-9 flex-shrink-0 transition-all"
            style={{
              backgroundColor: "var(--nv-bg-card)",
              border: "1px solid var(--nv-border)",
              borderRadius: "var(--nv-radius-full)",
              color: "var(--nv-text-secondary)",
              transitionDuration: "var(--nv-duration-normal)",
              transitionTimingFunction: "var(--nv-ease)",
            }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex-1 min-w-0">
            {data ? (
              <>
                <h1
                  className="font-bold break-words sm:truncate"
                  style={{
                    color: "var(--nv-text-primary)",
                    fontSize: "var(--nv-text-2xl)",
                    lineHeight: "var(--nv-leading-tight)",
                    letterSpacing: "var(--nv-tracking-tight)",
                  }}
                >
                  {data.home_team}
                  <span className="mx-2" style={{ color: "var(--nv-text-tertiary)", fontSize: "var(--nv-text-lg)" }}>
                    vs
                  </span>
                  {data.away_team}
                </h1>
                <div className="flex items-center gap-2 mt-1">
                  <span className="nv-badge nv-badge-blue">
                    {data.league_code}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "var(--nv-text-tertiary)" }}
                  >
                    {data.season}
                  </span>
                </div>
              </>
            ) : urlHome && urlAway ? (
              <h1
                className="font-bold break-words sm:truncate"
                style={{
                  color: "var(--nv-text-primary)",
                  fontSize: "var(--nv-text-2xl)",
                  lineHeight: "var(--nv-leading-tight)",
                }}
              >
                {urlHome}
                <span className="mx-2" style={{ color: "var(--nv-text-tertiary)", fontSize: "var(--nv-text-lg)" }}>
                  vs
                </span>
                {urlAway}
              </h1>
            ) : (
              <h1
                className="font-bold"
                style={{
                  color: "var(--nv-text-primary)",
                  fontSize: "var(--nv-text-2xl)",
                }}
              >
                {t.analyze.matchNo.replace("{id}", match_id)}
              </h1>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center py-32 px-4">
            {/* Skeleton loading bars */}
            <div className="w-full max-w-md space-y-4">
              <div className="nv-skeleton h-8 w-3/4 mx-auto" style={{ borderRadius: "var(--nv-radius-sm)" }} />
              <div className="nv-skeleton h-4 w-1/2 mx-auto" style={{ borderRadius: "var(--nv-radius-sm)" }} />
              <div className="space-y-2 mt-6">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="nv-skeleton h-12" style={{ borderRadius: "var(--nv-radius-md)" }} />
                ))}
              </div>
            </div>
            <p
              className="text-sm font-medium mt-6"
              style={{ color: "var(--nv-text-primary)" }}
            >
              {t.analyze.analyzing}
            </p>
            <p
              className="text-xs mt-1"
              style={{ color: "var(--nv-text-tertiary)" }}
            >
              {t.analyze.analyzingNote}
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="p-6">
            <div
              className="nv-card text-center"
              style={{
                borderRadius: "var(--nv-radius-lg)",
                borderColor: "var(--nv-accent-red)",
                padding: "var(--nv-space-2xl)",
              }}
            >
              <div
                className="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{
                  backgroundColor: "var(--nv-accent-red-dim)",
                }}
              >
                <svg className="w-6 h-6" fill="none" stroke="var(--nv-accent-red)" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <p
                className="text-sm font-medium"
                style={{ color: "var(--nv-accent-red)" }}
              >
                {error}
              </p>
              <button
                onClick={retry}
                className="mt-4 px-4 py-2 text-sm font-semibold transition-all"
                style={{
                  backgroundColor: "var(--nv-accent-blue)",
                  color: "var(--nv-text-on-accent)",
                  borderRadius: "var(--nv-radius-md)",
                  transitionDuration: "var(--nv-duration-normal)",
                }}
              >
                {t.common.retry}
              </button>
            </div>
          </div>
        )}

        {data && !loading && (
          <div className="p-4 space-y-4">
            {/* Kural disi */}
            {data.skipped && (
              <div
                className="nv-card nv-fade-in"
                style={{
                  borderRadius: "var(--nv-radius-lg)",
                  borderColor: "var(--nv-accent-amber)",
                  padding: "var(--nv-space-lg)",
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: "var(--nv-accent-amber-dim)" }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="var(--nv-accent-amber)" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "var(--nv-accent-amber)" }}>
                      {t.analyze.noForecast}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--nv-text-tertiary)" }}>
                      {(data.skip_reason && t.skipReasons[data.skip_reason as keyof typeof t.skipReasons]) ?? data.skip_reason}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {!data.skipped && (
              <>
                {/* Period tabs */}
                <div className="flex gap-2" role="tablist">
                  {PERIOD_KEYS.map((key) => (
                    <button
                      key={key}
                      role="tab"
                      aria-selected={activePeriod === key}
                      onClick={() => changePeriod(key)}
                      className="px-4 py-2 text-sm font-semibold transition-all"
                      style={{
                        backgroundColor: activePeriod === key ? "var(--nv-accent-blue)" : "var(--nv-bg-card)",
                        color: activePeriod === key ? "var(--nv-text-on-accent)" : "var(--nv-text-secondary)",
                        border: `1px solid ${activePeriod === key ? "var(--nv-accent-blue)" : "var(--nv-border)"}`,
                        borderRadius: "var(--nv-radius-full)",
                        boxShadow: activePeriod === key
                          ? "var(--nv-shadow-glow-blue)"
                          : "none",
                        transitionDuration: "var(--nv-duration-normal)",
                        transitionTimingFunction: "var(--nv-ease)",
                      }}
                    >
                      <span className="hidden sm:inline">{t.periodTabs[key]}</span>
                      <span className="sm:hidden">{t.periodTabs[`${key}Short` as keyof typeof t.periodTabs]}</span>
                    </button>
                  ))}
                </div>

                {/* Period content -- pending iken hafif soluk */}
                <div
                  className="space-y-4 transition-opacity"
                  style={{
                    opacity: isPending ? 0.6 : 1,
                    transitionDuration: "var(--nv-duration-fast)",
                  }}
                >

                {activePeriod === "ft" && (
                  <PowerScoreGauge
                    score={computePowerScore(data, patternB, patternC, patternD)}
                    patternB={patternB}
                    patternC={patternC}
                    patternD={patternD}
                    trendCount={data.trends ? [data.trends.home_form, data.trends.away_form, data.trends.h2h].filter(Boolean).length : 0}
                  />
                )}

                {/* Form & H2H trendleri -- sadece MS periyodunda anlamli */}
                {activePeriod === "ft" && data.trends && (
                  <TrendsPanel
                    trends={data.trends}
                    homeTeam={data.home_team}
                    awayTeam={data.away_team}
                  />
                )}

                {/* Katman A -- 3.5+ skor dagilimi */}
                {scores && (scores.scores_1.length > 0 || scores.scores_x.length > 0 || scores.scores_2.length > 0) && (
                  <div
                    className="nv-card nv-fade-in space-y-3"
                    style={{
                      borderRadius: "var(--nv-radius-lg)",
                      padding: "var(--nv-space-lg)",
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: "var(--nv-accent-blue)" }}
                      />
                      <h3
                        className="text-sm font-bold"
                        style={{
                          color: "var(--nv-accent-blue)",
                          letterSpacing: "var(--nv-tracking-wide)",
                        }}
                      >
                        {t.analyze.layerA}
                      </h3>
                      <span
                        className="nv-badge ml-auto"
                        style={{
                          backgroundColor: "var(--nv-bg-elevated)",
                          color: "var(--nv-text-tertiary)",
                        }}
                      >
                        {t.analyze.scoreCount.replace("{count}", String(scores.scores_1.length + scores.scores_x.length + scores.scores_2.length))}
                      </span>
                    </div>
                    <div className="flex gap-3">
                      <ScoreList scores={scores.scores_1} type="1" label={t.analyze.homeWins} />
                      <ScoreList scores={scores.scores_x} type="x" label={t.analyze.drawLabel} />
                      <ScoreList scores={scores.scores_2} type="2" label={t.analyze.awayWins} />
                    </div>
                  </div>
                )}

                {scores && scores.scores_1.length === 0 && scores.scores_x.length === 0 && scores.scores_2.length === 0 && (
                  <div
                    className="nv-card text-center"
                    style={{
                      borderRadius: "var(--nv-radius-lg)",
                      padding: "var(--nv-space-lg)",
                    }}
                  >
                    <p className="text-sm font-medium" style={{ color: "var(--nv-text-tertiary)" }}>
                      {t.analyze.noScores}
                    </p>
                  </div>
                )}

                {/* Bos skor listesinde de arsiv eslesmeleri bulunabilir. */}
                <MatchProvider value={{ matchId: data.match_id, homeTeam: data.home_team, awayTeam: data.away_team }}>
                  <IddaaCoupon
                    patternB={patternB}
                    patternC={patternC}
                    patternD={patternD}
                    period={activePeriod}
                    recommendations={data.ft_recommendations}
                  />
                </MatchProvider>

                <MatchedMatchesList
                  matchId={data.match_id}
                  period={activePeriod}
                  hasPatternB={!!patternB && patternB.match_count >= 5}
                  hasPatternC={!!patternC && patternC.match_count >= 1}
                  hasPatternD={!!patternD && patternD.match_count >= 1}
                />
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
