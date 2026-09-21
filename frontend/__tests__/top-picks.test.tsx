import { expect, it, describe, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import TopPicks from "@/components/TopPicks";
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

describe("TopPicks", () => {
  it("shows empty message when no patterns", () => {
    renderWithContext(<TopPicks patternB={null} patternC={null} period="ft" />);
    expect(screen.getByText(/en büyük örneklem 0 maç/)).toBeDefined();
  });

  it("shows empty message when match_count is zero", () => {
    const empty = makePatternResult({ match_count: 0 });
    renderWithContext(<TopPicks patternB={empty} patternC={null} period="ft" />);
    expect(screen.getByText(/en büyük örneklem 0 maç/)).toBeDefined();
  });

  it("shows the actual sample when it is too small for a recommendation", () => {
    const small = makePatternResult({ match_count: 7, result_1_pct: 100 });
    renderWithContext(<TopPicks patternB={small} patternC={null} period="ft" />);
    expect(screen.getByText(/en büyük örneklem 7 maç/)).toBeDefined();
  });

  it("renders picks when pattern has high percentages", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 80,
      result_x_pct: 10,
      result_2_pct: 10,
      kg_var_pct: 75,
      kg_yok_pct: 25,
      ust_25_pct: 70,
      alt_25_pct: 30,
    });
    renderWithContext(<TopPicks patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText("Arşivde Öne Çıkanlar")).toBeDefined();
    expect(screen.getByText("%80")).toBeDefined();
  });

  it("shows match count and threshold in header", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 80,
      result_x_pct: 10,
      result_2_pct: 10,
    });
    renderWithContext(<TopPicks patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText(/En az 20 maç/)).toBeDefined();
    expect(screen.getByText(/eşik seçime göre/)).toBeDefined();
  });

  it("renders archive badge for single archive picks", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 85,
      result_x_pct: 10,
      result_2_pct: 5,
    });
    renderWithContext(<TopPicks patternB={b} patternC={null} period="ft" />);
    expect(screen.getAllByText("Arş.1").length).toBeGreaterThan(0);
  });

  it("renders 1+2 badge when both archives agree", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 85,
      result_x_pct: 10,
      result_2_pct: 5,
    });
    const c = makePatternResult({
      match_count: 20,
      result_1_pct: 80,
      result_x_pct: 12,
      result_2_pct: 8,
    });
    renderWithContext(<TopPicks patternB={b} patternC={c} period="ft" />);
    expect(screen.getAllByText("1+2").length).toBeGreaterThan(0);
  });

  it("shows add-to-cart buttons when inside MatchProvider", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 85,
      result_x_pct: 10,
      result_2_pct: 5,
    });
    renderWithContext(<TopPicks patternB={b} patternC={null} period="ft" />);
    expect(screen.getAllByLabelText("Sepete ekle").length).toBeGreaterThan(0);
  });

  it("renders without MatchProvider (no cart buttons)", () => {
    const b = makePatternResult({
      match_count: 30,
      result_1_pct: 85,
      result_x_pct: 10,
      result_2_pct: 5,
    });
    render(<TopPicks patternB={b} patternC={null} period="ft" />);
    expect(screen.getByText("Arşivde Öne Çıkanlar")).toBeDefined();
    expect(screen.queryAllByLabelText("Sepete ekle")).toHaveLength(0);
  });

  it("limits to 8 picks max", () => {
    const b = makePatternResult({
      match_count: 50,
      result_1_pct: 90,
      result_x_pct: 5,
      result_2_pct: 5,
      dc_1x_pct: 95,
      dc_x2_pct: 5,
      dc_12_pct: 95,
      kg_var_pct: 85,
      kg_yok_pct: 15,
      ust_25_pct: 80,
      alt_25_pct: 20,
      ust_35_pct: 75,
      alt_35_pct: 25,
      ust_15_pct: 90,
      alt_15_pct: 10,
      fark_ev1_pct: 75,
      fark_ber_pct: 10,
      fark_dep1_pct: 5,
    });
    const { container } = renderWithContext(<TopPicks patternB={b} patternC={null} period="ft" />);
    const pickRows = container.querySelectorAll(".grid.grid-cols-1 > div");
    expect(pickRows.length).toBeLessThanOrEqual(8);
    expect(pickRows.length).toBeGreaterThan(0);
  });
});
