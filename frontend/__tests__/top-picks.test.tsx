import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import TopPicks from "@/components/TopPicks";
import { MatchProvider } from "@/lib/match-context";
import type { FTRecommendation } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const recommendation: FTRecommendation = {
  recommendation_id: "ft-display-v3:result:1", archive: "both", market: "result", selection: "1",
  frequency_pct: 72, match_count: 30, archive_1_frequency_pct: 75, archive_1_match_count: 35,
  archive_2_frequency_pct: 72, archive_2_match_count: 30,
};

function renderWithContext(ui: React.ReactElement) {
  return render(<MatchProvider value={{ matchId: "123", homeTeam: "Home", awayTeam: "Away" }}>{ui}</MatchProvider>);
}

describe("TopPicks", () => {
  it("shows only frozen full-time recommendations", () => {
    renderWithContext(<TopPicks recommendations={[recommendation]} period="ft" />);
    expect(screen.getByText("İleri dönem deneysel seçimler")).toBeDefined();
    expect(screen.getByText("Ev Sahibi")).toBeDefined();
    expect(screen.getByText("%72")).toBeDefined();
    expect(screen.getByText("1+2")).toBeDefined();
  });

  it("does not present untracked recommendations for half periods", () => {
    const { container } = renderWithContext(<TopPicks recommendations={[recommendation]} period="ht" />);
    expect(container.textContent).toBe("");
  });

  it("states when no pre-match recommendation was frozen", () => {
    renderWithContext(<TopPicks recommendations={[]} period="ft" />);
    expect(screen.getByText(/kaydedilmiş seçim bulunmuyor/)).toBeDefined();
  });

  it("adds the exact tracked selection to the cart", () => {
    renderWithContext(<TopPicks recommendations={[recommendation]} period="ft" />);
    screen.getByRole("button", { name: "Sepete ekle" }).click();
    expect(window.localStorage.getItem("nortverse_bet_cart")).toContain('"marketKey":"result"');
  });
});
