import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import MatchedMatchesList from "@/components/MatchedMatchesList";
import { LocaleProvider } from "@/lib/locale-context";

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

function Wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider initial="tr">{children}</LocaleProvider>;
}

describe("MatchedMatchesList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("returns null when no pattern flags are true", () => {
    const { container } = render(<MatchedMatchesList matchId="123" hasPatternB={false} hasPatternC={false} />, { wrapper: Wrapper });
    expect(container.innerHTML).toBe("");
  });

  it("renders button when pattern flags are true", () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    expect(screen.getByRole("button")).toBeTruthy();
  });

  it("fetches data on button click", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    const { getMatchedMatches } = await import("@/lib/api");
    expect(getMatchedMatches).toHaveBeenCalledWith("123");
  });

  it("renders archive_b matches after click", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText("Team A - Team B")).toBeTruthy();
      expect(screen.getByText("Team C - Team D")).toBeTruthy();
    });
  });

  it("renders archive_c matches when hasPatternC is true", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={false} hasPatternC={true} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText("Team E - Team F")).toBeTruthy();
    });
  });

  it("renders archive_d matches with similarity percentage", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={true} hasPatternD={true} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/Arşiv 3/)).toBeTruthy();
      expect(screen.getByText("Team G - Team H")).toBeTruthy();
      expect(screen.getByText("92.3%")).toBeTruthy();
    });
  });

  it("renders score badges (İY/2Y/MS)", async () => {
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getAllByText("İY").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("MS").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows empty state when all archives are empty", async () => {
    const { getMatchedMatches } = await import("@/lib/api");
    vi.mocked(getMatchedMatches).mockResolvedValueOnce({ archive_b: [], archive_c: [], archive_d: [] });
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText("Eşleşen maç bulunamadı")).toBeTruthy();
    });
  });

  it("shows loading indicator when fetching", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.getMatchedMatches).mockReturnValue(new Promise(() => {}));
    render(<MatchedMatchesList matchId="123" hasPatternB={true} hasPatternC={false} />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Yükleniyor...")).toBeTruthy();
  });
});
