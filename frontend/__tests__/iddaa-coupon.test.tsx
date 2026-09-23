import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import IddaaCoupon from "@/components/IddaaCoupon";
import type { FTRecommendation } from "@/lib/types";

afterEach(cleanup);

const recommendation: FTRecommendation = {
  recommendation_id: "ft-display-v2:result:1", archive: "archive_1",
  market: "result", selection: "1", frequency_pct: 70, match_count: 30,
  archive_1_frequency_pct: 70, archive_1_match_count: 30,
  archive_2_frequency_pct: null, archive_2_match_count: null,
};

describe("IddaaCoupon", () => {
  it("shows a frozen recommendation even when current patterns are empty", () => {
    render(<IddaaCoupon patternB={null} patternC={null} period="ft" recommendations={[recommendation]} />);
    expect(screen.getByText("Ev Sahibi")).toBeDefined();
    expect(screen.getByText(/yeterli arşiv verisi bulunamadı/)).toBeDefined();
  });

  it("explains an empty frozen recommendation set independently of patterns", () => {
    render(<IddaaCoupon patternB={null} patternC={null} period="ft" recommendations={[]} />);
    expect(screen.getByText(/kaydedilmiş seçim bulunmuyor/)).toBeDefined();
  });
});
