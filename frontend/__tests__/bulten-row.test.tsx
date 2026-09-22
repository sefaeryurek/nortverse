import { expect, it, describe, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import BultenRow from "@/components/BultenRow";
import type { FixtureMatch } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({ children, href, className, style }: { children: React.ReactNode; href: string; className?: string; style?: React.CSSProperties }) => (
    <a href={href} className={className} style={style}>{children}</a>
  ),
}));

afterEach(() => { cleanup(); });

function makeMatch(overrides: Partial<FixtureMatch> = {}): FixtureMatch {
  return {
    match_id: "2813084",
    home_team: "Kayserispor",
    away_team: "Karagumruk",
    league_code: "Turkish Super League",
    league_name: "Turkish Super League",
    kickoff_time: "2026-09-15T18:00:00Z",
    status: "scheduled",
    live_home: null,
    live_away: null,
    live_minute: null,
    score_checked_at: null,
    ...overrides,
  };
}

describe("BultenRow", () => {
  it("renders team names", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" />);
    expect(screen.getByText("Kayserispor")).toBeDefined();
    expect(screen.getByText("Karagumruk")).toBeDefined();
  });

  it("renders kickoff time", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" />);
    expect(screen.getAllByText("21:00").length).toBeGreaterThan(0);
  });

  it("shows a live minute and score in the bulletin", () => {
    render(<BultenRow match={makeMatch({ status: "live", live_home: 1, live_away: 2,
      live_minute: "67", score_checked_at: new Date().toISOString() })} timeStr="21:00" />);
    expect(screen.getByText("67′")).toBeDefined();
    expect(screen.getByText("1 - 2")).toBeDefined();
    expect(screen.getByLabelText("Canlı skor")).toBeDefined();
  });

  it("labels a stale live score as the last known score", () => {
    render(<BultenRow match={makeMatch({ status: "live", live_home: 1, live_away: 2,
      live_minute: "67", score_checked_at: "2026-09-15T18:00:00Z" })} timeStr="21:00" />);
    expect(screen.getByText("Son skor")).toBeDefined();
    expect(screen.getByLabelText("Son görülen skor; güncel veri bekleniyor")).toBeDefined();
  });

  it("renders placeholder time with muted style", () => {
    render(<BultenRow match={makeMatch()} timeStr="--:--" />);
    const timeEls = screen.getAllByText("--:--");
    expect(timeEls.length).toBeGreaterThan(0);
    const el = timeEls[0];
    expect(el.style.color).toBe("rgb(71, 85, 105)");
  });

  it("links to analyze page with query params", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" />);
    const link = screen.getByRole("link");
    const href = link.getAttribute("href")!;
    expect(href).toContain("/analyze/2813084");
    expect(href).toContain("home=Kayserispor");
    expect(href).toContain("away=Karagumruk");
  });

  it("shows league name", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" />);
    expect(screen.getAllByText("Turkish Super League").length).toBeGreaterThan(0);
  });

  it("falls back to league_code when league_name is null", () => {
    render(<BultenRow match={makeMatch({ league_name: null, league_code: "TUR D1" })} timeStr="21:00" />);
    expect(screen.getAllByText("TUR D1").length).toBeGreaterThan(0);
  });

  it("renders league flag emoji", () => {
    const { container } = render(<BultenRow match={makeMatch()} timeStr="21:00" />);
    const flagEl = container.querySelector(".text-lg.leading-none") as HTMLElement;
    expect(flagEl).toBeDefined();
    expect(flagEl.textContent!.length).toBeGreaterThan(0);
  });

  it("encodes special characters in team name URL params", () => {
    render(
      <BultenRow
        match={makeMatch({ home_team: "FC Zürich", away_team: "BSC Young Boys" })}
        timeStr="20:30"
      />,
    );
    const link = screen.getByRole("link");
    const href = link.getAttribute("href")!;
    expect(href).toContain("FC%20Z");
  });
});
