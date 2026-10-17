import { expect, it, describe, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import BultenRow from "@/components/BultenRow";
import type { FixtureMatch } from "@/lib/types";
import { getDictionary } from "@/lib/i18n";

vi.mock("next/link", () => ({
  default: ({ children, href, className, style }: { children: React.ReactNode; href: string; className?: string; style?: React.CSSProperties }) => (
    <a href={href} className={className} style={style}>{children}</a>
  ),
}));

afterEach(() => { cleanup(); });

const t = getDictionary("tr");

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
    has_prediction: true,
    ...overrides,
  };
}

describe("BultenRow", () => {
  it("renders team names", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.getByText("Kayserispor")).toBeDefined();
    expect(screen.getByText("Karagumruk")).toBeDefined();
  });

  it("renders kickoff time", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.getAllByText("21:00").length).toBeGreaterThan(0);
  });

  it("shows a live minute and score in the bulletin", () => {
    render(<BultenRow match={makeMatch({ status: "live", live_home: 1, live_away: 2,
      live_minute: "67", score_checked_at: new Date().toISOString() })} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.getByText("67′")).toBeDefined();
    expect(screen.getByText("1 - 2")).toBeDefined();
  });

  it("renders placeholder time with muted style", () => {
    render(<BultenRow match={makeMatch()} timeStr="--:--" t={t} dateLocale="tr-TR" />);
    const timeEls = screen.getAllByText("--:--");
    expect(timeEls.length).toBeGreaterThan(0);
    const el = timeEls[0];
    expect(el.style.color).toBe("var(--nv-text-tertiary)");
  });

  it("links to analyze page with query params", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    const link = screen.getByRole("link");
    const href = link.getAttribute("href")!;
    expect(href).toContain("/analyze/2813084");
    expect(href).toContain("home=Kayserispor");
    expect(href).toContain("away=Karagumruk");
  });

  it("shows league name", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.getAllByText("Turkish Super League").length).toBeGreaterThan(0);
  });

  it("falls back to league_code when league_name is null", () => {
    render(<BultenRow match={makeMatch({ league_name: null, league_code: "TUR D1" })} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.getAllByText("TUR D1").length).toBeGreaterThan(0);
  });

  it("renders league flag emoji", () => {
    const { container } = render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    const flagEl = container.querySelector(".text-lg.leading-none") as HTMLElement;
    expect(flagEl).toBeDefined();
    expect(flagEl.textContent!.length).toBeGreaterThan(0);
  });

  it("shows A1 badge when pattern B matches exist", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" patternStatus={{ has_b: true, has_c: false }} t={t} dateLocale="tr-TR" />);
    expect(screen.getByText("A1")).toBeDefined();
    expect(screen.queryByText("A2")).toBeNull();
  });

  it("shows A2 badge when pattern C matches exist", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" patternStatus={{ has_b: false, has_c: true }} t={t} dateLocale="tr-TR" />);
    expect(screen.queryByText("A1")).toBeNull();
    expect(screen.getByText("A2")).toBeDefined();
  });

  it("shows both A1 and A2 badges when both patterns match but disagree", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" patternStatus={{ has_b: true, has_c: true, agreement: false }} t={t} dateLocale="tr-TR" />);
    expect(screen.getByText("A1")).toBeDefined();
    expect(screen.getByText("A2")).toBeDefined();
    expect(screen.queryByText("A1+A2")).toBeNull();
  });

  it("shows unified A1+A2 golden badge when both archives agree", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" patternStatus={{ has_b: true, has_c: true, agreement: true }} t={t} dateLocale="tr-TR" />);
    expect(screen.getByText("A1+A2")).toBeDefined();
    expect(screen.queryByText(/^A1$/)).toBeNull();
    expect(screen.queryByText(/^A2$/)).toBeNull();
  });

  it("shows no badge when patternStatus is undefined", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR" />);
    expect(screen.queryByText("A1")).toBeNull();
    expect(screen.queryByText("A2")).toBeNull();
  });

  it("encodes special characters in team name URL params", () => {
    render(
      <BultenRow
        match={makeMatch({ home_team: "FC Zürich", away_team: "BSC Young Boys" })}
        timeStr="20:30"
        t={t}
        dateLocale="tr-TR"
      />,
    );
    const link = screen.getByRole("link");
    const href = link.getAttribute("href")!;
    expect(href).toContain("FC%20Z");
  });

  it("A1+A2 uyumunda A3 rozeti de görünür", () => {
    render(<BultenRow match={makeMatch()} timeStr="21:00" t={t} dateLocale="tr-TR"
      patternStatus={{ has_b: true, has_c: true, has_d: true, agreement: true, agreement_bcd: false }} />);
    expect(screen.getByText("A1+A2")).toBeTruthy();
    expect(screen.getByText("A3")).toBeTruthy();
  });
});
