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

function RecommendationRow({ recommendation }: { recommendation: FTRecommendation }) {
  const match = useMatchInfo();
  const archive = recommendation.archive === "archive_1" ? "A"
    : recommendation.archive === "archive_2" ? "B" : "AB";
  return (
    <div className="flex items-center gap-2 rounded-lg border border-emerald-900 bg-emerald-950/40 px-3 py-2">
      <span className="min-w-12 rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-center font-mono text-[9px] font-bold text-slate-300">
        {ARCHIVE_LABELS[recommendation.archive]}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[10px] uppercase tracking-wider text-slate-500">{MARKET_LABELS[recommendation.market]}</div>
        <div className="truncate text-sm font-semibold text-emerald-100">{SELECTION_LABELS[recommendation.selection]}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-base font-extrabold leading-none text-emerald-100">%{Math.round(recommendation.frequency_pct)}</div>
        <div className="mt-0.5 font-mono text-[9px] text-slate-500">{recommendation.match_count} maç</div>
      </div>
      {match && <AddToCartButton item={{
        matchId: match.matchId, homeTeam: match.homeTeam, awayTeam: match.awayTeam,
        marketKey: recommendation.market, marketLabel: MARKET_LABELS[recommendation.market],
        selectionLabel: SELECTION_LABELS[recommendation.selection], pct: recommendation.frequency_pct,
        archive, period: "ft",
      }} />}
    </div>
  );
}

export default function TopPicks({ recommendations, period }: Props) {
  if (period !== "ft") return null;
  if (recommendations.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-bold tracking-wide text-slate-300">İleri dönem deneysel seçimler</h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          Bu maç için ft-display-v2 kuralıyla maç öncesi kaydedilmiş seçim bulunmuyor.
          Ayrıntılı arşiv istatistikleri aşağıda bilgi amacıyla gösteriliyor.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-3 rounded-xl border border-emerald-800 bg-emerald-950/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-bold tracking-wide text-emerald-200">İleri dönem deneysel seçimler</h3>
        <span className="font-mono text-[10px] text-slate-500">ft-display-v2 · {recommendations.length} seçim</span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {recommendations.map((recommendation) => <RecommendationRow key={recommendation.recommendation_id} recommendation={recommendation} />)}
      </div>
      <p className="text-[10px] leading-relaxed text-slate-500">
        Seçimler maç başlamadan sabitlenir ve aynı kayıt sonuçlandıktan sonra ölçülür.
        Yüzde, benzer geçmiş maçlardaki görülme sıklığıdır; kalibre edilmiş olasılık veya getiri tahmini değildir.
      </p>
    </div>
  );
}
