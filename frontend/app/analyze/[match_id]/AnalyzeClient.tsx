"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import type { AnalysisEvidence, AnalysisValidation, AnalyzeResponse, PatternResult, ScoreValidation } from "@/lib/types";
import { analyzeMatch, getAnalysisEvidence, getAnalysisValidation, getScoreValidation } from "@/lib/api";
import ScoreList from "@/components/ScoreList";
import { MatchProvider } from "@/lib/match-context";

const IddaaCoupon = dynamic(() => import("@/components/IddaaCoupon"));
const TrendsPanel = dynamic(() => import("@/components/TrendsPanel"));

type Period = "ht" | "h2" | "ft";

const SKIP_REASON_LABELS: Record<string, string> = {
  not_league_match: "Bu maç lig maçı değil (kupa veya özel maç). Tahmin üretilemez.",
  home_team_insufficient: "Ev sahibi takım bu sezonda yeterli lig maçı oynamamış (minimum 5 gerekiyor).",
  away_team_insufficient: "Deplasman takımı bu sezonda yeterli lig maçı oynamamış (minimum 5 gerekiyor).",
  h2h_insufficient: "Bu iki takım arasında yeterli karşılaşma geçmişi bulunamadı (minimum 5 lig maçı gerekiyor).",
  data_fetch_failed: "Maç verisi alınırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
};

const PERIODS: { key: Period; label: string; short: string }[] = [
  { key: "ht", label: "1. Yarı (İY)", short: "İY" },
  { key: "h2", label: "2. Yarı (2Y)", short: "2Y" },
  { key: "ft", label: "Maç Sonu (MS)", short: "MS" },
];

function patternFor(data: AnalyzeResponse, period: Period) {
  return {
    b: period === "ht" ? data.ht_b : period === "h2" ? data.h2_b : data.ft_b,
    c: period === "ht" ? data.ht_c : period === "h2" ? data.h2_c : data.ft_c,
  };
}

function scoresFor(data: AnalyzeResponse, period: Period) {
  const p = period === "ht" ? data.ht : period === "h2" ? data.half2 : data.ft;
  return { scores_1: p.scores_1, scores_x: p.scores_x, scores_2: p.scores_2 };
}

function computePowerScore(data: AnalyzeResponse, patternB: PatternResult | null, patternC: PatternResult | null): number {
  let score = 0;
  let factors = 0;

  // Factor 1: Pattern B match count (volume)
  if (patternB && patternB.match_count > 0) {
    score += Math.min(30, patternB.match_count); // max 30 points
    factors++;
  }

  // Factor 2: Pattern C match count (volume)
  if (patternC && patternC.match_count > 0) {
    score += Math.min(20, patternC.match_count * 2); // max 20 points, C has fewer matches
    factors++;
  }

  // Factor 3: Top selection confidence
  const topPct = Math.max(
    patternB?.result_1_pct ?? 0,
    patternB?.result_x_pct ?? 0,
    patternB?.result_2_pct ?? 0,
    patternB?.ust_25_pct ?? 0,
    patternB?.alt_25_pct ?? 0,
    patternB?.kg_var_pct ?? 0,
    patternB?.kg_yok_pct ?? 0,
  );
  if (topPct > 0) {
    score += Math.round(topPct * 0.3); // max ~30 points
    factors++;
  }

  // Factor 4: Trends available
  if (data.trends) {
    const trendBlocks = [data.trends.home_form, data.trends.away_form, data.trends.h2h].filter(Boolean).length;
    score += trendBlocks * 5; // max 15 points (3 blocks x 5)
    factors++;
  }

  // Factor 5: Both archives agree
  if (patternB && patternC && patternB.match_count >= 5 && patternC.match_count >= 1) {
    score += 5;
    factors++;
  }

  return factors > 0 ? Math.min(100, score) : 0;
}

interface Props {
  match_id: string;
  initialData: AnalyzeResponse | null;
  evidence?: AnalysisEvidence | null;
  initialError: string;
  urlHome: string;
  urlAway: string;
}

