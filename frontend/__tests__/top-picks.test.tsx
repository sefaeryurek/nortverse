import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import TopPicks from "@/components/TopPicks";
import { MatchProvider } from "@/lib/match-context";
import type { FTRecommendation } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const recommendation: FTRecommendation = {
  recommendation_id: "ft-display-v3:result:1", archive: "archive_1+archive_2", market: "result", selection: "1",
  frequency_pct: 72, match_count: 30, calibrated_pct: null, margin: null, is_confident: false,
  archive_1_frequency_pct: 75, archive_1_match_count: 35,
  archive_2_frequency_pct: 72, archive_2_match_count: 30,
  archive_3_frequency_pct: null, archive_3_match_count: null,
};

function renderWithContext(ui: React.ReactElement) {
  return render(<MatchProvider value={{ matchId: "123", homeTeam: "Home", awayTeam: "Away" }}>{ui}</MatchProvider>);
}

describe("TopPicks", () => {
  it("shows only frozen full-time recommendations", () => {
    renderWithContext(<TopPicks recommendations={[recommendation]} period="ft" />);
    expect(screen.getByText("Maç öncesi seçim")).toBeDefined();
    expect(screen.getByText("Ev Sahibi")).toBeDefined();
    expect(screen.getByText("%72")).toBeDefined();
    expect(screen.getByText("A1+A2")).toBeDefined();
  });

  it("shows v4 calibrated probability, league average and signal tier; cart gets calibrated pct", () => {
    const v4: FTRecommendation = {
      ...recommendation, recommendation_id: "ft-display-v4:result:2", selection: "2",
      frequency_pct: 61, calibrated_pct: 48.2, margin: 17.6, confidence_tier: "high", prior_pct: 30.6,
    };
    renderWithContext(<TopPicks recommendations={[v4]} period="ft" />);
    expect(screen.getAllByText("%48").length).toBeGreaterThan(0);
    expect(screen.getByText("Güçlü sinyal")).toBeDefined();
    expect(screen.getByText(/Lig ortalaması %30.6 · avantaj \+17.6 puan/)).toBeDefined();
    expect(screen.getByText(/ft-display-v4/)).toBeDefined();
  });

  it("does not present untracked recommendations for half periods", () => {
    const { container } = renderWithContext(<TopPicks recommendations={[recommendation]} period="ht" />);
    expect(container.textContent).toBe("");
  });

  it("states when no pre-match recommendation was frozen", () => {
    renderWithContext(<TopPicks recommendations={[]} period="ft" />);
    expect(screen.getByText(/yayın şartını sağlayan bir seçim yok/)).toBeDefined();
  });

  it("adds the exact tracked selection to the cart", () => {
    renderWithContext(<TopPicks recommendations={[recommendation]} period="ft" />);
    screen.getByRole("button", { name: "Sepete ekle" }).click();
    expect(window.localStorage.getItem("nortverse_bet_cart")).toContain('"marketKey":"result"');
  });

  it("warns only when the pick was frozen with different archive settings", () => {
    const { rerender } = renderWithContext(<TopPicks recommendations={[recommendation]} period="ft" settingsChanged />);
    expect(screen.getByText(/farklı bir arşiv ayarıyla donduruldu/)).toBeDefined();
    rerender(
      <MatchProvider value={{ matchId: "123", homeTeam: "Home", awayTeam: "Away" }}>
        <TopPicks recommendations={[recommendation]} period="ft" />
      </MatchProvider>,
    );
    expect(screen.queryByText(/farklı bir arşiv ayarıyla donduruldu/)).toBeNull();
  });
});
