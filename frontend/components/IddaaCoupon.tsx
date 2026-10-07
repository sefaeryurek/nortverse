import type { FTRecommendation, PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import TopPicks from "./TopPicks";
import MarketSummary from "./MarketSummary";
import DetailedStats from "./DetailedStats";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  patternD: PatternResult | null;
  period: Period;
  recommendations: FTRecommendation[];
}

export default function IddaaCoupon({ patternB, patternC, patternD, period, recommendations }: Props) {
  const hasB = patternB !== null && patternB.match_count >= 5;
  const hasC = patternC !== null && patternC.match_count >= 1;
  const hasD = patternD !== null && patternD.match_count >= 1;
  const recommendationPanel = <TopPicks recommendations={recommendations} period={period} />;

  if (!hasB && !hasC && !hasD) {
    return (
      <div className="space-y-4">
        {recommendationPanel}
        <div
          className="nv-card text-center"
          style={{
            borderRadius: "var(--nv-radius-lg)",
            padding: "var(--nv-space-2xl)",
          }}
        >
          <p
            className="text-sm font-medium"
            style={{ color: "var(--nv-text-secondary)" }}
          >
            Bu periyot için yeterli arşiv verisi bulunamadı.
          </p>
          <p
            className="text-xs mt-1"
            style={{ color: "var(--nv-text-tertiary)" }}
          >
            Arşiv 1 için en az 5, Arşiv 2/3 için en az 1 eşleşme gerekiyor
          </p>
        </div>
      </div>
    );
  }

  const safeB = hasB ? patternB : null;
  const safeC = hasC ? patternC : null;
  const safeD = hasD ? patternD : null;

  return (
    <div className="space-y-4">
      {/* Katman 1: Onerilen Bahisler (her zaman ustte, varsayilan gorunur) */}
      {recommendationPanel}

      {/* Katman 2: Ana Pazar Ozeti (varsayilan gorunur) */}
      <MarketSummary patternB={safeB} patternC={safeC} patternD={safeD} period={period} />

      {/* Katman 3: Detayli Analiz (varsayilan kapali, collapsible) */}
      <DetailedStats patternB={safeB} patternC={safeC} patternD={safeD} period={period} />
    </div>
  );
}