export default function AnalyzeClient({ match_id, initialData, evidence, initialError, urlHome, urlAway }: Props) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [data, setData] = useState<AnalyzeResponse | null>(initialData);
  const [evidenceData, setEvidenceData] = useState<AnalysisEvidence | null>(evidence ?? null);
  const [validationData, setValidationData] = useState<AnalysisValidation | null>(null);
  const [scoreValidation, setScoreValidation] = useState<ScoreValidation | null>(null);
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

  useEffect(() => {
    if (evidence || !data || data.skipped) return;
    let cancelled = false;
    getAnalysisEvidence()
      .then((value) => { if (!cancelled) setEvidenceData(value); })
      .catch(() => { /* Optional coverage data must not delay the analysis. */ });
    return () => { cancelled = true; };
  }, [data, evidence]);

  useEffect(() => {
    if (!data || data.skipped) return;
    let cancelled = false;
    getAnalysisValidation()
      .then((value) => { if (!cancelled) setValidationData(value); })
      .catch(() => { /* Optional outcome data must not delay the analysis. */ });
    return () => { cancelled = true; };
  }, [data]);

  useEffect(() => {
    if (!data || data.skipped) return;
    let cancelled = false;
    getScoreValidation()
      .then((value) => { if (!cancelled) setScoreValidation(value); })
      .catch(() => { /* Optional comparison must not delay the analysis. */ });
    return () => { cancelled = true; };
  }, [data]);

  const retry = () => {
    setError("");
    setLoading(true);
    setAttempt((n) => n + 1);
  };

  const { b: patternB, c: patternC } = data
    ? patternFor(data, activePeriod)
    : { b: null, c: null };
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
            onClick={() => router.back()}
            aria-label="Önceki sayfaya dön"
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
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
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
                Maç #{match_id}
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
              Analiz yükleniyor...
            </p>
            <p
              className="text-xs mt-1"
              style={{ color: "var(--nv-text-tertiary)" }}
            >
              İlk analiz veri kaynağına göre daha uzun sürebilir.
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
                <svg className="w-6 h-6" fill="none" stroke="var(--nv-accent-red)" strokeWidth={2} viewBox="0 0 24 24">
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
                  color: "white",
                  borderRadius: "var(--nv-radius-md)",
                  transitionDuration: "var(--nv-duration-normal)",
                }}
              >
                Tekrar dene
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
                    <svg className="w-4 h-4" fill="none" stroke="var(--nv-accent-amber)" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "var(--nv-accent-amber)" }}>
                      Bu maç için tahmin üretilemedi
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--nv-text-tertiary)" }}>
                      {(data.skip_reason && SKIP_REASON_LABELS[data.skip_reason]) ?? data.skip_reason}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {!data.skipped && (
              <>
                {/* Period tabs */}
                <div className="flex gap-2">
                  {PERIODS.map(({ key, label, short }) => (
                    <button
                      key={key}
                      onClick={() => changePeriod(key)}
                      className="px-4 py-2 text-sm font-semibold transition-all"
                      style={{
                        backgroundColor: activePeriod === key ? "var(--nv-accent-blue)" : "var(--nv-bg-card)",
                        color: activePeriod === key ? "white" : "var(--nv-text-secondary)",
                        border: `1px solid ${activePeriod === key ? "var(--nv-accent-blue)" : "var(--nv-border)"}`,
                        borderRadius: "var(--nv-radius-full)",
                        boxShadow: activePeriod === key
                          ? "var(--nv-shadow-glow-blue)"
                          : "none",
                        transitionDuration: "var(--nv-duration-normal)",
                        transitionTimingFunction: "var(--nv-ease)",
                      }}
                    >
                      <span className="hidden sm:inline">{label}</span>
                      <span className="sm:hidden">{short}</span>
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

                {/* Mac Guc Skoru -- sadece MS periyodunda ve skip edilmemis maclar */}
                {activePeriod === "ft" && (() => {
                  const ps = computePowerScore(data, patternB, patternC);
                  if (ps <= 0) return null;
                  const gaugeColor = ps >= 70 ? "var(--nv-accent-green)" : ps >= 40 ? "var(--nv-accent-blue)" : "var(--nv-accent-amber)";
                  const trendCount = data.trends
                    ? [data.trends.home_form, data.trends.away_form, data.trends.h2h].filter(Boolean).length
                    : 0;
                  return (
                    <div
                      className="nv-card nv-fade-in"
                      style={{
                        borderRadius: "var(--nv-radius-lg)",
                        padding: "var(--nv-space-lg)",
                      }}
                    >
                      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4">
                        {/* Radial gauge */}
                        <div
                          className="flex-shrink-0 relative flex items-center justify-center"
                          style={{ width: 80, height: 80 }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              inset: 0,
                              borderRadius: "50%",
                              background: `conic-gradient(${gaugeColor} ${ps * 3.6}deg, var(--nv-bg-elevated) ${ps * 3.6}deg 360deg)`,
                            }}
                          />
                          <div
                            className="flex items-center justify-center"
                            style={{
                              position: "absolute",
                              inset: 6,
                              borderRadius: "50%",
                              backgroundColor: "var(--nv-bg-card)",
                            }}
                          >
                            <span
                              style={{
                                fontFamily: "var(--nv-font-mono)",
                                fontSize: "var(--nv-text-xl, 1.25rem)",
                                fontWeight: 700,
                                color: gaugeColor,
                                lineHeight: 1,
                              }}
                            >
                              {ps}
                            </span>
                          </div>
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0 text-center sm:text-left">
                          <h3
                            className="text-sm font-bold"
                            style={{
                              color: "var(--nv-text-primary)",
                              letterSpacing: "var(--nv-tracking-wide)",
                            }}
                          >
                            Maç Güç Skoru
                          </h3>
                          <div className="flex flex-wrap justify-center sm:justify-start gap-2 mt-2">
                            {patternB && patternB.match_count > 0 && (
                              <span
                                className="nv-badge"
                                style={{
                                  backgroundColor: "var(--nv-bg-elevated)",
                                  color: "var(--nv-text-secondary)",
                                  fontSize: "var(--nv-text-xs)",
                                }}
                              >
                                Arşiv 1: {patternB.match_count} maç
                              </span>
                            )}
                            {patternC && patternC.match_count > 0 && (
                              <span
                                className="nv-badge"
                                style={{
                                  backgroundColor: "var(--nv-bg-elevated)",
                                  color: "var(--nv-text-secondary)",
                                  fontSize: "var(--nv-text-xs)",
                                }}
                              >
                                Arşiv 2: {patternC.match_count} maç
                              </span>
                            )}
                            {trendCount > 0 && (
                              <span
                                className="nv-badge"
                                style={{
                                  backgroundColor: "var(--nv-bg-elevated)",
                                  color: "var(--nv-text-secondary)",
                                  fontSize: "var(--nv-text-xs)",
                                }}
                              >
                                Trend: {trendCount}/3
                              </span>
                            )}
                            {patternB && patternC && patternB.match_count >= 5 && patternC.match_count >= 1 && (
                              <span
                                className="nv-badge"
                                style={{
                                  backgroundColor: "var(--nv-accent-green-dim, rgba(34,197,94,0.1))",
                                  color: "var(--nv-accent-green)",
                                  fontSize: "var(--nv-text-xs)",
                                }}
                              >
                                Çift arşiv onayı
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}

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
                        Katman A — 3.5+ Oranı Olan Skorlar
                      </h3>
                      <span
                        className="nv-badge ml-auto"
                        style={{
                          backgroundColor: "var(--nv-bg-elevated)",
                          color: "var(--nv-text-tertiary)",
                        }}
                      >
                        {scores.scores_1.length + scores.scores_x.length + scores.scores_2.length} skor
                      </span>
                    </div>
                    <div className="flex gap-3">
                      <ScoreList scores={scores.scores_1} type="1" label="Ev Kazanır" />
                      <ScoreList scores={scores.scores_x} type="x" label="Berabere" />
                      <ScoreList scores={scores.scores_2} type="2" label="Dep. Kazanır" />
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
                      Bu periyotta 3.5+ oranı olan skor bulunamadı
                    </p>
                  </div>
                )}

                {/* Bos skor listesinde de arsiv eslesmeleri bulunabilir. */}
                <MatchProvider value={{ matchId: data.match_id, homeTeam: data.home_team, awayTeam: data.away_team }}>
                  <IddaaCoupon
                    patternB={patternB}
                    patternC={patternC}
                    period={activePeriod}
                    trends={data.trends}
                    recommendations={data.ft_recommendations}
                  />
                </MatchProvider>
                </div>
                {(evidenceData || validationData) && (
                  <section
                    className="nv-card nv-fade-in text-xs"
                    style={{
                      borderRadius: "var(--nv-radius-lg)",
                      padding: "var(--nv-space-lg)",
                      color: "var(--nv-text-secondary)",
                    }}
                    aria-label="Analiz doğrulama kapsamı"
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--nv-text-primary)" }}>Analiz doğrulama kapsamı</h2>
                    {evidenceData && (<>
                    <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
                      Yalnızca analiz ve arşiv desenleri maçtan önce kaydedilmiş, sonucu bilinen maçlar sayılır.
                    </p>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {[
                        ["Maç öncesi", evidenceData.eligible_matches],
                        ["Arşiv 1", evidenceData.archive_1_evaluated],
                        ["Arşiv 2", evidenceData.archive_2_evaluated],
                      ].map(([label, count]) => (
                        <div
                          key={label}
                          className="nv-card px-2 py-2 text-center"
                          style={{ borderRadius: "var(--nv-radius-md)" }}
                        >
                          <div
                            className="text-lg font-bold"
                            style={{
                              fontFamily: "var(--nv-font-mono)",
                              color: "var(--nv-text-primary)",
                            }}
                          >
                            {count}
                          </div>
                          <div className="text-[10px]" style={{ color: "var(--nv-text-tertiary)" }}>{label}</div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
                      Her arşiv için {evidenceData.minimum_for_rate} sonuçlu maç tamamlanmadan isabet oranı sunulmuyor.
                      Ekrandaki yüzdeler geçmiş eşleşme sıklığıdır.
                    </p>
                    <p className="mt-2 leading-relaxed" style={{ color: "var(--nv-text-secondary)" }}>
                      Maç sonu skor listesi: {evidenceData.score_list_hits}/{evidenceData.score_list_evaluated} maçta
                      gerçek skor seçilen listede bulundu.
                      {evidenceData.score_list_evaluated < evidenceData.minimum_for_rate
                        ? " Örneklem henüz sonuç çıkarmak için küçük."
                        : ` Skor kapsama oranı: %${Math.round(100 * evidenceData.score_list_hits / evidenceData.score_list_evaluated)}. Bu oran bahis getirisi veya olasılık kalibrasyonu değildir.`}
                    </p>
                    <p className="mt-2 leading-relaxed" style={{ color: "var(--nv-accent-amber)" }}>
                      Skor listesinin basit bir yaygın skor seçimini geçtiği henüz gösterilmedi. Bu liste doğrulanmış bahis önerisi değildir.
                    </p>
                    </>)}
                    {validationData && (
                      <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--nv-border)" }}>
                        <h3 className="font-semibold" style={{ color: "var(--nv-text-primary)" }}>İleri dönem seçim takibi</h3>
                        <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
                          Toplam {validationData.total_snapshots} snapshot sabitlendi.
                          Kurallar: {validationData.rule_version} -- Temel: {validationData.baseline_version}.
                        </p>
                        {validationData.markets.length === 0 ? (
                          <p className="mt-2" style={{ color: "var(--nv-text-tertiary)" }}>Henüz pazar verisi yok.</p>
                        ) : (
                          <div className="mt-3 space-y-4">
                            {validationData.markets.map((m) => {
                              const mLabel = { result: "Maç sonucu", over_25: "2.5 Alt/Üst", btts: "Karşılıklı gol" }[m.market];
                              const tierBadge = m.display_tier === "cok_erken"
                                ? <span className="nv-badge nv-badge-amber ml-2">Çok Erken</span>
                                : m.display_tier === "on_bulgu"
                                ? <span className="nv-badge nv-badge-amber ml-2">Ön Bulgu</span>
                                : <span className="nv-badge nv-badge-green ml-2">Tam</span>;
                              const pct = (v: number | null) => v !== null ? `%${(v * 100).toFixed(1)}` : "---";
                              const ci = (lo: number | null, hi: number | null) =>
                                lo !== null && hi !== null ? `(${pct(lo)} -- ${pct(hi)})` : "";
                              return (
                                <div
                                  key={m.market}
                                  className="nv-card"
                                  style={{
                                    borderRadius: "var(--nv-radius-md)",
                                    padding: "var(--nv-space-md)",
                                  }}
                                >
                                  <div className="flex items-center">
                                    <span className="font-semibold" style={{ color: "var(--nv-text-primary)" }}>{mLabel}</span>
                                    {tierBadge}
                                  </div>
                                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--nv-text-secondary)" }}>
                                    <span>Fırsat: {m.opportunities}</span>
                                    <span>Seçim: {m.issued}</span>
                                    <span>Kaçınma: {m.abstained}</span>
                                    <span>Çözülen: {m.resolved_issued}</span>
                                  </div>
                                  {m.display_tier !== "cok_erken" && (
                                    <>
                                      <div className="mt-2 space-y-1" style={{ color: "var(--nv-text-secondary)" }}>
                                        <div>Kapsam: {pct(m.coverage)} {ci(m.coverage_ci_low, m.coverage_ci_high)}</div>
                                        <div>Model isabet: {pct(m.model_hit_rate)} {ci(m.model_hit_rate_ci_low, m.model_hit_rate_ci_high)}</div>
                                        <div>Temel isabet: {pct(m.baseline_hit_rate)} {ci(m.baseline_hit_rate_ci_low, m.baseline_hit_rate_ci_high)}</div>
                                        {m.paired_difference !== null && (
                                          <div>Fark: {(m.paired_difference * 100).toFixed(1)} puan</div>
                                        )}
                                      </div>
                                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
                                        <span>İkisi de ok: {m.both_hit}</span>
                                        <span>Sadece model: {m.model_only}</span>
                                        <span>Sadece temel: {m.baseline_only}</span>
                                        <span>İkisi de x: {m.neither}</span>
                                      </div>
                                    </>
                                  )}
                                  {m.display_tier === "tam" && (
                                    <div className="mt-2 space-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
                                      <div>Yayımlanan sıklık ort.: %{m.avg_published_frequency?.toFixed(1) ?? "---"}</div>
                                      <div>Gözlenen isabet: %{m.observed_hit_rate?.toFixed(1) ?? "---"}</div>
                                      <div>Kalibrasyon farkı: {m.calibration_gap?.toFixed(1) ?? "---"} puan</div>
                                      <div>Brier (seçilen olay): {m.selected_event_brier?.toFixed(4) ?? "---"}</div>
                                    </div>
                                  )}
                                  {m.display_tier === "cok_erken" && (
                                    <p className="mt-2" style={{ color: "var(--nv-accent-amber)", opacity: 0.8 }}>Sonuç çıkarmak için çok erken.</p>
                                  )}
                                  {m.display_tier === "on_bulgu" && (
                                    <p className="mt-2" style={{ color: "var(--nv-accent-amber)", opacity: 0.8 }}>Ön bulgu — sonuçlar değişebilir.</p>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        <div className="mt-3 space-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
                          <p>Arşiv yüzdesi kalibre olasılık değildir.</p>
                          <p>Oran verisi olmadan ROI veya karlılık ölçülemez.</p>
                          {validationData.markets.some((m) => m.display_tier === "tam" && m.market === "result") && (
                            <p>{validationData.brier_note}</p>
                          )}
                        </div>
                      </div>
                    )}
                  </section>
                )}
                {scoreValidation && (
                  <section
                    className="nv-card nv-fade-in text-xs"
                    style={{
                      borderRadius: "var(--nv-radius-lg)",
                      padding: "var(--nv-space-lg)",
                      color: "var(--nv-text-secondary)",
                    }}
                    aria-label="İleri dönem skor karşılaştırması"
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--nv-text-primary)" }}>İleri dönem skor karşılaştırması</h2>
                    <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
                      Maç öncesi {scoreValidation.recorded} skor listesi sabitlendi; {scoreValidation.resolved} maçın kesin sonucu doğrulandı.
                      {" "}{scoreValidation.paired} maçta aynı uzunlukta geçmişte en sık görülen skor listesiyle karşılaştırma yapılabildi.
                    </p>
                    {scoreValidation.paired > 0 && (
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1" style={{ color: "var(--nv-text-primary)" }}>
                        <span>Analiz listesi: {scoreValidation.paired_model_hits}/{scoreValidation.paired}</span>
                        <span>Basit liste: {scoreValidation.baseline_hits}/{scoreValidation.paired}</span>
                        <span>İkisi de: {scoreValidation.both_hit}</span>
                        <span>Sadece analiz: {scoreValidation.model_only}</span>
                        <span>Sadece basit: {scoreValidation.baseline_only}</span>
                        <span>İkisi de değil: {scoreValidation.neither}</span>
                      </div>
                    )}
                    <p className="mt-2" style={{ color: "var(--nv-text-tertiary)" }}>
                      {scoreValidation.paired < scoreValidation.minimum_for_rate
                        ? `${scoreValidation.minimum_for_rate} eşleşmiş sonuçtan önce oran gösterilmez.`
                        : `Analiz listesi %${Math.round(100 * scoreValidation.paired_model_hits / scoreValidation.paired)}, basit liste %${Math.round(100 * scoreValidation.baseline_hits / scoreValidation.paired)} kapsam sağladı. Fark %95 aralığı: ${scoreValidation.difference_ci_low_pp} ile ${scoreValidation.difference_ci_high_pp} puan.`}
                      {" "}Skor kapsamı bahis getirisi veya olasılık kalibrasyonu değildir.
                    </p>
                  </section>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
