"use client";

import type { FTRecommendation } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { useMatchInfo } from "@/lib/match-context";
import AddToCartButton from "./AddToCartButton";

interface Props {
  recommendations: FTRecommendation[];
  period: Period;
}

const MARKET_LABELS: Record<FTRecommendation["market"], string> = {
  result: "Maç Sonucu",
  over_25: "2.5 Alt/Üst",
  btts: "Karşılıklı Gol",
};

const SELECTION_LABELS: Record<FTRecommendation["selection"], string> = {
  "1": "Ev Sahibi", X: "Beraberlik", "2": "Deplasman",
  under: "2.5 Alt", over: "2.5 Üst", yes: "Var", no: "Yok",
};

const ARCHIVE_LABELS: Record<FTRecommendation["archive"], string> = {
  archive_1: "Arşiv 1", archive_2: "Arşiv 2", both: "1+2",
};

function pctColor(pct: number) {
  if (pct >= 80) return "var(--nv-accent-green)";
  if (pct >= 65) return "var(--nv-accent-blue)";
  if (pct >= 50) return "var(--nv-text-secondary)";
  return "var(--nv-text-tertiary)";
}

function pctBarBg(pct: number) {
  if (pct >= 80) return "var(--nv-accent-green)";
  if (pct >= 65) return "var(--nv-accent-blue)";
  if (pct >= 50) return "var(--nv-text-secondary)";
  return "var(--nv-text-tertiary)";
}

function archiveBadgeClass(archive: FTRecommendation["archive"]) {
  if (archive === "both") return "nv-badge nv-badge-purple";
  if (archive === "archive_1") return "nv-badge nv-badge-blue";
  return "nv-badge nv-badge-amber";
}

function RecommendationRow({ recommendation }: { recommendation: FTRecommendation }) {
  const match = useMatchInfo();
  const pct = Math.round(recommendation.frequency_pct);
  const color = pctColor(pct);
  const archive = recommendation.archive === "archive_1" ? "A"
    : recommendation.archive === "archive_2" ? "B" : "AB";

  return (
    <div
      className="nv-card-interactive flex items-center gap-3"
      style={{
        padding: "var(--nv-space-md)",
        borderRadius: "var(--nv-radius-md)",
      }}
    >
      {/* Confidence ring */}
      <div
        className="nv-conf-ring flex-shrink-0"
        style={{
          "--size": "40px",
          "--stroke": "4px",
          "--pct": pct,
          "--ring-color": color,
        } as React.CSSProperties}
      >
        <span
          className="absolute text-[10px] font-bold"
          style={{
            fontFamily: "var(--nv-font-mono)",
            color: color,
          }}
        >
          {pct}
        </span>
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={archiveBadgeClass(recommendation.archive)}>
            {ARCHIVE_LABELS[recommendation.archive]}
          </span>
          <span
            className="text-[10px] uppercase"
            style={{
              color: "var(--nv-text-tertiary)",
              letterSpacing: "var(--nv-tracking-wide)",
            }}
          >
            {MARKET_LABELS[recommendation.market]}
          </span>
        </div>
        <div
          className="text-sm font-semibold"
          style={{ color: "var(--nv-text-primary)" }}
        >
          {SELECTION_LABELS[recommendation.selection]}
        </div>
        {/* Percentage bar */}
        <div className="nv-pct-bar mt-1.5" style={{ height: "4px" }}>
          <div
            className="nv-pct-bar-fill"
            style={{
              width: `${pct}%`,
              backgroundColor: pctBarBg(pct),
            }}
          />
        </div>
      </div>

      {/* Right side: pct + count + cart */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="text-right">
          <div
            className="text-base font-extrabold leading-none"
            style={{
              fontFamily: "var(--nv-font-mono)",
              color: color,
            }}
          >
            %{pct}
          </div>
          <div
            className="mt-0.5 text-[9px]"
            style={{
              fontFamily: "var(--nv-font-mono)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            {recommendation.match_count} maç
          </div>
        </div>
        {match && <AddToCartButton item={{
          matchId: match.matchId, homeTeam: match.homeTeam, awayTeam: match.awayTeam,
          marketKey: recommendation.market, marketLabel: MARKET_LABELS[recommendation.market],
          selectionLabel: SELECTION_LABELS[recommendation.selection], pct: recommendation.frequency_pct,
          archive, period: "ft",
        }} />}
      </div>
    </div>
  );
}

export default function TopPicks({ recommendations, period }: Props) {
  if (period !== "ft") return null;
  if (recommendations.length === 0) {
    return (
      <div
        className="nv-card nv-fade-in"
        style={{
          borderRadius: "var(--nv-radius-lg)",
          padding: "var(--nv-space-lg)",
        }}
      >
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-secondary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          İleri dönem deneysel seçimler
        </h3>
        <p
          className="mt-1 text-xs leading-relaxed"
          style={{ color: "var(--nv-text-tertiary)" }}
        >
          Bu maç için ft-display-v3 kuralıyla maç öncesi kaydedilmiş seçim bulunmuyor.
          Ayrıntılı arşiv istatistikleri aşağıda bilgi amacıyla gösteriliyor.
        </p>
      </div>
    );
  }
  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", padding: "var(--nv-space-lg)" }}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-primary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          İleri dönem deneysel seçimler
        </h3>
        <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
          ft-display-v3 · {recommendations.length} seçim
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {recommendations.map((recommendation) => (
          <RecommendationRow key={recommendation.recommendation_id} recommendation={recommendation} />
        ))}
      </div>
      <p
        className="text-[10px] leading-relaxed mt-3"
        style={{ color: "var(--nv-text-tertiary)" }}
      >
        Seçimler maç başlamadan sabitlenir ve aynı kayıt sonuçlandıktan sonra ölçülür.
        Yüzde, benzer geçmiş maçlardaki görülme sıklığıdır; kalibre edilmiş olasılık veya getiri tahmini değildir.
      </p>
    </div>
  );
}
