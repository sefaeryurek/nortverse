import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import PowerScoreGauge, { computePowerScore } from "@/components/PowerScoreGauge";

afterEach(cleanup);
import { makePatternResult } from "./fixtures";
import type { AnalyzeResponse } from "@/lib/types";

function makeAnalyzeResponse(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    match_id: "123",
    home_team: "Team A",
    away_team: "Team B",
    league_code: "TEST",
    season: "2025-2026",
    ht: { scores_1: [], scores_x: [], scores_2: [] },
    half2: { scores_1: [], scores_x: [], scores_2: [] },
    ft: { scores_1: ["1-0"], scores_x: [], scores_2: [] },
    ht_b: null,
    ht_c: null,
    h2_b: null,
    h2_c: null,
    ft_b: null,
    ft_c: null,
    trends: null,
    skipped: false,
    skip_reason: null,
    recommendation_rule_version: "ft-display-v3",
    ft_recommendations: [],
    ...overrides,
  } as AnalyzeResponse;
}

describe("computePowerScore", () => {
  it("returns 0 when no pattern data", () => {
    const data = makeAnalyzeResponse();
    expect(computePowerScore(data, null, null)).toBe(0);
  });

  it("gives points for pattern B match count", () => {
    const data = makeAnalyzeResponse();
    const b = makePatternResult({ match_count: 20, result_1_pct: 50 });
    const score = computePowerScore(data, b, null);
    expect(score).toBeGreaterThan(0);
  });

  it("gives extra points for pattern C", () => {
    const data = makeAnalyzeResponse();
    const b = makePatternResult({ match_count: 20, result_1_pct: 50 });
    const c = makePatternResult({ match_count: 5, result_1_pct: 60 });
    const scoreWithC = computePowerScore(data, b, c);
    const scoreWithoutC = computePowerScore(data, b, null);
    expect(scoreWithC).toBeGreaterThan(scoreWithoutC);
  });

  it("gives points for trends", () => {
    const data = makeAnalyzeResponse({
      trends: {
        home_form: { label: "Ev", sample_size: 5, win_pct: 60, draw_pct: 20, loss_pct: 20, kg_var_pct: 50, over_25_pct: 50, avg_goals_for: 1.5, avg_goals_against: 1.0, last_n_results: ["G"] },
        away_form: null,
        h2h: null,
      },
    });
    const b = makePatternResult({ match_count: 10, result_1_pct: 50 });
    const withTrends = computePowerScore(data, b, null);
    const dataNoTrends = makeAnalyzeResponse();
    const withoutTrends = computePowerScore(dataNoTrends, b, null);
    expect(withTrends).toBeGreaterThan(withoutTrends);
  });

  it("caps at 100", () => {
    const data = makeAnalyzeResponse({
      trends: {
        home_form: { label: "Ev", sample_size: 5, win_pct: 80, draw_pct: 10, loss_pct: 10, kg_var_pct: 50, over_25_pct: 50, avg_goals_for: 2, avg_goals_against: 0.5, last_n_results: ["G"] },
        away_form: { label: "Dep", sample_size: 5, win_pct: 30, draw_pct: 30, loss_pct: 40, kg_var_pct: 50, over_25_pct: 50, avg_goals_for: 1, avg_goals_against: 1.5, last_n_results: ["M"] },
        h2h: { label: "H2H", sample_size: 5, win_pct: 50, draw_pct: 30, loss_pct: 20, kg_var_pct: 40, over_25_pct: 40, avg_goals_for: 1.2, avg_goals_against: 1.0, last_n_results: ["B"] },
      },
    });
    const b = makePatternResult({ match_count: 100, result_1_pct: 90 });
    const c = makePatternResult({ match_count: 50, result_1_pct: 85 });
    expect(computePowerScore(data, b, c)).toBeLessThanOrEqual(100);
  });

  it("gives dual archive bonus", () => {
    const data = makeAnalyzeResponse();
    const b = makePatternResult({ match_count: 10, result_1_pct: 50 });
    const c = makePatternResult({ match_count: 3, result_1_pct: 55 });
    const withDual = computePowerScore(data, b, c);
    const cTooFew = makePatternResult({ match_count: 0 });
    const withoutDual = computePowerScore(data, b, cTooFew);
    expect(withDual).toBeGreaterThan(withoutDual);
  });
});

describe("PowerScoreGauge", () => {
  it("renders nothing when score is 0", () => {
    const { container } = render(
      <PowerScoreGauge score={0} patternB={null} patternC={null} trendCount={0} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders gauge with score", () => {
    const b = makePatternResult({ match_count: 30 });
    render(
      <PowerScoreGauge score={65} patternB={b} patternC={null} trendCount={2} />,
    );
    expect(screen.getByText("65")).toBeTruthy();
    expect(screen.getByText("Maç Güç Skoru")).toBeTruthy();
  });

  it("shows archive badges", () => {
    const b = makePatternResult({ match_count: 25 });
    const c = makePatternResult({ match_count: 8 });
    render(
      <PowerScoreGauge score={50} patternB={b} patternC={c} trendCount={0} />,
    );
    expect(screen.getByText("Arşiv 1: 25 maç")).toBeTruthy();
    expect(screen.getByText("Arşiv 2: 8 maç")).toBeTruthy();
  });

  it("shows trend badge", () => {
    const b = makePatternResult({ match_count: 10 });
    render(
      <PowerScoreGauge score={40} patternB={b} patternC={null} trendCount={3} />,
    );
    expect(screen.getByText("Trend: 3/3")).toBeTruthy();
  });

  it("shows dual archive badge when both qualify", () => {
    const b = makePatternResult({ match_count: 10 });
    const c = makePatternResult({ match_count: 2 });
    render(
      <PowerScoreGauge score={50} patternB={b} patternC={c} trendCount={0} />,
    );
    expect(screen.getByText("Çift arşiv onayı")).toBeTruthy();
  });
});
