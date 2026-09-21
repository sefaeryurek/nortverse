import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import AnalyzeClient from "@/app/analyze/[match_id]/AnalyzeClient";
import { getAnalysisEvidence } from "@/lib/api";
import { makePatternResult } from "./fixtures";
import type { AnalysisEvidence, AnalyzeResponse, PatternResult } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ back: vi.fn() }) }));
vi.mock("@/lib/api", () => ({ analyzeMatch: vi.fn(), getAnalysisEvidence: vi.fn() }));
vi.mock("next/dynamic", () => ({
  default: () => ({ patternB, patternC }: { patternB?: PatternResult | null; patternC?: PatternResult | null }) => (
    <div data-testid="archive-analysis">{patternB?.match_count ?? "none"}/{patternC?.match_count ?? "none"}</div>
  ),
}));

beforeEach(() => { vi.mocked(getAnalysisEvidence).mockRejectedValue(new Error("offline")); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

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

    render(<AnalyzeClient match_id="3003889" initialData={data}
      evidence={{ eligible_matches: 48, archive_1_evaluated: 5, archive_2_evaluated: 0, minimum_for_rate: 100 }}
      initialError="" urlHome="" urlAway="" />);

    expect(screen.getByText("Bu periyotta 3.5+ oranı olan skor bulunamadı")).toBeDefined();
    expect(screen.getByTestId("archive-analysis").textContent).toBe("none/12");
    const panel = within(screen.getByLabelText("Analiz doğrulama kapsamı"));
    expect(panel.getByText("48")).toBeDefined();
    expect(panel.getByText("5")).toBeDefined();
    expect(panel.getByText("0")).toBeDefined();
  });

  it("shows Archive 1 matches for an empty score shortlist", () => {
    const data: AnalyzeResponse = {
      match_id: "3013703", home_team: "Home", away_team: "Away",
      league_code: "SPA D1", season: "2026/2027",
      ht: emptyPeriod, half2: emptyPeriod, ft: emptyPeriod,
      ht_b: null, ht_c: null, h2_b: null, h2_c: null,
      ft_b: makePatternResult({ match_count: 7 }), ft_c: null,
      trends: null, skipped: false, skip_reason: null,
    };

    render(<AnalyzeClient match_id="3013703" initialData={data} initialError="" urlHome="" urlAway="" />);

    expect(screen.getByText("Bu periyotta 3.5+ oranı olan skor bulunamadı")).toBeDefined();
    expect(screen.getByTestId("archive-analysis").textContent).toBe("7/none");
  });

  it("shows the analysis before optional coverage data resolves", async () => {
    const data: AnalyzeResponse = {
      match_id: "3013703", home_team: "Home", away_team: "Away",
      league_code: "SPA D1", season: "2026/2027",
      ht: emptyPeriod, half2: emptyPeriod, ft: emptyPeriod,
      ht_b: null, ht_c: null, h2_b: null, h2_c: null,
      ft_b: makePatternResult({ match_count: 7 }), ft_c: null,
      trends: null, skipped: false, skip_reason: null,
    };
    let resolveEvidence!: (value: AnalysisEvidence) => void;
    vi.mocked(getAnalysisEvidence).mockReturnValue(new Promise((resolve) => { resolveEvidence = resolve; }));

    render(<AnalyzeClient match_id="3013703" initialData={data} initialError="" urlHome="" urlAway="" />);
    expect(screen.getByTestId("archive-analysis").textContent).toBe("7/none");
    expect(screen.queryByLabelText("Analiz doğrulama kapsamı")).toBeNull();

    resolveEvidence({ eligible_matches: 48, archive_1_evaluated: 5, archive_2_evaluated: 0, minimum_for_rate: 100 });
    expect(await screen.findByLabelText("Analiz doğrulama kapsamı")).toBeDefined();
  });
});
