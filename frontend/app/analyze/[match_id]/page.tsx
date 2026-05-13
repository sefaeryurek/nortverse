"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import type { AnalyzeResponse } from "@/lib/types";
import { analyzeMatch } from "@/lib/api";
import IddaaCoupon from "@/components/IddaaCoupon";
import ScoreList from "@/components/ScoreList";
import TrendsPanel from "@/components/TrendsPanel";
import { MatchProvider } from "@/lib/match-context";

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

export default function AnalyzePage() {
  const { match_id } = useParams<{ match_id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlHome = searchParams.get("home") ?? "";
  const urlAway = searchParams.get("away") ?? "";
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activePeriod, setActivePeriod] = useState<Period>("ft");
  const [isPending, startTransition] = useTransition();

  const changePeriod = (key: Period) => {
    if (key === activePeriod) return;
    startTransition(() => setActivePeriod(key));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    analyzeMatch(match_id)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [match_id]);

  const { b: patternB, c: patternC } = data
    ? patternFor(data, activePeriod)
    : { b: null, c: null };
  const scores = data ? scoresFor(data, activePeriod) : null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-5 py-4 border-b flex items-center gap-3 flex-shrink-0"
        style={{ borderColor: "#1e293b" }}
      >
        <button
          onClick={() => router.back()}
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors flex-shrink-0 bg-slate-800 text-slate-500 hover:bg-slate-700 hover:text-slate-200"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <div className="flex-1 min-w-0">
          {data ? (
            <>
              <h1 className="text-base font-bold truncate" style={{ color: "#e2e8f0" }}>
                {data.home_team}
                <span className="mx-2" style={{ color: "#475569" }}>vs</span>
                {data.away_team}
              </h1>
              <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                {data.league_code} · {data.season}
              </p>
            </>
          ) : urlHome && urlAway ? (
            <h1 className="text-base font-bold truncate" style={{ color: "#e2e8f0" }}>
              {urlHome}
              <span className="mx-2" style={{ color: "#475569" }}>vs</span>
              {urlAway}
            </h1>
          ) : (
            <h1 className="text-base font-bold" style={{ color: "#e2e8f0" }}>
              Maç #{match_id}
            </h1>
          )}
        </div>
      </div>

      {/* İçerik */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center py-32">
            <div
              className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin mb-5"
              style={{ borderColor: "#3b82f6", borderTopColor: "transparent" }}
            />
            <p className="text-sm font-medium" style={{ color: "#e2e8f0" }}>
              Analiz yükleniyor...
            </p>
            <p className="text-xs mt-1" style={{ color: "#64748b" }}>
              İlk açılışta ~15 saniye sürebilir
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="p-6">
            <div
              className="rounded-xl p-6 border text-center"
              style={{ backgroundColor: "#1c0816", borderColor: "#7f1d1d" }}
            >
              <div className="text-3xl mb-3">⚠️</div>
              <p className="text-sm font-medium" style={{ color: "#f87171" }}>{error}</p>
            </div>
          </div>
        )}

        {data && !loading && (
          <div className="p-4 space-y-4">
            {/* Kural dışı */}
            {data.skipped && (
              <div
                className="rounded-xl p-5 border"
                style={{ backgroundColor: "#1c1109", borderColor: "#92400e" }}
              >
                <p className="text-sm font-semibold" style={{ color: "#fcd34d" }}>
                  Bu maç için tahmin üretilemedi
                </p>
                <p className="text-xs mt-1" style={{ color: "#78716c" }}>
                  {(data.skip_reason && SKIP_REASON_LABELS[data.skip_reason]) ?? data.skip_reason}
                </p>
              </div>
            )}

            {!data.skipped && (
              <>
                {/* Periyot sekmeleri */}
                <div className="flex gap-2">
                  {PERIODS.map(({ key, label, short }) => (
                    <button
                      key={key}
                      onClick={() => changePeriod(key)}
                      className="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
                      style={{
                        backgroundColor: activePeriod === key ? "#1d4ed8" : "#1e293b",
                        color: activePeriod === key ? "#fff" : "#94a3b8",
                        border: `1px solid ${activePeriod === key ? "#2563eb" : "#2d3748"}`,
                        boxShadow: activePeriod === key
                          ? "0 0 12px rgba(37,99,235,0.4)"
                          : "none",
                      }}
                    >
                      <span className="hidden sm:inline">{label}</span>
                      <span className="sm:hidden">{short}</span>
                    </button>
                  ))}
                </div>

                {/* Periyot içeriği — pending iken hafif soluk (kullanıcı geçiş hissini alır) */}
                <div
                  className="space-y-4 transition-opacity duration-150"
                  style={{ opacity: isPending ? 0.6 : 1 }}
                >

                {/* Form & H2H trendleri — sadece MS periyodunda anlamlı */}
                {activePeriod === "ft" && data.trends && (
                  <TrendsPanel
                    trends={data.trends}
                    homeTeam={data.home_team}
                    awayTeam={data.away_team}
                  />
                )}

                {/* Katman A — 3.5+ skor dağılımı */}
                {scores && (scores.scores_1.length > 0 || scores.scores_x.length > 0 || scores.scores_2.length > 0) && (
                  <div
                    className="rounded-xl p-4 border space-y-3"
                    style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#38bdf8" }} />
                      <h3 className="text-sm font-bold tracking-wide" style={{ color: "#38bdf8" }}>
                        Katman A — 3.5+ Oranı Olan Skorlar
                      </h3>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-mono ml-auto"
                        style={{ backgroundColor: "#1e293b", color: "#64748b" }}
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

                {/* Arşiv İstatistikleri */}
                {scores && (scores.scores_1.length > 0 || scores.scores_x.length > 0 || scores.scores_2.length > 0) ? (
                  <MatchProvider value={{ matchId: data.match_id, homeTeam: data.home_team, awayTeam: data.away_team }}>
                    <IddaaCoupon
                      patternB={patternB}
                      patternC={patternC}
                      period={activePeriod}
                      trends={data.trends}
                    />
                  </MatchProvider>
                ) : (
                  <div
                    className="rounded-xl p-5 border text-center"
                    style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
                  >
                    <p className="text-sm font-medium" style={{ color: "#475569" }}>
                      Bu periyotta 3.5+ oranı olan skor bulunamadı
                    </p>
                    <p className="text-xs mt-1" style={{ color: "#334155" }}>
                      Tahmin üretmek için en az 1 skor gerekiyor
                    </p>
                  </div>
                )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
