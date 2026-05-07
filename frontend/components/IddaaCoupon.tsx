import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import TopPicks from "./TopPicks";
import MarketSummary from "./MarketSummary";
import DetailedStats from "./DetailedStats";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

export default function IddaaCoupon({ patternB, patternC, period }: Props) {
  const hasB = patternB !== null && patternB.match_count >= 5;
  const hasC = patternC !== null && patternC.match_count >= 5;

  if (!hasB && !hasC) {
    return (
      <div
        className="rounded-xl p-8 border text-center"
        style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
      >
        <div className="text-3xl mb-3">📊</div>
        <p className="text-sm font-medium" style={{ color: "#64748b" }}>
          Bu periyot için yeterli arşiv verisi bulunamadı.
        </p>
        <p className="text-xs mt-1" style={{ color: "#374151" }}>
          Minimum 5 eşleşme gerekiyor
        </p>
      </div>
    );
  }

  const safeB = hasB ? patternB : null;
  const safeC = hasC ? patternC : null;

  return (
    <div className="space-y-4">
      {/* Katman 1: Önerilen Bahisler (her zaman üstte, varsayılan görünür) */}
      <TopPicks patternB={safeB} patternC={safeC} period={period} />

      {/* Katman 2: Ana Pazar Özeti (varsayılan görünür) */}
      <MarketSummary patternB={safeB} patternC={safeC} period={period} />

      {/* Katman 3: Detaylı Analiz (varsayılan kapalı, collapsible) */}
      <DetailedStats patternB={safeB} patternC={safeC} period={period} />
    </div>
  );
}
