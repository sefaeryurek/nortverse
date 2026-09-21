import { expect, it, describe, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import MarketSummary from "@/components/MarketSummary";
import { MatchProvider } from "@/lib/match-context";
import { makePatternResult } from "./fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function renderWithContext(ui: React.ReactElement) {
  return render(
    <MatchProvider value={{ matchId: "2813084", homeTeam: "Kayserispor", awayTeam: "Karagumruk" }}>
      {ui}
    </MatchProvider>,
  );
}

describe("MarketSummary", () => {
  it("returns null when both patterns are null", () => {
    const { container } = renderWithContext(
      <MarketSummary patternB={null} patternC={null} period="ft" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders with zero-pct data without crashing", () => {
    const empty = makePatternResult({ match_count: 0 });
    renderWithContext(
      <MarketSummary patternB={empty} patternC={null} period="ft" />,
    );
  });

  it("renders market rows with pattern data", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 60,
      result_x_pct: 25,
      result_2_pct: 15,
      ust_25_pct: 70,
      alt_25_pct: 30,
      kg_var_pct: 55,
      kg_yok_pct: 45,
    });
    renderWithContext(<MarketSummary patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText("Ana Pazar Özeti")).toBeDefined();
    expect(screen.getByText("Arşiv 1 · 30 maç")).toBeDefined();
    expect(screen.getByText("Arşiv 2")).toBeDefined();
  });

  it("shows agreement marker when archives match", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 70,
      result_x_pct: 20,
      result_2_pct: 10,
    });
    const c = makePatternResult({
      match_count: 20,
      result_1_pct: 68,
      result_x_pct: 22,
      result_2_pct: 10,
    });
    renderWithContext(<MarketSummary patternB={b} patternC={c} period="ft" />);
    expect(screen.getAllByText("✦").length).toBeGreaterThan(0);
  });

  it("keeps raw market frequencies informational even at high percentages", () => {
    const b = makePatternResult({
      match_count: 1,
      result_1_pct: 100,
      result_x_pct: 0,
      result_2_pct: 0,
    });
    renderWithContext(<MarketSummary patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText("Arşiv 1 · 1 maç")).toBeDefined();
    expect(screen.queryAllByLabelText("Sepete ekle")).toHaveLength(0);
  });

  it("renders without MatchProvider (no cart buttons)", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 75,
      result_x_pct: 15,
      result_2_pct: 10,
    });
    render(<MarketSummary patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText("Ana Pazar Özeti")).toBeDefined();
    expect(screen.queryAllByLabelText("Sepete ekle")).toHaveLength(0);
  });
});
