import type { FTRecommendation, PatternResult, TrendsData } from "@/lib/types";
import type { Period } from "@/lib/labels";
import TopPicks from "./TopPicks";
import MarketSummary from "./MarketSummary";
import DetailedStats from "./DetailedStats";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
  trends?: TrendsData | null;
  recommendations: FTRecommendation[];
}

export default function IddaaCoupon({ patternB, patternC, period, recommendations }: Props) {
  // Sprint 8.9: Pattern B (skor seti) icin 5+ eslesme sart, Pattern C (oran benzerligi)
  // tolerance=0.0 ile siki arandigindan 1+ yeterli -- dusuk guven UI'da rozetle belirtilir.
  const hasB = patternB !== null && patternB.match_count >= 5;
  const hasC = patternC !== null && patternC.match_count >= 1;
  const recommendationPanel = <TopPicks recommendations={recommendations} period={period} />;

  if (!hasB && !hasC) {
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
            Arşiv 1 için en az 5, Arşiv 2 için en az 1 eşleşme gerekiyor
          </p>
        </div>
      </div>
    );
  }

  const safeB = hasB ? patternB : null;
  const safeC = hasC ? patternC : null;

  return (
    <div className="space-y-4">
      {/* Katman 1: Onerilen Bahisler (her zaman ustte, varsayilan gorunur) */}
      {recommendationPanel}

      {/* Katman 1b: Akilli Kombinasyon Kuponlari (Top Picks'ten otomatik uretilir) */}
      {/* Katman 2: Ana Pazar Ozeti (varsayilan gorunur) */}
      <MarketSummary patternB={safeB} patternC={safeC} period={period} />

      {/* Katman 3: Detayli Analiz (varsayilan kapali, collapsible) */}
      <DetailedStats patternB={safeB} patternC={safeC} period={period} />
    </div>
  );
}
