import { expect, it, describe, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import ComboSuggestion from "@/components/ComboSuggestion";
import { MatchProvider } from "@/lib/match-context";
import { STORAGE_KEY } from "@/lib/cart";
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

const richPattern = makePatternResult({
  match_count: 40,
  result_1_pct: 82,
  result_x_pct: 10,
  result_2_pct: 8,
  kg_var_pct: 78,
  kg_yok_pct: 22,
  ust_25_pct: 76,
  alt_25_pct: 24,
  ust_15_pct: 88,
  alt_15_pct: 12,
  dc_1x_pct: 92,
  dc_x2_pct: 8,
  dc_12_pct: 90,
  fark_ev1_pct: 78,
  fark_ber_pct: 12,
  fark_dep1_pct: 5,
});

describe("ComboSuggestion", () => {
  it("returns null when both patterns are null", () => {
    const { container } = renderWithContext(
      <ComboSuggestion patternB={null} patternC={null} period="ft" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null when match_count is too low", () => {
    const low = makePatternResult({ match_count: 2, result_1_pct: 90 });
    const { container } = renderWithContext(
      <ComboSuggestion patternB={low} patternC={null} period="ft" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders combo cards with rich pattern data", () => {
    renderWithContext(
      <ComboSuggestion patternB={richPattern} patternC={null} period="ft" />,
    );
    expect(screen.getByText("Birlikte Değerlendirilebilen Seçimler")).toBeDefined();
    expect(screen.queryAllByText(/^≈/)).toHaveLength(0);
  });

  it("shows combo count badge", () => {
    renderWithContext(
      <ComboSuggestion patternB={richPattern} patternC={null} period="ft" />,
    );
    const badges = screen.getAllByText(/^[1-3]$/);
    expect(badges.length).toBeGreaterThan(0);
  });

  it("each combo card has 'Sepete Ekle' button with leg count", () => {
    renderWithContext(
      <ComboSuggestion patternB={richPattern} patternC={null} period="ft" />,
    );
    const addButtons = screen.getAllByText(/Sepete Ekle/);
    expect(addButtons.length).toBeGreaterThan(0);
    addButtons.forEach((btn) => {
      expect(btn.textContent).toMatch(/\d+ seçim/);
    });
  });

  it("clicking 'Sepete Ekle' adds legs to cart", () => {
    renderWithContext(
      <ComboSuggestion patternB={richPattern} patternC={null} period="ft" />,
    );
    const addButtons = screen.getAllByText(/Sepete Ekle/);
    fireEvent.click(addButtons[0]);
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    expect(stored.length).toBeGreaterThan(0);
  });

  it("renders without MatchProvider (no add buttons)", () => {
    render(<ComboSuggestion patternB={richPattern} patternC={null} period="ft" />);
    expect(screen.queryAllByText(/Sepete Ekle/)).toHaveLength(0);
  });
});
