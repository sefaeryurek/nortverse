"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { AnalyzeResponse } from "@/lib/types";
import { analyzeMatch } from "@/lib/api";
import IddaaCoupon from "@/components/IddaaCoupon";

type Period = "ht" | "h2" | "ft";

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

export default function AnalyzePage() {
  const { match_id } = useParams<{ match_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activePeriod, setActivePeriod] = useState<Period>("ft");

  useEffect(() => {
    analyzeMatch(match_id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [match_id]);

  const { b: patternB, c: patternC } = data
    ? patternFor(data, activePeriod)
    : { b: null, c: null };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-5 py-4 border-b flex items-center gap-3 flex-shrink-0"
        style={{ borderColor: "#1e293b" }}
      >
        <button
          onClick={() => router.back()}
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors flex-shrink-0"
          style={{ backgroundColor: "#1e293b", color: "#64748b" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#334155";
            e.currentTarget.style.color = "#e2e8f0";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "#1e293b";
            e.currentTarget.style.color = "#64748b";
          }}
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
                  Bu maç filtreleme kuralına takıldı
                </p>
                <p className="text-xs mt-1" style={{ color: "#78716c" }}>
                  {data.skip_reason}
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
                      onClick={() => setActivePeriod(key)}
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

                {/* Kupon */}
                <IddaaCoupon
                  patternB={patternB}
                  patternC={patternC}
                  period={activePeriod}
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
