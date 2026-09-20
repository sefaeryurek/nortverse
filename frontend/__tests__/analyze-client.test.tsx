import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import AnalyzeClient from "@/app/analyze/[match_id]/AnalyzeClient";
import { makePatternResult } from "./fixtures";
import type { AnalyzeResponse, PatternResult } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ back: vi.fn() }) }));
vi.mock("next/dynamic", () => ({
  default: () => ({ patternC }: { patternC?: PatternResult | null }) => (
    <div data-testid="archive-analysis">{patternC?.match_count ?? "none"}</div>
  ),
}));

afterEach(cleanup);

const emptyPeriod = { scores_1: [], scores_x: [], scores_2: [] };

describe("AnalyzeClient", () => {
  it("shows independent archive analysis when the 3.5+ score list is empty", () => {
    const data: AnalyzeResponse = {
      match_id: "3003889", home_team: "Home", away_team: "Away",
      league_code: "ENG PR", season: "2026/2027",
      ht: emptyPeriod, half2: emptyPeriod, ft: emptyPeriod,
      ht_b: null, ht_c: null, h2_b: null, h2_c: null,
      ft_b: null, ft_c: makePatternResult({ match_count: 12, result_1_pct: 75 }),
      trends: null, skipped: false, skip_reason: null,
    };

    render(<AnalyzeClient match_id="3003889" initialData={data} initialError="" urlHome="" urlAway="" />);

    expect(screen.getByText("Bu periyotta 3.5+ oranı olan skor bulunamadı")).toBeDefined();
    expect(screen.getByTestId("archive-analysis").textContent).toBe("12");
  });
});
