import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import MatchedMatchesList from "@/components/MatchedMatchesList";

const mockData = {
  archive_b: [
    { match_id: "1001", home_team: "Team A", away_team: "Team B", league_code: "ENG PR", ht: "0-1", h2: null, ft: "1-2", kickoff_time: null },
    { match_id: "1002", home_team: "Team C", away_team: "Team D", league_code: "SPA D1", ht: "1-0", h2: "1-1", ft: "2-1", kickoff_time: null },
  ],
  archive_c: [
    { match_id: "2001", home_team: "Team E", away_team: "Team F", league_code: "ITA D1", ht: "0-0", h2: null, ft: "1-0", kickoff_time: null },
  ],
  archive_d: [
    { match_id: "3001", home_team: "Team G", away_team: "Team H", league_code: "GER D1", ht: "1-1", h2: "0-0", ft: "1-1", kickoff_time: null, similarity: 0.923 },
  ],
};

vi.mock("@/lib/api", () => ({
  getMatchedMatches: vi.fn(() => Promise.resolve(mockData)),
}));

describe("MatchedMatchesList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("returns null when no pattern flags are true", () => {
    const { container } = render(
      <MatchedMatchesList matchId="123" hasPatternB={false} hasPatternC={false} hasPatternD={false} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders accordion button with title", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    expect(screen.getByText("Eşleşen Arşiv Maçları")).toBeTruthy();
  });

  it("shows A1 badge when hasPatternB", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    expect(screen.getByText("A1")).toBeTruthy();
    expect(screen.queryByText("A2")).toBeNull();
  });

  it("shows A2 badge when hasPatternC", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={false} hasPatternC={true} />);
    expect(screen.getByText("A2")).toBeTruthy();
    expect(screen.queryByText("A1")).toBeNull();
  });

  it("shows A3 badge when hasPatternD", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={false} hasPatternC={false} hasPatternD={true} />);
    expect(screen.getByText("A3")).toBeTruthy();
  });

  it("shows all three badges when all patterns active", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />);
    expect(screen.getByText("A1")).toBeTruthy();
    expect(screen.getByText("A2")).toBeTruthy();
    expect(screen.getByText("A3")).toBeTruthy();
  });

  it("starts collapsed with aria-expanded=false", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-expanded")).toBe("false");
  });

  it("expands on click and fetches data", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />);
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    await waitFor(() => {
      expect(screen.getByText("Team A - Team B")).toBeTruthy();
    });
  });

  it("renders archive_b matches with section header", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/Arşiv 1/)).toBeTruthy();
      expect(screen.getByText("2 maç")).toBeTruthy();
      expect(screen.getByText("Team A - Team B")).toBeTruthy();
      expect(screen.getByText("Team C - Team D")).toBeTruthy();
    });
  });

  it("renders archive_c matches with section header", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/Arşiv 2/)).toBeTruthy();
      expect(screen.getAllByText("1 maç").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Team E - Team F")).toBeTruthy();
    });
  });

  it("renders archive_d matches with similarity percentage", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/Arşiv 3/)).toBeTruthy();
      expect(screen.getByText("Team G - Team H")).toBeTruthy();
      expect(screen.getByText("92.3%")).toBeTruthy();
    });
  });

  it("renders score badges (IY/2Y/MS)", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getAllByText("IY").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("MS").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows empty state when all archives are empty", async () => {
    const { getMatchedMatches } = await import("@/lib/api");
    vi.mocked(getMatchedMatches).mockResolvedValueOnce({ archive_b: [], archive_c: [], archive_d: [] });
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText("Eşleşen maç bulunamadı")).toBeTruthy();
    });
  });

  it("shows loading indicator when fetching", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.getMatchedMatches).mockReturnValue(new Promise(() => {}));
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Yükleniyor...")).toBeTruthy();
  });
});
