"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { AnalyzeResponse } from "@/lib/types";
import { analyzeMatch } from "@/lib/api";
import IddaaCoupon from "@/components/IddaaCoupon";

const PERIODS = [
  { key: "ht", label: "İlk Yarı (İY)" },
  { key: "half2", label: "İkinci Yarı (2Y)" },
  { key: "ft", label: "Maç Sonu (MS)" },
] as const;

export default function AnalyzePage() {
  const { match_id } = useParams<{ match_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activePeriod, setActivePeriod] = useState<"ht" | "half2" | "ft">("ft");

  useEffect(() => {
    analyzeMatch(match_id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [match_id]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-6 py-4 border-b flex items-center gap-3"
        style={{ borderColor: "#2d3748" }}
      >
        <button
          onClick={() => router.back()}
          className="text-sm px-2 py-1 rounded transition-colors"
          style={{ color: "#64748b" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
        >
          ← Geri
        </button>
        <div className="flex-1">
          {data ? (
            <div>
              <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
                {data.home_team} <span style={{ color: "#475569" }}>vs</span>{" "}
                {data.away_team}
              </h1>
              <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>
                {data.league_code} · {data.season}
              </p>
            </div>
          ) : (
            <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
              Maç #{match_id}
            </h1>
          )}
        </div>
      </div>

      {/* İçerik */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-24">
            <div
              className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin mb-4"
              style={{ borderColor: "#3b82f6", borderTopColor: "transparent" }}
            />
            <p className="text-sm font-medium" style={{ color: "#e2e8f0" }}>
              Analiz ediliyor...
            </p>
            <p className="text-xs mt-1" style={{ color: "#64748b" }}>
              Veri çekiliyor, yaklaşık 15 saniye
            </p>
          </div>
        )}

        {error && (
          <div
            className="rounded-lg p-5 border text-center"
            style={{ backgroundColor: "#1c0816", borderColor: "#7f1d1d" }}
          >
            <div className="text-3xl mb-2">⚠️</div>
            <p className="text-sm font-medium" style={{ color: "#f87171" }}>
              {error}
            </p>
          </div>
        )}

        {data && !loading && (
          <div className="space-y-4">
            {/* Kural dışı */}
            {data.skipped && (
              <div
                className="rounded-lg p-4 border"
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
                  {PERIODS.map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setActivePeriod(key)}
                      className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
                      style={{
                        backgroundColor:
                          activePeriod === key ? "#1d4ed8" : "#1c2333",
                        color: activePeriod === key ? "#fff" : "#94a3b8",
                        border: `1px solid ${activePeriod === key ? "#2563eb" : "#2d3748"}`,
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {/* Aktif periyot içeriği */}
                {activePeriod === "ht" && (
                  <IddaaCoupon
                    period={data.ht}
                    patternB={data.pattern_b}
                    patternC={data.pattern_c}
                    label="İlk Yarı (İY)"
                  />
                )}
                {activePeriod === "half2" && (
                  <IddaaCoupon
                    period={data.half2}
                    patternB={data.pattern_b}
                    patternC={data.pattern_c}
                    label="İkinci Yarı (2Y)"
                  />
                )}
                {activePeriod === "ft" && (
                  <IddaaCoupon
                    period={data.ft}
                    patternB={data.pattern_b}
                    patternC={data.pattern_c}
                    label="Maç Sonu (MS)"
                  />
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
